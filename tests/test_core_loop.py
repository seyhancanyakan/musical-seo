"""Cekirdek gelir dongusu — uctan uca, network YOK.

Dongu: sanatci kredi alir -> kurator secer -> gonderir (1 kredi duser) ->
kurator nitelikli geri bildirim verir -> $1 kazanir -> cevapsiz gonderimde
SLA dolunca kredi otomatik iade edilir.
"""
from __future__ import annotations

import sqlite3

import pytest

from marketplace import accounts, db, pricing, service
from musical_seo.models import TrackInfo

# Fixture kuratoru: quality 80 + 5000 fan (gecmis istatistik yok) -> GOLD
# kademe -> gonderim 3 kredi (reach-bazli fiyat).
GOLD_COST = pricing.TIER_COST["gold"]


@pytest.fixture()
def loop_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    # Dinleme kapisi testlerde kapali (kendi testi ayrica var)
    monkeypatch.setattr(pricing, "LISTEN_GATE_SECONDS", 0)
    # Deezer lookup'ini sahtele (network yok)
    monkeypatch.setattr(
        service.deezer, "lookup",
        lambda artist, title: TrackInfo(
            source="deezer", found=True, title=title, artist=artist,
            url="https://www.deezer.com/track/1",
        ),
    )
    curator_id = db.add_curator(
        name="Test Kurator", email="k@test.com", playlist_id="123",
        playlist_title="Test Liste", playlist_url="https://deezer.com/playlist/123",
        fans=5000, track_count=50, diversity=0.6, quality_score=80.0,
        status="approved", quality_passed=True,
    )
    return curator_id


def _make_users(curator_id):
    artist = accounts.register("artist@test.com", "parola123", "Sanatci", "artist")
    curator = accounts.register(
        "curator@test.com", "parola123", "Kurator", "curator", curator_id=curator_id
    )
    return artist, curator


def test_full_loop_qualified_feedback_earns(loop_db):
    curator_id = loop_db
    artist, curator = _make_users(curator_id)

    # Kredi yukle (pilot: manuel odeme sonrasi admin grant)
    accounts.grant_credits(artist["id"], 10, reason="purchase")

    # Gonderim: gold kurator -> GOLD_COST kredi duser
    sub = service.create_submission(
        "Sanatci", "Sarki", curator_id, artist_user_id=artist["id"]
    )
    assert accounts.get_user(artist["id"])["credits"] == 10 - GOLD_COST
    assert sub["cost_credits"] == GOLD_COST
    assert sub["artist_user_id"] == artist["id"]

    # Nitelikli geri bildirim (>=120 karakter) -> kazanc tahakkuku
    feedback = "x" * 150
    service.respond(sub["id"], "rejected", feedback)
    earnings = accounts.earnings_for(curator["id"])
    assert earnings["total_usd"] == 1.0
    assert earnings["pending_usd"] == 1.0

    # Ayni gonderime ikinci tahakkuk yazilamaz
    assert accounts.accrue_earning(curator["id"], sub["id"]) is False


def test_short_feedback_is_rejected(loop_db):
    """Garantili geri bildirim: 120 karakterin alti KABUL EDILMEZ —
    kabul de red de nitelikli yazili degerlendirme ister."""
    curator_id = loop_db
    artist, curator = _make_users(curator_id)
    accounts.grant_credits(artist["id"], GOLD_COST)
    sub = service.create_submission(
        "Sanatci", "Sarki", curator_id, artist_user_id=artist["id"]
    )
    with pytest.raises(ValueError, match="120 karakter"):
        service.respond(sub["id"], "rejected", "kisa yorum")
    with pytest.raises(ValueError, match="120 karakter"):
        service.respond(sub["id"], "accepted", "")
    # Gonderim hala pending; kazanc yok
    assert accounts.earnings_for(curator["id"])["total_usd"] == 0.0


def test_parse_spotify_playlist_id():
    assert service.parse_spotify_playlist_id(
        "https://open.spotify.com/playlist/3FixUcICt6cDhoqX5HCL9Y?si=abc"
    ) == "3FixUcICt6cDhoqX5HCL9Y"
    assert service.parse_spotify_playlist_id("https://deezer.com/playlist/1") is None


def test_ownership_verification_flow(loop_db, monkeypatch):
    """Kod uret -> aciklamada gorunce dogrula + otomatik onay."""
    curator_id = loop_db
    code = service.start_ownership_verification(curator_id)
    assert code.startswith("MZK-")

    # Aciklamayi sahtele: once kodsuz (hata), sonra kodlu (onay)
    monkeypatch.setattr(service, "_playlist_description", lambda pid: "bos aciklama")
    with pytest.raises(ValueError, match="bulunamadi"):
        service.check_ownership(curator_id)

    monkeypatch.setattr(
        service, "_playlist_description", lambda pid: f"Submit: x@y.com | {code}"
    )
    curator = service.check_ownership(curator_id)
    assert curator["ownership_verified"] == 1
    assert curator["status"] == "approved"


def test_expired_submission_refunds_credit(loop_db, monkeypatch):
    curator_id = loop_db
    artist, _ = _make_users(curator_id)
    accounts.grant_credits(artist["id"], GOLD_COST)
    sub = service.create_submission(
        "Sanatci", "Sarki", curator_id, artist_user_id=artist["id"]
    )
    assert accounts.get_user(artist["id"])["credits"] == 0

    # SLA'yi gecmis gibi isaretle
    conn = sqlite3.connect(db._DB_PATH)
    conn.execute(
        "UPDATE submissions SET deadline = '2000-01-01T00:00:00+00:00' WHERE id = ?",
        (sub["id"],),
    )
    conn.commit()
    conn.close()

    result = service.expire_and_refund()
    assert result["expired"] == 1
    assert result["refunded"] == 1
    assert accounts.get_user(artist["id"])["credits"] == GOLD_COST  # iade geldi

    # Idempotent: ikinci kosuda cift iade yok
    result2 = service.expire_and_refund()
    assert result2["refunded"] == 0
    assert accounts.get_user(artist["id"])["credits"] == GOLD_COST


def test_no_credit_blocks_submission(loop_db):
    curator_id = loop_db
    artist, _ = _make_users(curator_id)
    with pytest.raises(ValueError, match="Yetersiz kredi"):
        service.create_submission(
            "Sanatci", "Sarki", curator_id, artist_user_id=artist["id"]
        )


def test_auth_roundtrip(loop_db):
    artist, _ = _make_users(loop_db)
    token = accounts.login("artist@test.com", "parola123")
    user = accounts.user_by_token(token)
    assert user is not None and user["id"] == artist["id"]
    assert "password_hash" not in user
    with pytest.raises(ValueError):
        accounts.login("artist@test.com", "yanlis-parola")
