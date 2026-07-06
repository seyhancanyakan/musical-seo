"""Sync/Lisans mini-marketplace testleri: komisyon hesabi, fiyatsiz kullanim
turu hatasi, kabul -> lisans metni, paid idempotent, pause -> katalogda gizli.
Network YOK.
"""
from __future__ import annotations

import pytest

from marketplace import accounts, db, syncmarket


@pytest.fixture()
def sync_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


@pytest.fixture()
def artist(sync_db):
    return accounts.register("sanatci@test.com", "parola123", "Sanatci", "artist")


def test_commission_calculation(artist):
    listing = syncmarket.create_listing(
        artist, "Sanatci", "Sarki", price_youtube=1000,
    )
    request = syncmarket.request_license(
        listing["id"], "Marka A.S.", "marka@test.com", "youtube",
    )
    assert request["price_try"] == 1000
    assert request["commission_try"] == round(1000 * syncmarket.COMMISSION_RATE)
    assert request["commission_try"] == 150


def test_missing_price_for_use_kind_raises(artist):
    listing = syncmarket.create_listing(
        artist, "Sanatci", "Sarki", price_youtube=1000,
    )
    with pytest.raises(ValueError, match="bu kullanim icin fiyat yok"):
        syncmarket.request_license(
            listing["id"], "Marka A.S.", "marka@test.com", "film",
        )


def test_no_positive_price_rejected_on_create(artist):
    with pytest.raises(ValueError, match="fiyat"):
        syncmarket.create_listing(artist, "Sanatci", "Sarki")
    with pytest.raises(ValueError, match="fiyat"):
        syncmarket.create_listing(artist, "Sanatci", "Sarki", price_youtube=0)


def test_accept_generates_license_text_with_artist_name(artist):
    listing = syncmarket.create_listing(
        artist, "Sanatci", "Sarki", price_reklam=2000,
    )
    request = syncmarket.request_license(
        listing["id"], "Reklam Ajansi", "ajans@test.com", "reklam",
    )
    accepted = syncmarket.respond_request(artist, request["id"], "accepted")
    assert accepted["status"] == "accepted"
    assert accepted["license_text"] is not None
    assert "Sanatci" in accepted["license_text"]
    assert "1 (bir) yil" in accepted["license_text"]
    assert "TEK KULLANIM" in accepted["license_text"]
    assert "MUZIKSEO" in accepted["license_text"]


def test_reject_does_not_generate_license_text(artist):
    listing = syncmarket.create_listing(
        artist, "Sanatci", "Sarki", price_film=5000,
    )
    request = syncmarket.request_license(
        listing["id"], "Yapimci", "yapimci@test.com", "film",
    )
    rejected = syncmarket.respond_request(artist, request["id"], "rejected")
    assert rejected["status"] == "rejected"
    assert rejected["license_text"] is None


def test_mark_paid_idempotent(artist):
    listing = syncmarket.create_listing(
        artist, "Sanatci", "Sarki", price_youtube=1000,
    )
    request = syncmarket.request_license(
        listing["id"], "Marka A.S.", "marka@test.com", "youtube",
    )
    syncmarket.respond_request(artist, request["id"], "accepted")

    paid_once = syncmarket.mark_paid(request["id"])
    assert paid_once["status"] == "paid"
    # Ikinci cagri hata firlatmaz, ayni sonucu doner (idempotent).
    paid_twice = syncmarket.mark_paid(request["id"])
    assert paid_twice["status"] == "paid"


def test_mark_paid_requires_accepted_status(artist):
    listing = syncmarket.create_listing(
        artist, "Sanatci", "Sarki", price_youtube=1000,
    )
    request = syncmarket.request_license(
        listing["id"], "Marka A.S.", "marka@test.com", "youtube",
    )
    with pytest.raises(ValueError, match="kabul edilmis"):
        syncmarket.mark_paid(request["id"])


def test_pause_hides_from_public_catalog(artist):
    listing = syncmarket.create_listing(
        artist, "Sanatci", "Sarki", price_youtube=1000,
    )
    assert len(syncmarket.list_public()) == 1

    syncmarket.pause_listing(artist, listing["id"])
    assert syncmarket.list_public() == []

    syncmarket.activate_listing(artist, listing["id"])
    assert len(syncmarket.list_public()) == 1


def test_public_catalog_filters_by_use_kind(artist):
    syncmarket.create_listing(artist, "Sanatci", "Sarki1", price_youtube=1000)
    syncmarket.create_listing(artist, "Sanatci", "Sarki2", price_film=3000)

    only_youtube = syncmarket.list_public(use_kind="youtube")
    assert len(only_youtube) == 1
    assert only_youtube[0]["title"] == "Sarki1"

    only_film = syncmarket.list_public(use_kind="film")
    assert len(only_film) == 1
    assert only_film[0]["title"] == "Sarki2"


def test_respond_requires_ownership(artist, sync_db):
    other_artist = accounts.register("baska@test.com", "parola123", "Baska", "artist")
    listing = syncmarket.create_listing(
        artist, "Sanatci", "Sarki", price_youtube=1000,
    )
    request = syncmarket.request_license(
        listing["id"], "Marka A.S.", "marka@test.com", "youtube",
    )
    with pytest.raises(ValueError, match="Talep bulunamadi"):
        syncmarket.respond_request(other_artist, request["id"], "accepted")


def test_double_respond_rejected(artist):
    listing = syncmarket.create_listing(
        artist, "Sanatci", "Sarki", price_youtube=1000,
    )
    request = syncmarket.request_license(
        listing["id"], "Marka A.S.", "marka@test.com", "youtube",
    )
    syncmarket.respond_request(artist, request["id"], "accepted")
    with pytest.raises(ValueError, match="zaten yanitlanmis"):
        syncmarket.respond_request(artist, request["id"], "rejected")
