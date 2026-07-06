"""Gelir katmani testleri: fiyatlandirma, garanti, referans, dinleme kapisi,
Deezer sahiplik guvenligi, payout, pro tahsis. Network YOK.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from marketplace import accounts, db, growth, premium, pricing, service
from musical_seo.models import TrackInfo

FEEDBACK = "x" * 150


@pytest.fixture()
def rev_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    monkeypatch.setattr(pricing, "LISTEN_GATE_SECONDS", 0)
    monkeypatch.setattr(
        service.deezer, "lookup",
        lambda artist, title: TrackInfo(
            source="deezer", found=True, title=title, artist=artist,
            url="https://www.deezer.com/track/1",
        ),
    )
    return db.add_curator(
        name="Kucuk Kurator", email="k@test.com", playlist_id="111",
        playlist_title="Kucuk Liste", playlist_url="https://deezer.com/playlist/111",
        fans=100, track_count=30, diversity=0.5, quality_score=30.0,
        status="approved", quality_passed=True,
    )  # bronze -> 1 kredi


# --- Saf fiyatlandirma -------------------------------------------------------

def test_curator_tier_ladder():
    assert pricing.curator_tier(10.0, 100) == "bronze"
    assert pricing.curator_tier(45.0, 100) == "silver"      # kalite ile
    assert pricing.curator_tier(10.0, 2000) == "silver"     # fan ile
    assert pricing.curator_tier(70.0, 5000) == "gold"
    # platinum kanitlanmis performans ister; veri yoksa gold'da kalir
    assert pricing.curator_tier(70.0, 5000, None, None) == "gold"
    assert pricing.curator_tier(70.0, 5000, 90, 30) == "platinum"
    assert pricing.curator_tier(70.0, 5000, 70, 30) == "gold"  # dusuk yanit orani


def test_submission_cost_rules():
    assert pricing.submission_cost("bronze") == 1
    assert pricing.submission_cost("platinum") == 4
    assert pricing.submission_cost("bronze", "radyo") == pricing.PRO_TYPE_COST
    # Artist Pro indirimi: 1 kredi, taban 1'in altina inmez
    assert pricing.submission_cost("gold", pro_artist=True) == 2
    assert pricing.submission_cost("bronze", pro_artist=True) == 1


def test_total_cost_and_refund():
    # bronze + garanti: 1 + max(1, ceil(0.5)) = 2; SLA kacarsa 2x = 4 iade
    total = pricing.total_submission_cost(1, guaranteed=True)
    assert total == 2
    assert pricing.refund_amount(total, guaranteed=True) == 4
    assert pricing.refund_amount(3, guaranteed=False) == 3
    # rush eklentisi
    assert pricing.total_submission_cost(1, priority=True) == 2
    assert pricing.sla_hours(priority=True) == pricing.PRIORITY_SLA_HOURS


# --- Deezer sahiplik guvenligi ---------------------------------------------------

def test_deezer_apply_no_longer_auto_approves(tmp_path, monkeypatch):
    """GUVENLIK: kalite esigini gecen Deezer basvurusu bile sahiplik
    dogrulamasi olmadan approved OLMAZ."""
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    monkeypatch.setattr(
        service, "inspect_playlist",
        lambda pid: {
            "playlist_id": pid, "title": "Populer Liste",
            "url": f"https://deezer.com/playlist/{pid}",
            "fans": 9000, "track_count": 80, "diversity": 0.6,
            "owner_name": "Baskasi", "tracks": [],
        },
    )
    curator = service.apply_curator("Ben", "ben@x.com", "12345")
    assert curator["status"] == "pending"          # otomatik onay YOK
    assert curator["quality_passed"] == 1          # kalite gecti ama yetmez

    # Sahiplik kaniti gelince otomatik onay
    code = service.start_ownership_verification(curator["id"])
    monkeypatch.setattr(service, "_playlist_description", lambda pid: f"abc {code}")
    approved = service.check_ownership(curator["id"])
    assert approved["status"] == "approved"
    assert approved["ownership_verified"] == 1


def test_low_quality_ownership_does_not_auto_approve(tmp_path, monkeypatch):
    """Sahiplik kanitlansa bile kalite esigi gecilmediyse admin onayi gerekir."""
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    curator_id = db.add_curator(
        name="Zayif Liste", email="z@x.com", playlist_id="222",
        playlist_title="Zayif", playlist_url="", fans=0, track_count=5,
        diversity=0.1, quality_score=5.0, status="pending", quality_passed=False,
    )
    code = service.start_ownership_verification(curator_id)
    monkeypatch.setattr(service, "_playlist_description", lambda pid: code)
    result = service.check_ownership(curator_id)
    assert result["ownership_verified"] == 1
    assert result["status"] == "pending"           # hala admin bekliyor


# --- Garanti + rush gonderim -------------------------------------------------------

def test_guaranteed_submission_double_refund(rev_db):
    artist = accounts.register("a@test.com", "parola123", "Sanatci", "artist")
    accounts.grant_credits(artist["id"], 2)
    sub = service.create_submission(
        "Sanatci", "Sarki", rev_db, artist_user_id=artist["id"], guaranteed=True
    )
    assert sub["cost_credits"] == 2                # bronze 1 + garanti 1
    assert accounts.get_user(artist["id"])["credits"] == 0

    conn = sqlite3.connect(db._DB_PATH)
    conn.execute(
        "UPDATE submissions SET deadline = '2000-01-01T00:00:00+00:00' WHERE id = ?",
        (sub["id"],),
    )
    conn.commit()
    conn.close()
    result = service.expire_and_refund()
    assert result["refunded"] == 1
    # 2x iade: 2 odedi, 4 geri aldi (garanti sozunun tamami)
    assert accounts.get_user(artist["id"])["credits"] == 4
    # idempotent
    assert service.expire_and_refund()["refunded"] == 0


def test_priority_submission_shorter_sla_and_bonus(rev_db):
    artist = accounts.register("a2@test.com", "parola123", "Sanatci", "artist")
    curator_user = accounts.register(
        "k2@test.com", "parola123", "Kurator", "curator", curator_id=rev_db
    )
    accounts.grant_credits(artist["id"], 2)
    sub = service.create_submission(
        "Sanatci", "Sarki", rev_db, artist_user_id=artist["id"], priority=True
    )
    assert sub["cost_credits"] == 2                # bronze 1 + rush 1
    assert sub["priority"] == 1
    # 48 saatlik SLA
    created = datetime.fromisoformat(sub["created_at"])
    deadline = datetime.fromisoformat(sub["deadline"])
    assert (deadline - created) == timedelta(hours=pricing.PRIORITY_SLA_HOURS)

    service.respond(sub["id"], "rejected", FEEDBACK)
    earnings = accounts.earnings_for(curator_user["id"])
    assert earnings["total_usd"] == accounts.FEEDBACK_EARNING_USD + pricing.PRIORITY_BONUS_USD


# --- Dinleme kapisi -----------------------------------------------------------------

def test_listen_gate_blocks_instant_response(rev_db, monkeypatch):
    monkeypatch.setattr(pricing, "LISTEN_GATE_SECONDS", 90)
    artist = accounts.register("a3@test.com", "parola123", "Sanatci", "artist")
    accounts.grant_credits(artist["id"], 1)
    sub = service.create_submission(
        "Sanatci", "Sarki", rev_db, artist_user_id=artist["id"]
    )
    # Acilmadan yanit yok
    with pytest.raises(ValueError, match="dinle"):
        service.respond(sub["id"], "rejected", FEEDBACK)
    # Acilir acilmaz yanit da yok (90 sn gecmedi)
    service.open_submission(sub["id"])
    with pytest.raises(ValueError, match="saniye"):
        service.respond(sub["id"], "rejected", FEEDBACK)
    # Acilisi 2 dk geriye cek -> yanit kabul
    conn = sqlite3.connect(db._DB_PATH)
    past = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    conn.execute(
        "UPDATE submissions SET opened_at = ? WHERE id = ?", (past, sub["id"])
    )
    conn.commit()
    conn.close()
    updated = service.respond(sub["id"], "rejected", FEEDBACK)
    assert updated["status"] == "rejected"


# --- Referans ------------------------------------------------------------------------

def test_referral_bonus_once_on_first_submission(rev_db):
    referrer = accounts.register("ref@test.com", "parola123", "Davet Eden", "artist")
    code = growth.referral_code_for(referrer["id"])
    invited = accounts.register(
        "yeni@test.com", "parola123", "Yeni", "artist", referral_code=code
    )
    accounts.grant_credits(invited["id"], 5)
    before_ref = accounts.get_user(referrer["id"])["credits"]

    service.create_submission(
        "Sanatci", "Sarki", rev_db, artist_user_id=invited["id"]
    )
    # Iki taraf da +1
    assert accounts.get_user(referrer["id"])["credits"] == before_ref + 1
    invited_after = accounts.get_user(invited["id"])["credits"]

    # Ikinci gonderimde tekrar bonus YOK
    service.create_submission(
        "Sanatci", "Sarki 2", rev_db, artist_user_id=invited["id"]
    )
    assert accounts.get_user(referrer["id"])["credits"] == before_ref + 1
    assert accounts.get_user(invited["id"])["credits"] == invited_after - 1


def test_invalid_referral_code_rejected(rev_db):
    with pytest.raises(ValueError, match="referans"):
        accounts.register(
            "x@test.com", "parola123", "X", "artist", referral_code="REF-YOK"
        )


# --- Payout ---------------------------------------------------------------------------

def test_payout_threshold_and_instant_fee(rev_db, monkeypatch):
    curator_user = accounts.register(
        "k3@test.com", "parola123", "Kurator", "curator", curator_id=rev_db
    )
    # $5 tahakkuk (esik alti)
    for sid in range(1, 6):
        accounts.accrue_earning(curator_user["id"], 1000 + sid)
    with pytest.raises(ValueError, match="esigi"):
        premium.request_payout(curator_user, instant=False)

    payout = premium.request_payout(curator_user, instant=True)
    assert payout["instant"] == 1
    assert payout["fee_usd"] == pricing.instant_payout_fee(5.0)
    assert payout["amount_usd"] == round(5.0 - payout["fee_usd"], 2)
    # Tahakkuklar 'requested' oldu -> ikinci payout bos
    with pytest.raises(ValueError, match="tahakkuk"):
        premium.request_payout(curator_user, instant=True)

    paid = premium.mark_payout_paid(payout["id"])
    assert paid["status"] == "paid"
    assert accounts.earnings_for(curator_user["id"])["pending_usd"] == 0.0


# --- Artist Pro -----------------------------------------------------------------------

def test_pro_monthly_grant_idempotent(rev_db):
    artist = accounts.register("pro@test.com", "parola123", "Pro", "artist")
    until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    accounts.set_pro_until(artist["id"], until)
    assert accounts.is_pro(accounts.get_user(artist["id"]))

    assert premium.grant_pro_monthly() == 1
    assert accounts.get_user(artist["id"])["credits"] == pricing.PRO_MONTHLY_CREDITS
    # Ayni ay icinde ikinci tahsis yok
    assert premium.grant_pro_monthly() == 0
    assert accounts.get_user(artist["id"])["credits"] == pricing.PRO_MONTHLY_CREDITS


# --- Public karne + lig -----------------------------------------------------------------

def test_public_report_locked_and_leaderboard_opt_in(rev_db):
    artist = accounts.register("lig@test.com", "parola123", "Ligci", "artist")
    token = growth.create_public_report(
        artist["id"], "Ligci", "Hit", 78.5,
        {"finding_counts": {"warn": 2}, "subscores": {"metadata": 80}},
    )
    report = growth.get_public_report(token)
    assert report["score"] == 78.5
    assert report["locked"] is True
    assert "findings" not in report            # detay sizmaz

    # Opt-in olmadan ligde gorunmez
    assert growth.leaderboard() == []
    accounts.set_leaderboard_opt_in(artist["id"], True)
    board = growth.leaderboard()
    assert len(board) == 1 and board[0]["artist"] == "Ligci"
