"""Sahte Playlist Dedektoru — GERCEK veri pipeline testleri (spotify_client +
fraud_forensics entegrasyonu). Spotify/Deezer/musical_seo.audio/audit
tamamen monkeypatch'lenir — bu dosyada AG YOK.

Kapsam:
- marketplace.spotify_client: parse_playlist_id, get_token (kimliksiz),
  get_playlist (guarded, monkeypatch'li istek).
- fraud_forensics.snapshot_playlist: satir yazar, guvenceli (None -> sessiz).
- analyze_playlist canli playlist ornegini kullanir: follower_anomaly zaman
  serisi ile informatif olur, audio_label_mismatch/track_seo_poverty
  playlist parca ornegiyle informatif olur.
- Renormalizasyon: geo_cluster (veri kaynagi yok) HER ZAMAN agirlikli
  skordan dislanir; kalan sinyallerin agirligi 1'e olceklenir.
- data_coverage alani + veri_yetersiz esigi renormalizasyondan sonra da korunur.
- Spotify kimlik bilgisi yoksa (get_playlist None) analiz yine de patlamadan
  calisir, snapshot atlanir.
"""
from __future__ import annotations

import pytest

from marketplace import db, fraud_forensics, spotify_client


@pytest.fixture()
def fraud_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


# --- spotify_client: parse_playlist_id (saf, agsiz) --------------------------

def test_parse_playlist_id_from_open_spotify_url():
    url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc123"
    assert spotify_client.parse_playlist_id(url) == "37i9dQZF1DXcBWIGoYBM5M"


def test_parse_playlist_id_from_intl_prefixed_url():
    url = "https://open.spotify.com/intl-tr/playlist/ABC123XYZ"
    assert spotify_client.parse_playlist_id(url) == "ABC123XYZ"


def test_parse_playlist_id_from_uri():
    assert spotify_client.parse_playlist_id("spotify:playlist:ZZZ999") == "ZZZ999"


def test_parse_playlist_id_returns_none_for_non_spotify_url():
    assert spotify_client.parse_playlist_id("https://deezer.com/playlist/1") is None
    assert spotify_client.parse_playlist_id("") is None


# --- spotify_client: get_token / get_playlist (guarded) ----------------------

def test_get_token_returns_none_without_credentials(monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    spotify_client._token_cache["access_token"] = None
    spotify_client._token_cache["expires_at"] = 0.0
    assert spotify_client.get_token() is None
    assert spotify_client.available() is False


def test_get_playlist_returns_none_without_token(monkeypatch):
    monkeypatch.setattr(spotify_client, "get_token", lambda: None)
    assert spotify_client.get_playlist("anyid") is None


def test_get_playlist_returns_none_on_non_200(monkeypatch):
    monkeypatch.setattr(spotify_client, "get_token", lambda: "fake-token")

    class FakeResponse:
        status_code = 404

    monkeypatch.setattr(
        spotify_client.requests, "get", lambda *a, **k: FakeResponse()
    )
    assert spotify_client.get_playlist("editorial123") is None


def test_get_playlist_parses_followers_and_tracks(monkeypatch):
    monkeypatch.setattr(spotify_client, "get_token", lambda: "fake-token")

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "name": "Gercek Liste",
                "followers": {"total": 4321},
                "tracks": {
                    "total": 2,
                    "items": [
                        {"track": {"id": "t1", "name": "Song A", "artists": [{"name": "Artist A"}]}},
                        {"track": {"id": "t2", "name": "Song B", "artists": [{"name": "Artist B"}]}},
                    ],
                },
            }

    monkeypatch.setattr(
        spotify_client.requests, "get", lambda *a, **k: FakeResponse()
    )
    result = spotify_client.get_playlist("id123")
    assert result == {
        "name": "Gercek Liste",
        "followers": 4321,
        "track_count": 2,
        "tracks": [
            {"id": "t1", "name": "Song A", "artists": ["Artist A"]},
            {"id": "t2", "name": "Song B", "artists": ["Artist B"]},
        ],
    }


# --- fraud_forensics.snapshot_playlist ---------------------------------------

def test_snapshot_playlist_writes_row_from_live_spotify_data(fraud_db, monkeypatch):
    url = "https://open.spotify.com/playlist/ABC123"
    fake_playlist = {
        "name": "Test Playlist",
        "followers": 1234,
        "track_count": 2,
        "tracks": [
            {"id": "t1", "name": "Song One", "artists": ["Artist A"]},
            {"id": "t2", "name": "Song Two", "artists": ["Artist B"]},
        ],
    }
    monkeypatch.setattr(
        fraud_forensics.spotify_client, "get_playlist", lambda pid: fake_playlist
    )

    result = fraud_forensics.snapshot_playlist(url)

    assert result == fake_playlist
    snapshots = fraud_forensics._fetch_snapshots(url)
    assert len(snapshots) == 1
    assert snapshots[0]["follower_count"] == 1234
    assert snapshots[0]["track_ids"] == ["t1", "t2"]


def test_snapshot_playlist_none_for_non_spotify_url_no_network(fraud_db):
    # Regex eslesmezse spotify_client.get_playlist HIC cagrilmaz (network yok).
    url = "https://deezer.com/playlist/1"
    assert fraud_forensics.snapshot_playlist(url) is None
    assert fraud_forensics._fetch_snapshots(url) == []


def test_snapshot_playlist_none_when_spotify_unavailable(fraud_db, monkeypatch):
    url = "https://open.spotify.com/playlist/NOCREDS"
    monkeypatch.setattr(fraud_forensics.spotify_client, "get_playlist", lambda pid: None)
    assert fraud_forensics.snapshot_playlist(url) is None
    assert fraud_forensics._fetch_snapshots(url) == []


# --- analyze_playlist: canli veri kullanir, zaman serisi birikir ------------

def test_analyze_playlist_follower_series_becomes_informative_across_calls(
    fraud_db, monkeypatch,
):
    url = "https://open.spotify.com/playlist/SERIES1"
    responses = iter([
        {
            "name": "P", "followers": 1000, "track_count": 1,
            "tracks": [{"id": "a", "name": "A", "artists": ["Art"]}],
        },
        {
            "name": "P", "followers": 1050, "track_count": 1,
            "tracks": [{"id": "a", "name": "A", "artists": ["Art"]}],
        },
    ])
    monkeypatch.setattr(
        fraud_forensics.spotify_client, "get_playlist", lambda pid: next(responses)
    )
    # audio/seo orneklemesini bu testte devre disi birak (izolasyon icin) —
    # ayri bir test tam zinciri (deezer+audio+audit) dogruluyor.
    monkeypatch.setattr(fraud_forensics, "_gather_audio_profiles", lambda tracks: [])
    monkeypatch.setattr(fraud_forensics, "_gather_track_scores", lambda tracks: [])

    fraud_forensics.analyze_playlist(url)  # ilk anlik goruntu (henuz notr)
    report = fraud_forensics.analyze_playlist(url)  # ikinci -> zaman serisi var

    assert report["signals"]["follower_anomaly"]["score"] != 0.5
    assert "follower_anomaly" in report["data_coverage"]["informative_signal_names"]


def test_analyze_playlist_uses_real_track_sample_for_audio_and_seo(fraud_db, monkeypatch):
    url = "https://open.spotify.com/playlist/FULL1"
    playlist = {
        "name": "Sakin Aksam Muzikleri",
        "followers": 500,
        "track_count": 1,
        "tracks": [{"id": "t1", "name": "Chill Song", "artists": ["Chill Artist"]}],
    }
    monkeypatch.setattr(fraud_forensics.spotify_client, "get_playlist", lambda pid: playlist)

    class FakeDeezerResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"preview": "https://fake/preview.mp3"}]}

    monkeypatch.setattr(
        fraud_forensics.requests, "get", lambda *a, **k: FakeDeezerResponse()
    )

    class FakeProfile:
        energy = 0.9  # "sakin" iddiasina karsi enerjik -> mismatch

    monkeypatch.setattr(fraud_forensics.audio, "available", lambda: True)
    monkeypatch.setattr(fraud_forensics.audio, "analyze_url", lambda preview_url: FakeProfile())

    class FakeAuditResult:
        score = 20  # dusuk SEO skoru -> poverty sinyali informatif + yuksek

    monkeypatch.setattr(fraud_forensics.seo_audit, "run_audit", lambda q: FakeAuditResult())

    report = fraud_forensics.analyze_playlist(url)

    assert report["playlist_title"] == "Sakin Aksam Muzikleri"
    assert report["signals"]["audio_label_mismatch"]["score"] != 0.5
    assert report["signals"]["audio_label_mismatch"]["score"] > 0.5
    assert report["signals"]["track_seo_poverty"]["score"] != 0.5
    assert report["signals"]["track_seo_poverty"]["score"] == 1.0


# --- Renormalizasyon (geo her zaman disarida) --------------------------------

def test_weighted_risk_score_excludes_geo_and_rescales_remaining_weights():
    signals = {
        "follower_anomaly": {"score": 0.8},
        "track_churn": {"score": 0.4},
        "geo_cluster": {"score": 0.5},       # notr/veri yok -> DISLANMALI
        "audio_label_mismatch": {"score": 0.6},
        "track_seo_poverty": {"score": 0.2},
    }
    total, informative = fraud_forensics._weighted_risk_score(signals)

    assert "geo_cluster" not in informative
    assert set(informative) == {
        "follower_anomaly", "track_churn", "audio_label_mismatch", "track_seo_poverty",
    }
    weight_sum = sum(fraud_forensics.SIGNAL_WEIGHTS[n] for n in informative)
    assert weight_sum == pytest.approx(0.85)  # 1.0 - geo'nun 0.15'i

    expected = (
        0.8 * 0.30 + 0.4 * 0.20 + 0.6 * 0.20 + 0.2 * 0.15
    ) / weight_sum * 100
    assert total == pytest.approx(round(expected, 1))


def test_weighted_risk_score_falls_back_to_raw_average_when_all_neutral():
    signals = {name: {"score": 0.5} for name in fraud_forensics.SIGNAL_WEIGHTS}
    total, informative = fraud_forensics._weighted_risk_score(signals)
    assert informative == []
    assert total == pytest.approx(50.0)


# --- data_coverage ------------------------------------------------------------

def test_data_coverage_reflects_informative_signal_count():
    signals = {
        "follower_anomaly": {"score": 0.9},
        "track_churn": {"score": 0.5},
        "geo_cluster": {"score": 0.5},
        "audio_label_mismatch": {"score": 0.5},
        "track_seo_poverty": {"score": 0.1},
    }
    coverage = fraud_forensics._data_coverage(signals)
    assert coverage["informative_signals"] == 2
    assert coverage["total_signals"] == 5
    assert coverage["ratio"] == pytest.approx(0.4)
    assert set(coverage["informative_signal_names"]) == {
        "follower_anomaly", "track_seo_poverty",
    }


def test_analyze_playlist_report_includes_data_coverage(fraud_db):
    report = fraud_forensics.analyze_playlist(
        "https://deezer.com/playlist/coverage-check", track_scores=[10, 15],
    )
    assert "data_coverage" in report
    assert report["data_coverage"]["total_signals"] == 5


def test_get_report_roundtrip_includes_recomputed_data_coverage(fraud_db):
    report = fraud_forensics.analyze_playlist(
        "https://deezer.com/playlist/coverage-roundtrip", track_scores=[10, 15],
    )
    fetched = fraud_forensics.get_report(report["report_token"])
    assert fetched is not None
    assert fetched["data_coverage"] == report["data_coverage"]


# --- veri_yetersiz esigi renormalizasyondan sonra da korunur -----------------

def test_single_informative_signal_gives_real_verdict(fraud_db):
    # MIN_INFORMATIVE=1: sadece track_seo_poverty informatif (1 sinyal) olsa bile
    # veri_yetersiz DEGIL — renormalize edilmis gercek verdict uretilir; guven
    # duzeyi data_coverage (1/5) ile gosterilir.
    report = fraud_forensics.analyze_playlist(
        "https://deezer.com/playlist/only-one-signal", track_scores=[10, 15],
    )
    assert report["verdict"] != "veri_yetersiz"
    assert report["data_coverage"]["informative_signals"] == 1


# --- Spotify kimlik bilgisi yok -> analiz yine de calisir, cokmez -----------

def test_analyze_playlist_when_spotify_unavailable_does_not_crash(fraud_db, monkeypatch):
    monkeypatch.setattr(fraud_forensics.spotify_client, "get_playlist", lambda pid: None)
    url = "https://open.spotify.com/playlist/NOCREDS2"

    report = fraud_forensics.analyze_playlist(url)

    assert report["verdict"] == "veri_yetersiz"  # hicbir sinyal informatif degil
    assert fraud_forensics._fetch_snapshots(url) == []  # snapshot atlandi, satir yok


# --- snapshot_all_known_playlists (gunluk cron) ------------------------------

def test_snapshot_all_known_playlists_covers_each_distinct_url(fraud_db, monkeypatch):
    fraud_forensics.analyze_playlist("https://deezer.com/playlist/x1")
    fraud_forensics.analyze_playlist("https://deezer.com/playlist/x2")
    fraud_forensics.analyze_playlist("https://deezer.com/playlist/x1")  # tekrar -> DISTINCT'te tek

    seen = []

    def fake_snapshot(url):
        seen.append(url)
        return None

    monkeypatch.setattr(fraud_forensics, "snapshot_playlist", fake_snapshot)
    count = fraud_forensics.snapshot_all_known_playlists()

    assert sorted(seen) == [
        "https://deezer.com/playlist/x1", "https://deezer.com/playlist/x2",
    ]
    assert count == 0  # fake_snapshot her zaman None doner


# --- progress callback (SSE canli akis) --------------------------------------

def test_analyze_playlist_emits_progress_stages_in_order(fraud_db, monkeypatch):
    """progress=None ile davranis ayni kalirken, callback verilirse
    resolve->snapshot->audio->seo->signals->done sirasiyla akmali (bkz.
    api_fraud.analyze_playlist_stream)."""
    monkeypatch.setattr(fraud_forensics.spotify_client, "get_playlist", lambda pid: None)
    url = "https://open.spotify.com/playlist/PROGRESS1"

    events: list[dict] = []
    report = fraud_forensics.analyze_playlist(
        url, track_scores=[10, 15], progress=events.append
    )

    stages = [e["stage"] for e in events]
    assert stages == ["resolve", "snapshot", "audio", "seo", "signals", "done"]
    assert all(isinstance(e["msg"], str) and e["msg"] for e in events)

    done_event = events[-1]
    assert done_event["data"]["report_token"] == report["report_token"]
    assert done_event["data"]["verdict"] == report["verdict"]
    assert done_event["data"]["total_risk_score"] == report["total_risk_score"]


def test_analyze_playlist_progress_callback_failure_never_breaks_analysis(
    fraud_db, monkeypatch,
):
    """_emit guvenceli: progress callback'i patlarsa bile analiz normal
    tamamlanip raporu dondurmeli (SSE tuketicisi hicbir zaman analizi bozmaz)."""
    monkeypatch.setattr(fraud_forensics.spotify_client, "get_playlist", lambda pid: None)
    url = "https://open.spotify.com/playlist/PROGRESSBOOM"

    def boom(event):
        raise RuntimeError("consumer patladi")

    report = fraud_forensics.analyze_playlist(url, progress=boom)

    assert report["report_token"].startswith("FRAUD-")


def test_snapshot_all_known_playlists_survives_individual_failures(fraud_db, monkeypatch):
    fraud_forensics.analyze_playlist("https://deezer.com/playlist/ok")
    fraud_forensics.analyze_playlist("https://deezer.com/playlist/boom")

    def flaky_snapshot(url):
        if "boom" in url:
            raise RuntimeError("Spotify kota asimi (simule)")
        return {"name": "ok", "followers": 1, "track_count": 0, "tracks": []}

    monkeypatch.setattr(fraud_forensics, "snapshot_playlist", flaky_snapshot)
    count = fraud_forensics.snapshot_all_known_playlists()

    assert count == 1  # sadece "ok" basarili sayildi, "boom" cokmeden atlandi
