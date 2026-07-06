"""Label/A&R B2B erisimi testleri: basvuru, onay, token guvenligi, gizlilik
(opt-in filtresi) ve skor deltasi. Network YOK.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from marketplace import accounts, db, labels

FEEDBACK = "x" * 150


@pytest.fixture()
def lbl_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    return tmp_path


def _insert_report(user_id: int, artist: str, score: float, created_at: str) -> None:
    conn = sqlite3.connect(db._DB_PATH)
    conn.execute(
        "INSERT INTO public_reports "
        "(created_at, token, user_id, artist, title, score, summary_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (created_at, f"KRN-{user_id}-{created_at}", user_id, artist, "Sarki",
         score, json.dumps({})),
    )
    conn.commit()
    conn.close()


def _insert_submission(user_id: int, curator_id: int, status: str,
                       verified: bool = False) -> None:
    conn = sqlite3.connect(db._DB_PATH)
    conn.execute(
        "INSERT INTO submissions "
        "(created_at, artist, title, track_url, curator_id, message, status, "
        " deadline, artist_user_id, placement_verified) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (db.now_iso(), "Sanatci", "Sarki", None, curator_id, "msg", status,
         db.now_iso(), user_id, int(verified)),
    )
    conn.commit()
    conn.close()


# --- Basvuru -----------------------------------------------------------------

def test_apply_label_success(lbl_db):
    lead = labels.apply_label("ABC Label", "Ayse Yilmaz", "ayse@abclabel.com", "Ilgi alani: pop")
    assert lead["status"] == "pending"
    assert lead["company"] == "ABC Label"
    assert lead["email"] == "ayse@abclabel.com"


def test_apply_label_invalid_email_rejected(lbl_db):
    with pytest.raises(ValueError):
        labels.apply_label("ABC Label", "Ayse", "gecersiz-eposta", "")


def test_apply_label_duplicate_pending_rejected(lbl_db):
    labels.apply_label("ABC Label", "Ayse", "ayse@abclabel.com", "")
    with pytest.raises(ValueError, match="bekleyen"):
        labels.apply_label("ABC Label 2", "Baska Kisi", "ayse@abclabel.com", "")


def test_apply_label_allowed_after_rejection(lbl_db):
    lead = labels.apply_label("ABC Label", "Ayse", "ayse@abclabel.com", "")
    labels.reject_label(lead["id"])
    # Onceki basvuru artik pending degil -> yeni basvuru serbest
    second = labels.apply_label("ABC Label", "Ayse", "ayse@abclabel.com", "")
    assert second["status"] == "pending"


# --- Admin onay/red -----------------------------------------------------------

def test_approve_label_generates_token(lbl_db):
    lead = labels.apply_label("ABC Label", "Ayse", "ayse@abclabel.com", "")
    approved = labels.approve_label(lead["id"])
    assert approved["status"] == "approved"
    assert approved["access_token"].startswith("LBL-")
    expires = datetime.fromisoformat(approved["expires_at"])
    delta_days = (expires - datetime.now(timezone.utc)).days
    assert 28 <= delta_days <= 30

    listed = labels.admin_list(status="approved")
    assert len(listed) == 1 and listed[0]["id"] == lead["id"]


def test_reject_label(lbl_db):
    lead = labels.apply_label("ABC Label", "Ayse", "ayse@abclabel.com", "")
    rejected = labels.reject_label(lead["id"])
    assert rejected["status"] == "rejected"
    assert rejected["access_token"] is None


def test_approve_unknown_lead_raises(lbl_db):
    with pytest.raises(ValueError):
        labels.approve_label(999)


# --- Token dogrulama -----------------------------------------------------------

def test_invalid_token_raises(lbl_db):
    with pytest.raises(ValueError, match="gecersiz veya suresi dolmus"):
        labels._validate_token("LBL-YOK")


def test_expired_token_raises(lbl_db):
    lead = labels.apply_label("ABC Label", "Ayse", "ayse@abclabel.com", "")
    approved = labels.approve_label(lead["id"])
    conn = sqlite3.connect(db._DB_PATH)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conn.execute(
        "UPDATE label_leads SET expires_at = ? WHERE id = ?", (past, lead["id"])
    )
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="gecersiz veya suresi dolmus"):
        labels._validate_token(approved["access_token"])


def test_pending_lead_token_none_raises(lbl_db):
    labels.apply_label("ABC Label", "Ayse", "ayse@abclabel.com", "")
    with pytest.raises(ValueError, match="gecersiz veya suresi dolmus"):
        labels._validate_token("")


# --- Yukselen sanatcilar raporu (gizlilik + delta) -----------------------------

def test_rising_report_only_opt_in_and_delta_sorted(lbl_db):
    curator_id = db.add_curator(
        name="Liste", email="k@test.com", playlist_id="1",
        playlist_title="Liste", playlist_url="https://deezer.com/playlist/1",
        fans=100, track_count=30, diversity=0.5, quality_score=30.0,
        status="approved",
    )
    opt_in = accounts.register("optin@test.com", "parola123", "Opt Sanatci", "artist")
    opt_out = accounts.register("optout@test.com", "parola123", "Gizli Sanatci", "artist")
    accounts.set_leaderboard_opt_in(opt_in["id"], True)
    # opt_out opt-in yapilmadi (varsayilan kapali)

    old_ts = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    new_ts = datetime.now(timezone.utc).isoformat()
    _insert_report(opt_in["id"], "Opt Sanatci", 50.0, old_ts)
    _insert_report(opt_in["id"], "Opt Sanatci", 78.0, new_ts)
    _insert_report(opt_out["id"], "Gizli Sanatci", 10.0, old_ts)
    _insert_report(opt_out["id"], "Gizli Sanatci", 90.0, new_ts)

    _insert_submission(opt_in["id"], curator_id, "accepted", verified=True)
    _insert_submission(opt_in["id"], curator_id, "rejected")

    lead = labels.apply_label("ABC Label", "Ayse", "ayse@abclabel.com", "")
    approved = labels.approve_label(lead["id"])

    report = labels.rising_report(approved["access_token"])
    assert len(report) == 1                       # opt-out sizmadi
    entry = report[0]
    assert entry["artist_name"] == "Opt Sanatci"
    assert entry["latest_score"] == 78.0
    assert entry["score_delta"] == 28.0            # 78 - 50
    assert entry["accepted"] == 1
    assert entry["verified_placements"] == 1
    assert entry["accept_rate"] == 50.0            # 1 kabul / 2 yanit


def test_rising_report_no_history_before_window_gives_none_delta(lbl_db):
    accounts.register("k@test.com", "parola123", "Kurator", "curator")
    opt_in = accounts.register("solo@test.com", "parola123", "Tek Rapor", "artist")
    accounts.set_leaderboard_opt_in(opt_in["id"], True)
    _insert_report(opt_in["id"], "Tek Rapor", 60.0, datetime.now(timezone.utc).isoformat())

    lead = labels.apply_label("ABC Label", "Ayse", "ayse@abclabel.com", "")
    approved = labels.approve_label(lead["id"])
    report = labels.rising_report(approved["access_token"])
    assert len(report) == 1
    assert report[0]["score_delta"] is None
    assert report[0]["accept_rate"] is None


def test_rising_report_invalid_token_raises(lbl_db):
    with pytest.raises(ValueError, match="gecersiz veya suresi dolmus"):
        labels.rising_report("LBL-YOK")
