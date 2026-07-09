"""'song' ve 'playlist' sayfa turleri icin uretim boru hatti testleri:
enqueue_song/enqueue_playlist idempotency + oncelik, build_next_batch'in
page_type'a gore dispatch etmesi (basarili/thin/failed, karisik kuyruk),
catalog_scout'un yeni seed fonksiyonlari. TUM dis cagrilar (deezer/audio/
audit/fraud_forensics.analyze_playlist/spotify_client) monkeypatch'lenir —
AG YOK.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from marketplace import catalog_scout, seo_pages


@pytest.fixture()
def seo_db(tmp_path, monkeypatch):
    monkeypatch.setattr(seo_pages, "_DB_PATH", tmp_path / "seo_pages.db")


def _fake_deezer_track(
    found=True, isrc="USRC00001", artist="Test Sanatci", title="Test Sarki",
    album="Test Album", release_date="2020-01-01", url="https://deezer.com/track/1",
    deezer_id=123,
):
    return SimpleNamespace(
        found=found, isrc=isrc, artist=artist, title=title, album=album,
        release_date=release_date, url=url, extra={"id": deezer_id},
    )


def _fake_audio_profile(bpm=120.0, energy=0.5, brightness=0.5, instrumental_score=0.1):
    return SimpleNamespace(
        bpm=bpm, energy=energy, brightness=brightness, instrumental_score=instrumental_score,
    )


def _fake_audit_result(score=70):
    return SimpleNamespace(score=score)


def _fake_fraud_report(
    verdict="guvenli", total_risk_score=10.0, title="Todays Top Hits",
    informative_signals=3,
):
    return {
        "playlist_title": title,
        "total_risk_score": total_risk_score,
        "verdict": verdict,
        "signals": {},
        "recommendation": "test",
        "report_token": "FRAUD-TEST",
        "data_coverage": {
            "informative_signals": informative_signals, "total_signals": 5,
            "ratio": informative_signals / 5, "informative_signal_names": [],
        },
    }


# --- enqueue_song ----------------------------------------------------------

def test_enqueue_song_idempotent(seo_db):
    first = seo_pages.enqueue_song("Drake - Hotline Bling")
    second = seo_pages.enqueue_song("Drake - Hotline Bling")
    assert first["id"] == second["id"]

    conn = seo_pages._connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM build_queue WHERE page_type = 'song'"
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 1


def test_enqueue_song_invalid_raises(seo_db):
    with pytest.raises(ValueError):
        seo_pages.enqueue_song("   ")


def test_enqueue_song_priority_stored(seo_db):
    row = seo_pages.enqueue_song("Drake - God's Plan", priority=250)
    assert row["priority"] == 250
    assert row["page_type"] == "song"
    assert row["ref"] == "Drake - God's Plan"


# --- enqueue_playlist --------------------------------------------------------

def test_enqueue_playlist_idempotent(seo_db):
    url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
    first = seo_pages.enqueue_playlist(url)
    second = seo_pages.enqueue_playlist(url)
    assert first["id"] == second["id"]

    conn = seo_pages._connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM build_queue WHERE page_type = 'playlist'"
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 1


def test_enqueue_playlist_invalid_raises(seo_db):
    with pytest.raises(ValueError):
        seo_pages.enqueue_playlist("")


def test_enqueue_playlist_priority_stored(seo_db):
    url = "https://open.spotify.com/playlist/abc123"
    row = seo_pages.enqueue_playlist(url, priority=400)
    assert row["priority"] == 400
    assert row["page_type"] == "playlist"


# --- build_next_batch: 'song' ------------------------------------------------

def test_build_next_batch_song_happy_path(seo_db, monkeypatch):
    seo_pages.enqueue_song("Test Sanatci - Test Sarki")
    monkeypatch.setattr(seo_pages.deezer, "lookup", lambda a, t: _fake_deezer_track())
    monkeypatch.setattr(seo_pages, "_deezer_preview_url", lambda tid: "https://preview.mp3")
    monkeypatch.setattr(seo_pages.audio, "analyze_url", lambda url: _fake_audio_profile())
    monkeypatch.setattr(seo_pages.audit, "run_audit", lambda q: _fake_audit_result(score=75))

    result = seo_pages.build_next_batch()
    assert result == {"processed": 1, "built": 1, "thin": 0, "failed": 0}

    page = seo_pages.get_song_page("USRC00001")
    assert page is not None
    assert page["artist"] == "Test Sanatci"
    assert page["title"] == "Test Sarki"
    assert page["score"] == 75
    assert page["bpm"] == 120.0
    assert page["song_key"]
    assert page["data_json"]["isrc"] == "USRC00001"


def test_build_next_batch_song_thin_when_not_found(seo_db, monkeypatch):
    seo_pages.enqueue_song("Bilinmeyen Sanatci - Bilinmeyen Sarki")
    monkeypatch.setattr(
        seo_pages.deezer, "lookup", lambda a, t: SimpleNamespace(found=False)
    )

    result = seo_pages.build_next_batch()
    assert result == {"processed": 1, "built": 0, "thin": 1, "failed": 0}


def test_build_next_batch_song_thin_when_no_isrc(seo_db, monkeypatch):
    seo_pages.enqueue_song("Test Sanatci - Test Sarki")
    monkeypatch.setattr(
        seo_pages.deezer, "lookup", lambda a, t: _fake_deezer_track(isrc=None)
    )

    result = seo_pages.build_next_batch()
    assert result == {"processed": 1, "built": 0, "thin": 1, "failed": 0}


def test_build_next_batch_song_thin_when_audit_score_missing(seo_db, monkeypatch):
    # Deezer cozumlenir (ISRC var) ama audit hicbir skor uretemez -> upsert
    # kendi thin-guard'ini uygular (score None).
    seo_pages.enqueue_song("Test Sanatci - Test Sarki")
    monkeypatch.setattr(seo_pages.deezer, "lookup", lambda a, t: _fake_deezer_track())
    monkeypatch.setattr(seo_pages, "_deezer_preview_url", lambda tid: None)

    def _boom(q):
        raise RuntimeError("audit network down")

    monkeypatch.setattr(seo_pages.audit, "run_audit", _boom)

    result = seo_pages.build_next_batch()
    assert result == {"processed": 1, "built": 0, "thin": 1, "failed": 0}
    assert seo_pages.get_song_page("USRC00001") is None


def test_build_next_batch_song_failed_on_deezer_exception(seo_db, monkeypatch):
    seo_pages.enqueue_song("Patlayan Sorgu - Sarki")

    def _boom(a, t):
        raise RuntimeError("deezer network down")

    monkeypatch.setattr(seo_pages.deezer, "lookup", _boom)

    result = seo_pages.build_next_batch()
    assert result == {"processed": 1, "built": 0, "thin": 0, "failed": 1}


def test_build_next_batch_song_uses_search_without_dash(seo_db, monkeypatch):
    seo_pages.enqueue_song("Test Sarki Ham Sorgu")
    called = {}

    def _search(q):
        called["query"] = q
        return _fake_deezer_track()

    monkeypatch.setattr(seo_pages.deezer, "search", _search)
    monkeypatch.setattr(seo_pages, "_deezer_preview_url", lambda tid: None)
    monkeypatch.setattr(seo_pages.audit, "run_audit", lambda q: _fake_audit_result(score=60))

    result = seo_pages.build_next_batch()
    assert result["built"] == 1
    assert called["query"] == "Test Sarki Ham Sorgu"


# --- build_next_batch: 'playlist' --------------------------------------------

def test_build_next_batch_playlist_happy_path(seo_db, monkeypatch):
    url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
    seo_pages.enqueue_playlist(url)
    monkeypatch.setattr(
        seo_pages.fraud_forensics, "analyze_playlist",
        lambda ref, **kw: _fake_fraud_report(),
    )

    result = seo_pages.build_next_batch()
    assert result == {"processed": 1, "built": 1, "thin": 0, "failed": 0}

    page = seo_pages.get_playlist_page("37i9dQZF1DXcBWIGoYBM5M")
    assert page is not None
    assert page["fraud_score"] == 10.0
    assert page["verdict"] == "guvenli"
    assert page["data_json"]["report_token"] == "FRAUD-TEST"


def test_build_next_batch_playlist_thin_when_spotify_unavailable(seo_db, monkeypatch):
    url = "https://open.spotify.com/playlist/deadbeef"
    seo_pages.enqueue_playlist(url)
    monkeypatch.setattr(
        seo_pages.fraud_forensics, "analyze_playlist",
        lambda ref, **kw: _fake_fraud_report(
            verdict="veri_yetersiz", informative_signals=0,
        ),
    )

    result = seo_pages.build_next_batch()
    assert result == {"processed": 1, "built": 0, "thin": 1, "failed": 0}
    assert seo_pages.get_playlist_page("deadbeef") is None


def test_build_next_batch_playlist_failed_on_exception(seo_db, monkeypatch):
    url = "https://open.spotify.com/playlist/patlayan"
    seo_pages.enqueue_playlist(url)

    def _boom(ref, **kw):
        raise RuntimeError("spotify down")

    monkeypatch.setattr(seo_pages.fraud_forensics, "analyze_playlist", _boom)

    result = seo_pages.build_next_batch()
    assert result == {"processed": 1, "built": 0, "thin": 0, "failed": 1}


def test_build_next_batch_playlist_falls_back_to_url_when_no_id(seo_db, monkeypatch):
    # parse_playlist_id eslesmezse (Spotify disi bir URL) ham ref
    # platform_playlist_id olarak kullanilmali.
    url = "https://example.com/not-a-spotify-playlist"
    seo_pages.enqueue_playlist(url)
    monkeypatch.setattr(
        seo_pages.fraud_forensics, "analyze_playlist",
        lambda ref, **kw: _fake_fraud_report(),
    )

    result = seo_pages.build_next_batch()
    assert result["built"] == 1
    assert seo_pages.get_playlist_page(url) is not None


# --- karisik (mixed) turde kuyruk --------------------------------------------

def test_build_next_batch_mixed_types_processed_by_priority(seo_db, monkeypatch):
    seo_pages.enqueue_artist("Karma Sanatci", priority=10)
    seo_pages.enqueue_song("Karma Sanatci - Karma Sarki", priority=20)
    seo_pages.enqueue_playlist("https://open.spotify.com/playlist/karma123", priority=30)

    monkeypatch.setattr(
        seo_pages.audit, "run_audit",
        lambda q: SimpleNamespace(
            resolved_artist="Karma Sanatci", resolved_title="Karma Sarki", score=80,
            sources=[SimpleNamespace(found=True), SimpleNamespace(found=True)],
            findings=[], to_dict=lambda: {"resolved_artist": "Karma Sanatci", "score": 80},
        ),
    )
    monkeypatch.setattr(seo_pages.deezer, "lookup", lambda a, t: _fake_deezer_track())
    monkeypatch.setattr(seo_pages, "_deezer_preview_url", lambda tid: None)
    monkeypatch.setattr(
        seo_pages.fraud_forensics, "analyze_playlist",
        lambda ref, **kw: _fake_fraud_report(),
    )

    result = seo_pages.build_next_batch()
    assert result == {"processed": 3, "built": 3, "thin": 0, "failed": 0}
    assert seo_pages.get_artist_page("karma-sanatci") is not None
    assert seo_pages.get_song_page("USRC00001") is not None
    assert seo_pages.get_playlist_page("karma123") is not None


# --- catalog_scout: seed_songs_from_starter -----------------------------------

def test_seed_songs_from_starter_enqueues(seo_db, monkeypatch):
    monkeypatch.setattr(
        catalog_scout, "_deezer_top_tracks",
        lambda artist_name, limit: [f"{artist_name} - Song {i}" for i in range(limit)],
    )
    monkeypatch.setattr(catalog_scout, "STARTER_TOP_ARTISTS", ["Sanatci A", "Sanatci B"])

    result = catalog_scout.seed_songs_from_starter(per_artist=2, base_priority=100)
    assert result == {"queued": 4}

    conn = seo_pages._connect()
    try:
        rows = conn.execute(
            "SELECT ref, priority FROM build_queue WHERE page_type = 'song' "
            "ORDER BY priority DESC"
        ).fetchall()
    finally:
        conn.close()
    refs = [r["ref"] for r in rows]
    assert refs == ["Sanatci A - Song 0", "Sanatci A - Song 1", "Sanatci B - Song 0", "Sanatci B - Song 1"]
    assert [r["priority"] for r in rows] == [100, 99, 98, 97]


def test_seed_songs_from_starter_skips_artist_on_deezer_failure(seo_db, monkeypatch):
    def _flaky(artist_name, limit):
        if artist_name == "Sanatci A":
            raise RuntimeError("deezer down")
        return [f"{artist_name} - Song"]

    monkeypatch.setattr(catalog_scout, "_deezer_top_tracks", _flaky)
    monkeypatch.setattr(catalog_scout, "STARTER_TOP_ARTISTS", ["Sanatci A", "Sanatci B"])

    result = catalog_scout.seed_songs_from_starter(per_artist=1)
    assert result == {"queued": 1}


def test_seed_songs_from_starter_invalid_per_artist_raises(seo_db):
    with pytest.raises(ValueError):
        catalog_scout.seed_songs_from_starter(per_artist=0)


# --- catalog_scout: seed_playlists_from_search --------------------------------

def test_seed_playlists_from_search_enqueues(seo_db, monkeypatch):
    monkeypatch.setattr(catalog_scout.spotify_client, "available", lambda: True)
    monkeypatch.setattr(
        catalog_scout, "_spotify_search_playlist_urls",
        lambda query, limit: [
            f"https://open.spotify.com/playlist/{query.replace(' ', '')}-{i}"
            for i in range(limit)
        ],
    )

    result = catalog_scout.seed_playlists_from_search(
        queries=["pop", "chill"], limit_per=2, base_priority=50,
    )
    assert result == {"queued": 4}

    conn = seo_pages._connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM build_queue WHERE page_type = 'playlist'"
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 4


def test_seed_playlists_from_search_skips_when_spotify_unavailable(seo_db, monkeypatch):
    monkeypatch.setattr(catalog_scout.spotify_client, "available", lambda: False)

    result = catalog_scout.seed_playlists_from_search(queries=["pop"])
    assert result == {"queued": 0}

    conn = seo_pages._connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM build_queue WHERE page_type = 'playlist'"
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 0


def test_seed_playlists_from_search_empty_queries_raises(seo_db):
    with pytest.raises(ValueError):
        catalog_scout.seed_playlists_from_search(queries=[])


def test_seed_playlists_from_search_query_failure_does_not_abort(seo_db, monkeypatch):
    monkeypatch.setattr(catalog_scout.spotify_client, "available", lambda: True)

    def _flaky(query, limit):
        if query == "pop":
            raise RuntimeError("spotify down")
        return [f"https://open.spotify.com/playlist/{query}"]

    monkeypatch.setattr(catalog_scout, "_spotify_search_playlist_urls", _flaky)

    result = catalog_scout.seed_playlists_from_search(queries=["pop", "chill"])
    assert result == {"queued": 1}
