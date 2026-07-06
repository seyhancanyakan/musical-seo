"""Radyo reklam spotu mini-pazari testleri: radyo-disi kurator engeli, komisyon
hesabi, kabul -> sozlesme metni, paid idempotent + kabul sarti, record_air
odeme sarti + sayaci, pause -> katalogda gizli, gecersiz daypart/slot hatasi.
Network YOK.
"""
from __future__ import annotations

import pytest

from marketplace import accounts, db, radio_ads


@pytest.fixture()
def radio_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


def _make_curator_user(curator_type: str, email: str = "radyo@test.com") -> dict:
    curator_id = db.add_curator(
        name="Test Radyo", email=email, playlist_id=f"pid-{email}",
        playlist_title="Test Radyo Yayini", playlist_url="https://example.com/radyo",
        fans=1000, track_count=0, diversity=0.0, quality_score=10.0,
        status="approved", curator_type=curator_type,
    )
    return accounts.register(email, "parola123", "Test Radyo", "curator",
                              curator_id=curator_id)


@pytest.fixture()
def radio_curator(radio_db):
    return _make_curator_user("radyo")


@pytest.fixture()
def other_curator(radio_db):
    """Radyo turu OLMAYAN kurator (playlist)."""
    return _make_curator_user("playlist", email="playlist@test.com")


def test_non_radio_curator_cannot_create_listing(other_curator):
    with pytest.raises(ValueError, match="sadece radyo türü"):
        radio_ads.create_listing(
            other_curator, "Test FM", 30, "sabah", 10, 5000,
        )


def test_invalid_slot_seconds_raises(radio_curator):
    with pytest.raises(ValueError, match="spot süresi"):
        radio_ads.create_listing(
            radio_curator, "Test FM", 45, "sabah", 10, 5000,
        )


def test_invalid_daypart_raises(radio_curator):
    with pytest.raises(ValueError, match="kuşak"):
        radio_ads.create_listing(
            radio_curator, "Test FM", 30, "ogle", 10, 5000,
        )


def test_commission_calculation(radio_curator):
    listing = radio_ads.create_listing(
        radio_curator, "Test FM", 30, "sabah", 10, price_week_try=1000,
    )
    order = radio_ads.place_order(
        listing["id"], "Sanatci A", "sanatci@test.com", "artist", weeks=2,
    )
    assert order["price_try"] == 2000  # 2 hafta x 1000
    assert order["commission_try"] == round(2000 * radio_ads.COMMISSION_RATE)
    assert order["commission_try"] == 360


def test_accept_generates_contract_with_station_and_price(radio_curator):
    listing = radio_ads.create_listing(
        radio_curator, "Test FM", 30, "drive", 10, price_week_try=1000,
    )
    order = radio_ads.place_order(
        listing["id"], "Isletme A.S.", "isletme@test.com", "business", weeks=3,
    )
    accepted = radio_ads.respond_order(radio_curator, order["id"], "accepted")
    assert accepted["status"] == "accepted"
    assert accepted["contract_text"] is not None
    assert "Test FM" in accepted["contract_text"]
    assert str(accepted["price_try"]) in accepted["contract_text"]
    assert "MüzikSEO" in accepted["contract_text"]


def test_mark_paid_idempotent_and_requires_accepted(radio_curator):
    listing = radio_ads.create_listing(
        radio_curator, "Test FM", 30, "aksam", 10, price_week_try=1000,
    )
    order = radio_ads.place_order(
        listing["id"], "Sanatci A", "sanatci@test.com", "artist", weeks=1,
    )
    with pytest.raises(ValueError, match="kabul edilmiş"):
        radio_ads.mark_paid(order["id"])

    radio_ads.respond_order(radio_curator, order["id"], "accepted")
    paid_once = radio_ads.mark_paid(order["id"])
    assert paid_once["status"] == "paid"
    # Ikinci cagri hata firlatmaz, ayni sonucu doner (idempotent).
    paid_twice = radio_ads.mark_paid(order["id"])
    assert paid_twice["status"] == "paid"


def test_record_air_requires_payment_and_counts(radio_curator):
    listing = radio_ads.create_listing(
        radio_curator, "Test FM", 15, "gece", 10, price_week_try=1000,
    )
    order = radio_ads.place_order(
        listing["id"], "Sanatci A", "sanatci@test.com", "artist", weeks=1,
    )
    radio_ads.respond_order(radio_curator, order["id"], "accepted")

    with pytest.raises(ValueError, match="Önce ödeme tamamlanmalı"):
        radio_ads.record_air(radio_curator, order["id"])

    radio_ads.mark_paid(order["id"])
    first = radio_ads.record_air(radio_curator, order["id"])
    assert first["status"] == "airing"
    assert first["verified_plays"] == 1

    second = radio_ads.record_air(radio_curator, order["id"])
    assert second["status"] == "airing"
    assert second["verified_plays"] == 2


def test_pause_hides_from_public_catalog(radio_curator):
    listing = radio_ads.create_listing(
        radio_curator, "Test FM", 30, "gunduz", 10, price_week_try=1000,
    )
    assert len(radio_ads.public_catalog()) == 1

    radio_ads.pause_listing(radio_curator, listing["id"])
    assert radio_ads.public_catalog() == []

    radio_ads.activate_listing(radio_curator, listing["id"])
    assert len(radio_ads.public_catalog()) == 1
