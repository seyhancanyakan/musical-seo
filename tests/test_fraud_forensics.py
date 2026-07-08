"""Sahte Playlist Dedektoru testleri: 5 sinyalin normal/anomali davranisi,
agirlikli risk skoru siniri (0..100), verdict esikleri, analyze_playlist
entegrasyonu (veri enjeksiyonuyla, network YOK) + rapor kalicilik/gecmis.
"""
from __future__ import annotations

import pytest

from marketplace import db, fraud_forensics


@pytest.fixture()
def fraud_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


# --- signal_follower_anomaly --------------------------------------------------

def test_follower_anomaly_low_for_organic_growth(fraud_db):
    snapshots = [
        {"follower_count": 1000},
        {"follower_count": 1050},
        {"follower_count": 1100},
    ]
    result = fraud_forensics.signal_follower_anomaly("https://x", snapshots=snapshots)
    assert result["score"] < 0.1
    assert "detail" in result and "evidence" in result


def test_follower_anomaly_high_for_sudden_jump(fraud_db):
    snapshots = [
        {"follower_count": 1000},
        {"follower_count": 5000},  # %400 sicrama
    ]
    result = fraud_forensics.signal_follower_anomaly("https://x", snapshots=snapshots)
    assert result["score"] == 1.0


def test_follower_anomaly_neutral_without_data(fraud_db):
    result = fraud_forensics.signal_follower_anomaly("https://x", snapshots=[])
    assert result["score"] == 0.5
    assert "Yetersiz" in result["detail"]


# --- signal_track_churn -------------------------------------------------------

def test_track_churn_low_for_stable_playlist(fraud_db):
    snapshots = [
        {"track_ids": ["a", "b", "c", "d"]},
        {"track_ids": ["a", "b", "c", "e"]},  # diff={d,e}, union=5 -> 2/5
    ]
    result = fraud_forensics.signal_track_churn("https://x", snapshots=snapshots)
    assert result["score"] == pytest.approx(0.4, abs=0.01)


def test_track_churn_high_for_full_rotation(fraud_db):
    snapshots = [
        {"track_ids": ["a", "b", "c"]},
        {"track_ids": ["x", "y", "z"]},  # tamamen farkli
    ]
    result = fraud_forensics.signal_track_churn("https://x", snapshots=snapshots)
    assert result["score"] == 1.0


def test_track_churn_neutral_without_data(fraud_db):
    result = fraud_forensics.signal_track_churn("https://x", snapshots=[])
    assert result["score"] == 0.5


# --- signal_geo_cluster -------------------------------------------------------

def test_geo_cluster_low_for_diverse_distribution(fraud_db):
    dist = {"TR": 0.3, "US": 0.3, "DE": 0.2, "FR": 0.2}
    result = fraud_forensics.signal_geo_cluster("https://x", geo_distribution=dist)
    assert result["score"] == 0.0


def test_geo_cluster_high_for_concentrated_distribution(fraud_db):
    dist = {"XX": 0.95, "TR": 0.05}
    result = fraud_forensics.signal_geo_cluster("https://x", geo_distribution=dist)
    assert result["score"] > 0.8


def test_geo_cluster_neutral_without_data(fraud_db):
    result = fraud_forensics.signal_geo_cluster("https://x", geo_distribution=None)
    assert result["score"] == 0.5


# --- signal_audio_label_mismatch ---------------------------------------------

def test_audio_mismatch_high_when_calm_title_but_energetic_tracks(fraud_db):
    profiles = [{"energy": 0.9}, {"energy": 0.85}]
    result = fraud_forensics.signal_audio_label_mismatch(
        "https://x", playlist_title="Sakin Aksam Muzikleri", profiles=profiles,
    )
    assert result["score"] > 0.5


def test_audio_mismatch_low_when_consistent(fraud_db):
    profiles = [{"energy": 0.2}, {"energy": 0.25}]
    result = fraud_forensics.signal_audio_label_mismatch(
        "https://x", playlist_title="Sakin Aksam Muzikleri", profiles=profiles,
    )
    assert result["score"] == 0.0


def test_audio_mismatch_neutral_without_profiles(fraud_db):
    result = fraud_forensics.signal_audio_label_mismatch(
        "https://x", playlist_title="Sakin Aksam Muzikleri", profiles=None,
    )
    assert result["score"] == 0.5


def test_audio_mismatch_neutral_without_mood_keyword(fraud_db):
    profiles = [{"energy": 0.9}]
    result = fraud_forensics.signal_audio_label_mismatch(
        "https://x", playlist_title="En Iyi Parcalar 2026", profiles=profiles,
    )
    assert result["score"] == 0.5


# --- signal_track_seo_poverty -------------------------------------------------

def test_seo_poverty_high_for_low_quality_tracks(fraud_db):
    result = fraud_forensics.signal_track_seo_poverty(
        "https://x", track_scores=[10, 15, 20, 5],
    )
    assert result["score"] == 1.0


def test_seo_poverty_low_for_high_quality_tracks(fraud_db):
    result = fraud_forensics.signal_track_seo_poverty(
        "https://x", track_scores=[80, 90, 75, 60],
    )
    assert result["score"] == 0.0


def test_seo_poverty_neutral_without_data(fraud_db):
    result = fraud_forensics.signal_track_seo_poverty("https://x", track_scores=None)
    assert result["score"] == 0.5


# --- weighted score bounds + verdict thresholds -------------------------------

def test_verdict_thresholds():
    assert fraud_forensics._verdict_for(0) == "guvenli"
    assert fraud_forensics._verdict_for(24.9) == "guvenli"
    assert fraud_forensics._verdict_for(25) == "riskli"
    assert fraud_forensics._verdict_for(49.9) == "riskli"
    assert fraud_forensics._verdict_for(50) == "cok_riskli"
    assert fraud_forensics._verdict_for(74.9) == "cok_riskli"
    assert fraud_forensics._verdict_for(75) == "sahte"
    assert fraud_forensics._verdict_for(100) == "sahte"


def test_signal_weights_sum_to_one():
    assert sum(fraud_forensics.SIGNAL_WEIGHTS.values()) == pytest.approx(1.0)


# --- analyze_playlist integration (veri enjeksiyonu, network YOK) ------------

def test_analyze_playlist_all_neutral_is_veri_yetersiz(fraud_db):
    report = fraud_forensics.analyze_playlist("https://deezer.com/playlist/1")
    # Her sinyal notr (0.5) -> toplam skor 50.0 AMA hicbir sinyal informatif
    # degil: "kanit yok" != "sahte", verdict 'veri_yetersiz' olmali (yanlislikla
    # "cok_riskli/para odeme" GOSTERMEMELI).
    assert report["total_risk_score"] == pytest.approx(50.0)
    assert report["verdict"] == "veri_yetersiz"
    assert "GUVENILIR DEGIL" in report["recommendation"]
    assert report["report_token"].startswith("FRAUD-")
    assert set(report["signals"].keys()) == set(fraud_forensics.SIGNAL_WEIGHTS.keys())


def test_analyze_playlist_low_risk_with_clean_data(fraud_db):
    url = "https://deezer.com/playlist/2"
    # follower_anomaly + track_churn de dusuk kalsin diye istikrarli snapshot'lar.
    fraud_forensics.save_snapshot(url, 1000, 3, ["a", "b", "c"])
    fraud_forensics.save_snapshot(url, 1010, 3, ["a", "b", "c"])
    report = fraud_forensics.analyze_playlist(
        url,
        geo_distribution={"TR": 0.3, "US": 0.3, "DE": 0.4},
        profiles=[{"energy": 0.3}],
        playlist_title="Sakin Aksam",
        track_scores=[80, 85, 90],
    )
    assert report["verdict"] == "guvenli"
    assert report["total_risk_score"] < 25


def test_analyze_playlist_high_risk_with_fraud_signals(fraud_db):
    url = "https://deezer.com/playlist/3"
    # Buyuk takipci sicramasi + tam parca rotasyonu.
    fraud_forensics.save_snapshot(url, 1000, 3, ["a", "b", "c"])
    fraud_forensics.save_snapshot(url, 5000, 3, ["x", "y", "z"])
    report = fraud_forensics.analyze_playlist(
        url,
        geo_distribution={"XX": 0.98, "TR": 0.02},
        profiles=[{"energy": 0.95}],
        playlist_title="Sakin Uyku Muzikleri",
        track_scores=[5, 10, 8],
    )
    assert report["verdict"] == "sahte"
    assert report["total_risk_score"] > 75


def test_analyze_playlist_empty_url_raises(fraud_db):
    with pytest.raises(ValueError, match="bos olamaz"):
        fraud_forensics.analyze_playlist("")


def test_analyze_playlist_persists_and_get_report_roundtrip(fraud_db):
    report = fraud_forensics.analyze_playlist("https://deezer.com/playlist/4")
    fetched = fraud_forensics.get_report(report["report_token"])
    assert fetched is not None
    assert fetched["playlist_url"] == "https://deezer.com/playlist/4"
    assert fetched["total_risk_score"] == report["total_risk_score"]
    assert fetched["signals"].keys() == report["signals"].keys()


def test_get_report_missing_token_returns_none(fraud_db):
    assert fraud_forensics.get_report("FRAUD-NOPE1") is None


def test_reports_for_user_lists_own_reports_only(fraud_db):
    user_a = {"id": 1}
    user_b = {"id": 2}
    fraud_forensics.analyze_playlist("https://deezer.com/playlist/a1", user_a)
    fraud_forensics.analyze_playlist("https://deezer.com/playlist/a2", user_a)
    fraud_forensics.analyze_playlist("https://deezer.com/playlist/b1", user_b)

    reports_a = fraud_forensics.reports_for_user(1)
    reports_b = fraud_forensics.reports_for_user(2)

    assert len(reports_a) == 2
    assert len(reports_b) == 1
    assert {r["playlist_url"] for r in reports_a} == {
        "https://deezer.com/playlist/a1", "https://deezer.com/playlist/a2",
    }


def test_analyze_playlist_without_user_has_no_user_id_in_history(fraud_db):
    fraud_forensics.analyze_playlist("https://deezer.com/playlist/anon")
    # Kullanicisiz analiz gecmiste hicbir kullaniciya ait olmamali
    assert fraud_forensics.reports_for_user(1) == []


# --- snapshot deposu -----------------------------------------------------------

def test_save_snapshot_and_fetch_roundtrip(fraud_db):
    fraud_forensics.save_snapshot("https://deezer.com/playlist/5", 1000, 20, ["a", "b"])
    fraud_forensics.save_snapshot("https://deezer.com/playlist/5", 1010, 20, ["a", "c"])
    snapshots = fraud_forensics._fetch_snapshots("https://deezer.com/playlist/5")
    assert len(snapshots) == 2
    assert snapshots[0]["follower_count"] == 1000
    assert snapshots[1]["track_ids"] == ["a", "c"]


def test_analyze_playlist_uses_saved_snapshots_when_no_override(fraud_db):
    url = "https://deezer.com/playlist/6"
    fraud_forensics.save_snapshot(url, 1000, 10, ["a", "b", "c"])
    fraud_forensics.save_snapshot(url, 6000, 10, ["x", "y", "z"])  # buyuk sicrama + tam churn

    report = fraud_forensics.analyze_playlist(url)
    assert report["signals"]["follower_anomaly"]["score"] == 1.0
    assert report["signals"]["track_churn"]["score"] == 1.0
