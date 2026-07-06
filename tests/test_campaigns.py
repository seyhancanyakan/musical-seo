"""Kampanya fan-out testleri: paket onerici butce kirpma, fan-out butce
disiplini + en az bir siparis sarti, kupon kodu uretimi, rapor
planned/verified hesabi, e-posta dogrulama gate'i, admin toplu odeme gecisi.
Network YOK.
"""
from __future__ import annotations

import pytest

from marketplace import accounts, campaigns, db, radio_ads


@pytest.fixture()
def campaign_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


def _make_radio_curator(email: str = "radyo@test.com") -> dict:
    curator_id = db.add_curator(
        name="Test Radyo", email=email, playlist_id=f"pid-{email}",
        playlist_title="Test Radyo Yayini", playlist_url="https://example.com/radyo",
        fans=1000, track_count=0, diversity=0.0, quality_score=10.0,
        status="approved", curator_type="radyo",
    )
    return accounts.register(email, "parola123", "Test Radyo", "curator",
                              curator_id=curator_id)


@pytest.fixture()
def radio_curator(campaign_db):
    return _make_radio_curator()


def _listing(user, station_name, price_week_try, daypart="sabah", city="İstanbul",
             weekly_spots=10, slot_seconds=30):
    return radio_ads.create_listing(
        user, station_name, slot_seconds, daypart, weekly_spots,
        price_week_try, city=city,
    )


# --- Paket onerici -------------------------------------------------------------

def test_suggest_packages_empty_when_no_listings(campaign_db):
    packages = campaigns.suggest_packages()
    assert len(packages) == 3
    for pkg in packages:
        assert pkg["listings"] == []
        assert pkg["total_try"] == 0


def test_suggest_packages_trims_to_budget(radio_curator):
    _listing(radio_curator, "Ucuz FM", 1000)
    _listing(radio_curator, "Orta FM", 2000)
    _listing(radio_curator, "Pahali FM", 5000)

    packages = campaigns.suggest_packages(budget_try=2500)
    opening = next(p for p in packages if p["key"] == "opening")
    # Sadece en ucuz (1000) butceye sigar; 1000+2000=3000 > 2500 oldugu icin
    # ikinci ilan eklenmeden durulur (kirpma).
    assert [l["station_name"] for l in opening["listings"]] == ["Ucuz FM"]
    assert opening["total_try"] == 1000


def test_suggest_packages_weekend_filters_daypart(radio_curator):
    _listing(radio_curator, "Sabah FM", 1000, daypart="sabah")
    _listing(radio_curator, "Drive FM", 1500, daypart="drive")
    _listing(radio_curator, "Aksam FM", 1200, daypart="aksam")

    packages = campaigns.suggest_packages()
    weekend = next(p for p in packages if p["key"] == "weekend")
    stations = {l["station_name"] for l in weekend["listings"]}
    assert stations == {"Drive FM", "Aksam FM"}


# --- Fan-out butce disiplini ---------------------------------------------------

def test_create_campaign_stops_at_budget_and_requires_one_order(radio_curator):
    _listing(radio_curator, "Ucuz FM", 1000)
    _listing(radio_curator, "Pahali FM", 5000)

    campaign = campaigns.create_campaign(
        buyer_name="Sanatci A", buyer_email="sanatci@test.com", buyer_kind="artist",
        product_name="Yeni Albüm", spot_text="Yeni albüm çıktı!",
        cities=[], dayparts=[], weeks=1, budget_try=1200,
    )
    orders = campaigns.campaign_status(campaign["id"])
    # Sadece Ucuz FM (1000 <= 1200) siparise donusur; Pahali FM (5000) butceyi
    # asacagi icin dahil edilmez.
    assert len(orders) == 1
    assert orders[0]["station"] == "Ucuz FM"
    assert campaign["total_try"] == 1000


def test_create_campaign_raises_when_nothing_fits_budget(radio_curator):
    _listing(radio_curator, "Pahali FM", 5000)
    with pytest.raises(ValueError, match="bütçeye uyan ilan bulunamadı"):
        campaigns.create_campaign(
            buyer_name="Sanatci A", buyer_email="sanatci@test.com",
            buyer_kind="artist", product_name="Yeni Albüm",
            spot_text="Yeni albüm çıktı!", cities=[], dayparts=[],
            weeks=1, budget_try=100,
        )


def test_create_campaign_raises_when_no_listings_at_all(campaign_db):
    with pytest.raises(ValueError, match="bütçeye uyan ilan bulunamadı"):
        campaigns.create_campaign(
            buyer_name="Sanatci A", buyer_email="sanatci@test.com",
            buyer_kind="artist", product_name="Yeni Albüm",
            spot_text="Yeni albüm çıktı!", cities=[], dayparts=[],
            weeks=1, budget_try=10000,
        )


def test_create_campaign_filters_by_city(radio_curator):
    _listing(radio_curator, "İstanbul FM", 1000, city="İstanbul")
    _listing(radio_curator, "Ankara FM", 1000, city="Ankara")

    campaign = campaigns.create_campaign(
        buyer_name="İşletme A.Ş.", buyer_email="isletme@test.com",
        buyer_kind="business", product_name="Yeni Ürün",
        spot_text="Yeni ürünümüzü keşfedin!", cities=["Ankara"], dayparts=[],
        weeks=1, budget_try=10000,
    )
    orders = campaigns.campaign_status(campaign["id"])
    assert len(orders) == 1
    assert orders[0]["station"] == "Ankara FM"


# --- Kupon kodu ----------------------------------------------------------------

def test_coupon_code_generated_with_prefix(radio_curator):
    _listing(radio_curator, "Ucuz FM", 1000)
    campaign = campaigns.create_campaign(
        buyer_name="Sanatci A", buyer_email="sanatci@test.com", buyer_kind="artist",
        product_name="Yeni Albüm", spot_text="Yeni albüm çıktı!",
        cities=[], dayparts=[], weeks=1, budget_try=10000,
    )
    assert campaign["coupon_code"].startswith("RADYO-")
    assert len(campaign["coupon_code"]) == len("RADYO-") + 4
    assert campaign["coupon_code"] in campaign["contract_text"]


# --- Rapor: planned/verified hesabi ---------------------------------------------

def test_campaign_report_planned_and_verified(radio_curator):
    listing = _listing(radio_curator, "Ucuz FM", 1000, weekly_spots=10)
    campaign = campaigns.create_campaign(
        buyer_name="Sanatci A", buyer_email="sanatci@test.com", buyer_kind="artist",
        product_name="Yeni Albüm", spot_text="Yeni albüm çıktı!",
        cities=[], dayparts=[], weeks=3, budget_try=10000,
    )
    report = campaigns.campaign_report(campaign["id"])
    assert report["planned_spots"] == 10 * 3  # weekly_spots * weeks
    assert report["verified_plays"] == 0
    assert len(report["per_station"]) == 1
    assert report["per_station"][0]["station"] == "Ucuz FM"
    assert report["coupon_code"] == campaign["coupon_code"]

    # Yayin dogrulandiktan sonra teyitli sayim artmali.
    orders = campaigns.campaign_status(campaign["id"])
    order_id = orders[0]["order_id"]
    radio_ads.respond_order(radio_curator, order_id, "accepted")
    radio_ads.mark_paid(order_id)
    radio_ads.record_air(radio_curator, order_id)

    report_after = campaigns.campaign_report(campaign["id"])
    assert report_after["verified_plays"] == 1


# --- E-posta dogrulama gate'i -----------------------------------------------------

def test_get_campaign_requires_matching_email(radio_curator):
    _listing(radio_curator, "Ucuz FM", 1000)
    campaign = campaigns.create_campaign(
        buyer_name="Sanatci A", buyer_email="sanatci@test.com", buyer_kind="artist",
        product_name="Yeni Albüm", spot_text="Yeni albüm çıktı!",
        cities=[], dayparts=[], weeks=1, budget_try=10000,
    )
    with pytest.raises(ValueError, match="Kampanya bulunamadı"):
        campaigns.get_campaign(campaign["id"], "baskasi@test.com")

    found = campaigns.get_campaign(campaign["id"], "sanatci@test.com")
    assert found["id"] == campaign["id"]


def test_get_campaign_raises_for_missing_id(campaign_db):
    with pytest.raises(ValueError, match="Kampanya bulunamadı"):
        campaigns.get_campaign(9999, "kimse@test.com")


# --- Admin toplu odeme gecisi -----------------------------------------------------

def test_admin_mark_paid_transitions_all_linked_orders(radio_curator):
    _listing(radio_curator, "Ucuz FM", 1000)
    _listing(radio_curator, "Orta FM", 1500)
    campaign = campaigns.create_campaign(
        buyer_name="Sanatci A", buyer_email="sanatci@test.com", buyer_kind="artist",
        product_name="Yeni Albüm", spot_text="Yeni albüm çıktı!",
        cities=[], dayparts=[], weeks=1, budget_try=10000,
    )
    orders = campaigns.campaign_status(campaign["id"])
    assert len(orders) == 2
    for row in orders:
        radio_ads.respond_order(radio_curator, row["order_id"], "accepted")

    updated = campaigns.mark_campaign_paid(campaign["id"])
    assert updated["status"] == "active"

    for row in campaigns.campaign_status(campaign["id"]):
        assert row["status"] == "paid"


def test_admin_mark_paid_requires_accepted_orders(radio_curator):
    _listing(radio_curator, "Ucuz FM", 1000)
    campaign = campaigns.create_campaign(
        buyer_name="Sanatci A", buyer_email="sanatci@test.com", buyer_kind="artist",
        product_name="Yeni Albüm", spot_text="Yeni albüm çıktı!",
        cities=[], dayparts=[], weeks=1, budget_try=10000,
    )
    # Siparis henuz 'pending' -> mark_paid 'kabul edilmiş' hatasi firlatir.
    with pytest.raises(ValueError, match="kabul edilmiş"):
        campaigns.mark_campaign_paid(campaign["id"])
