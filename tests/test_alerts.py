"""Retention alert motoru testleri: 4 builder'in saf sekil kontrolu, run_daily
orkestrasyonu (cover_candidates + fraud_reports taramasi), idempotentlik
(alert_log ile ayni olay iki kez uretilmez), bos DB'de cokme olmamasi,
pending_alerts/alert_history sorgulari, growth.add_notification push'u.
Network YOK, DB tmp_path'e izole.
"""
from __future__ import annotations

import pytest

from marketplace import alerts, cover_hunter, db, fraud_forensics, growth


@pytest.fixture()
def alerts_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


def _seed_cover_hunt(user_id: int, query: str = "Test Sarki") -> int:
    conn = cover_hunter._connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO cover_hunts "
                "(created_at, user_id, original_query, original_audio_profile, "
                " status, report_token) "
                "VALUES (?, ?, ?, NULL, 'open', ?)",
                (db.now_iso(), user_id, query, f"HUNT-{user_id}-{query}"),
            )
            return int(cur.lastrowid)
    finally:
        conn.close()


def _add_pending_candidate(hunt_id: int, url: str) -> None:
    conn = cover_hunter._connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO cover_candidates "
                "(created_at, hunt_id, source, url, title, channel, "
                " similarity_score, match_reasons, status) "
                "VALUES (?, ?, 'youtube', ?, 'Baslik', 'Kanal', 0.9, '[]', 'pending')",
                (db.now_iso(), hunt_id, url),
            )
    finally:
        conn.close()


def _seed_risky_fraud_report(user_id: int, url: str) -> dict:
    """analyze_playlist'i yuksek riskli cikacak veriyle cagirir (bkz
    test_fraud_forensics.test_analyze_playlist_high_risk_with_fraud_signals)."""
    fraud_forensics.save_snapshot(url, 1000, 3, ["a", "b", "c"])
    fraud_forensics.save_snapshot(url, 5000, 3, ["x", "y", "z"])
    return fraud_forensics.analyze_playlist(
        url,
        {"id": user_id},
        geo_distribution={"XX": 0.98, "TR": 0.02},
        profiles=[{"energy": 0.95}],
        playlist_title="Sakin Uyku Muzikleri",
        track_scores=[5, 10, 8],
    )


# --- Builder'lar (saf, network yok) ------------------------------------------

def test_build_cover_alert_shape():
    alert = alerts.build_cover_alert(7, "42", 3)
    assert alert == {
        "user_id": 7,
        "alert_type": "cover",
        "ref": "42:3",
        "message": "Şarkının izinsiz cover'ı bulundu: 3 yeni aday",
    }


def test_build_fraud_alert_default_ref_and_override():
    default_alert = alerts.build_fraud_alert(3, "Todays Top Hits", "riskli")
    assert default_alert["user_id"] == 3
    assert default_alert["alert_type"] == "fraud"
    assert default_alert["ref"] == "Todays Top Hits:riskli"
    assert "Todays Top Hits" in default_alert["message"]
    assert "riskli" in default_alert["message"]

    overridden = alerts.build_fraud_alert(3, "Todays Top Hits", "riskli", ref="99")
    assert overridden["ref"] == "99"


def test_build_score_alert_shape():
    alert = alerts.build_score_alert(9, "Artist - Song", 45.0, 52.0)
    assert alert["user_id"] == 9
    assert alert["alert_type"] == "score"
    assert alert["ref"] == "Artist - Song:45->52"
    assert "45" in alert["message"] and "52" in alert["message"]


def test_build_competitor_alert_shape():
    alert = alerts.build_competitor_alert(4, "Rakip Sanatci", 20.0)
    assert alert["user_id"] == 4
    assert alert["alert_type"] == "competitor"
    assert alert["ref"] == "Rakip Sanatci:20"
    assert "Rakip Sanatci" in alert["message"]
    assert "20" in alert["message"]


# --- run_daily: bos DB -------------------------------------------------------

def test_run_daily_empty_db_returns_zero_no_crash(alerts_db):
    result = alerts.run_daily()
    assert result == {"generated": 0, "by_type": {}}


# --- run_daily: cover_candidates taramasi ------------------------------------

def test_run_daily_generates_cover_alert_for_pending_candidates(alerts_db):
    hunt_id = _seed_cover_hunt(user_id=11)
    _add_pending_candidate(hunt_id, "https://youtube.com/watch?v=a")
    _add_pending_candidate(hunt_id, "https://youtube.com/watch?v=b")

    result = alerts.run_daily()

    assert result["generated"] == 1
    assert result["by_type"] == {"cover": 1}
    history = alerts.alert_history(11)
    assert len(history) == 1
    assert history[0]["alert_type"] == "cover"
    assert "2 yeni aday" in history[0]["message"]


def test_run_daily_cover_alerts_idempotent_on_second_run(alerts_db):
    hunt_id = _seed_cover_hunt(user_id=12)
    _add_pending_candidate(hunt_id, "https://youtube.com/watch?v=a")

    first = alerts.run_daily()
    second = alerts.run_daily()

    assert first["generated"] == 1
    assert second == {"generated": 0, "by_type": {}}
    assert len(alerts.alert_history(12)) == 1


def test_run_daily_cover_alert_fires_again_when_pending_count_grows(alerts_db):
    hunt_id = _seed_cover_hunt(user_id=13)
    _add_pending_candidate(hunt_id, "https://youtube.com/watch?v=a")
    first = alerts.run_daily()
    assert first["generated"] == 1

    _add_pending_candidate(hunt_id, "https://youtube.com/watch?v=b")
    second = alerts.run_daily()

    assert second["generated"] == 1
    assert second["by_type"] == {"cover": 1}
    history = alerts.alert_history(13)
    assert len(history) == 2  # eski (1 aday) + yeni (2 aday) alert, ikisi de kalici


def test_run_daily_groups_cover_alerts_by_hunt(alerts_db):
    hunt_a = _seed_cover_hunt(user_id=21, query="Sarki A")
    hunt_b = _seed_cover_hunt(user_id=21, query="Sarki B")
    _add_pending_candidate(hunt_a, "https://youtube.com/watch?v=a1")
    _add_pending_candidate(hunt_b, "https://youtube.com/watch?v=b1")

    result = alerts.run_daily()

    assert result["by_type"] == {"cover": 2}
    assert len(alerts.alert_history(21)) == 2


# --- run_daily: fraud_reports taramasi ---------------------------------------

def test_run_daily_generates_fraud_alert_for_risky_verdict(alerts_db):
    report = _seed_risky_fraud_report(user_id=31, url="https://deezer.com/playlist/1")
    assert report["verdict"] in alerts.RISKY_FRAUD_VERDICTS

    result = alerts.run_daily()

    assert result["by_type"].get("fraud") == 1
    history = alerts.alert_history(31)
    assert len(history) == 1
    assert history[0]["alert_type"] == "fraud"


def test_run_daily_ignores_safe_verdict_reports(alerts_db):
    url = "https://deezer.com/playlist/2"
    fraud_forensics.save_snapshot(url, 1000, 3, ["a", "b", "c"])
    fraud_forensics.save_snapshot(url, 1010, 3, ["a", "b", "c"])
    report = fraud_forensics.analyze_playlist(
        url,
        {"id": 32},
        geo_distribution={"TR": 0.3, "US": 0.3, "DE": 0.4},
        profiles=[{"energy": 0.3}],
        playlist_title="Sakin Aksam",
        track_scores=[80, 85, 90],
    )
    assert report["verdict"] == "guvenli"

    result = alerts.run_daily()

    assert result["by_type"].get("fraud") is None
    assert alerts.alert_history(32) == []


def test_run_daily_fraud_alerts_idempotent_on_second_run(alerts_db):
    _seed_risky_fraud_report(user_id=33, url="https://deezer.com/playlist/3")

    first = alerts.run_daily()
    second = alerts.run_daily()

    assert first["by_type"].get("fraud") == 1
    assert second == {"generated": 0, "by_type": {}}


def test_run_daily_survives_missing_user_reports(alerts_db):
    """user_id olmayan (anonim) rapor run_daily'yi cokertmemeli, sadece atlanir."""
    fraud_forensics.analyze_playlist(
        "https://deezer.com/playlist/anon",
        None,
        geo_distribution={"XX": 0.98, "TR": 0.02},
        profiles=[{"energy": 0.95}],
        playlist_title="Sakin Anonim",
        track_scores=[5, 10, 8],
    )
    result = alerts.run_daily()
    assert result == {"generated": 0, "by_type": {}}


# --- growth notifications entegrasyonu (guarded push) -----------------------

def test_record_alert_pushes_notification_through_growth(alerts_db):
    hunt_id = _seed_cover_hunt(user_id=41)
    _add_pending_candidate(hunt_id, "https://youtube.com/watch?v=g1")

    alerts.run_daily()

    notes = growth.notifications_for(41)
    assert len(notes) == 1
    assert notes[0]["kind"] == "cover"
    assert "yeni aday" in notes[0]["message"]
    # alert_log'da da 'sent' 1 olarak isaretlenmis olmali
    history = alerts.alert_history(41)
    assert history[0]["sent"] == 1


def test_record_alert_survives_growth_failure(alerts_db, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("growth API cokmus")

    monkeypatch.setattr(growth, "add_notification", _boom)
    hunt_id = _seed_cover_hunt(user_id=42)
    _add_pending_candidate(hunt_id, "https://youtube.com/watch?v=g2")

    result = alerts.run_daily()

    assert result["generated"] == 1  # alert_log'a yine de yazildi
    history = alerts.alert_history(42)
    assert history[0]["sent"] == 0  # ama growth push'u basarisiz kaldi


# --- pending_alerts / alert_history helpers ----------------------------------

def test_pending_alerts_only_returns_unsent(alerts_db, monkeypatch):
    monkeypatch.setattr(growth, "add_notification", lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))
    hunt_id = _seed_cover_hunt(user_id=51)
    _add_pending_candidate(hunt_id, "https://youtube.com/watch?v=p1")
    alerts.run_daily()

    pending = alerts.pending_alerts(51)
    assert len(pending) == 1
    assert pending[0]["sent"] == 0


def test_alert_history_respects_limit(alerts_db):
    for i in range(3):
        hunt_id = _seed_cover_hunt(user_id=61, query=f"Sarki {i}")
        _add_pending_candidate(hunt_id, f"https://youtube.com/watch?v=h{i}")
    alerts.run_daily()

    full_history = alerts.alert_history(61)
    limited = alerts.alert_history(61, limit=2)
    assert len(full_history) == 3
    assert len(limited) == 2


def test_pending_alerts_empty_for_unknown_user(alerts_db):
    assert alerts.pending_alerts(999999) == []
    assert alerts.alert_history(999999) == []


# --- import sanity ------------------------------------------------------------

def test_module_imports_without_network():
    import marketplace.alerts  # noqa: F401
