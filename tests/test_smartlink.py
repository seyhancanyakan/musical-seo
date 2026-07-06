"""Akilli link + affiliate testleri: slug uniklik, fan dedupe, export kredi
dusumu + pro muafiyeti, tiklama sayaci, bilinmeyen affiliate anahtari.
Network YOK.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from marketplace import accounts, affiliate, db, smartlink


@pytest.fixture()
def link_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    return accounts.register("sanatci@test.com", "parola123", "Sanatci", "artist")


# --- Slug uniklik + goruntuleme sayaci --------------------------------------

def test_create_link_unique_slug_and_views_increment(link_db):
    artist_user = link_db
    link1 = smartlink.create_link(
        artist_user, "Sanatci", "Sarki",
        {"spotify": "https://open.spotify.com/track/1"},
    )
    link2 = smartlink.create_link(
        artist_user, "Sanatci", "Sarki",
        {"spotify": "https://open.spotify.com/track/2"},
    )
    assert link1["slug"] != link2["slug"]
    assert link1["views"] == 0

    fetched = smartlink.get_by_slug(link1["slug"])
    assert fetched["views"] == 1
    fetched_again = smartlink.get_by_slug(link1["slug"])
    assert fetched_again["views"] == 2


def test_invalid_link_platform_or_url_rejected(link_db):
    with pytest.raises(ValueError, match="Gecersiz platform"):
        smartlink.create_link(
            link_db, "Sanatci", "Sarki", {"tiktok": "https://tiktok.com/x"}
        )
    with pytest.raises(ValueError, match="URL"):
        smartlink.create_link(
            link_db, "Sanatci", "Sarki", {"spotify": "spotify.com/track/1"}
        )


def test_presave_flag_set_when_release_date_in_future(link_db):
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    upcoming = smartlink.create_link(
        link_db, "Sanatci", "Yeni Sarki",
        {"spotify": "https://open.spotify.com/track/9"}, release_date=future,
    )
    released = smartlink.create_link(
        link_db, "Sanatci", "Eski Sarki",
        {"spotify": "https://open.spotify.com/track/8"}, release_date=past,
    )
    assert upcoming["presave"] == 1
    assert released["presave"] == 0


# --- Tiklama sayaci ----------------------------------------------------------

def test_record_click_counts_per_platform(link_db):
    link = smartlink.create_link(
        link_db, "Sanatci", "Sarki",
        {"spotify": "https://open.spotify.com/track/1",
         "deezer": "https://deezer.com/track/1"},
    )
    smartlink.record_click(link["slug"], "spotify")
    smartlink.record_click(link["slug"], "spotify")
    updated = smartlink.record_click(link["slug"], "deezer")
    assert updated["clicks"]["spotify"] == 2
    assert updated["clicks"]["deezer"] == 1


def test_record_click_unknown_platform_rejected(link_db):
    link = smartlink.create_link(
        link_db, "Sanatci", "Sarki",
        {"spotify": "https://open.spotify.com/track/1"},
    )
    with pytest.raises(ValueError, match="Gecersiz platform"):
        smartlink.record_click(link["slug"], "tiktok")


# --- Fan dedupe --------------------------------------------------------------

def test_add_fan_dedupe(link_db):
    link = smartlink.create_link(
        link_db, "Sanatci", "Sarki",
        {"spotify": "https://open.spotify.com/track/1"},
    )
    assert smartlink.add_fan(link["slug"], "fan@test.com") is True
    assert smartlink.add_fan(link["slug"], "fan@test.com") is False   # dedupe
    assert smartlink.add_fan(link["slug"], "baska@test.com") is True

    fans = smartlink.fans_for(link_db, link["id"])
    assert len(fans) == 2


def test_add_fan_invalid_email_rejected(link_db):
    link = smartlink.create_link(
        link_db, "Sanatci", "Sarki",
        {"spotify": "https://open.spotify.com/track/1"},
    )
    with pytest.raises(ValueError, match="e-posta"):
        smartlink.add_fan(link["slug"], "gecersiz")


# --- Export kredi dusumu + pro muafiyeti -------------------------------------

def test_export_fans_charges_credit_unless_pro(link_db):
    link = smartlink.create_link(
        link_db, "Sanatci", "Sarki",
        {"spotify": "https://open.spotify.com/track/1"},
    )
    smartlink.add_fan(link["slug"], "fan@test.com")

    accounts.grant_credits(link_db["id"], 5)
    before = accounts.get_user(link_db["id"])["credits"]
    fans = smartlink.export_fans(link_db, link["id"])
    after = accounts.get_user(link_db["id"])["credits"]
    assert len(fans) == 1
    assert before - after == smartlink.EXPORT_COST

    # Pro kullaniciya ucretsiz
    until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    accounts.set_pro_until(link_db["id"], until)
    pro_user = accounts.get_user(link_db["id"])
    before_pro = accounts.get_user(link_db["id"])["credits"]
    smartlink.export_fans(pro_user, link["id"])
    after_pro = accounts.get_user(link_db["id"])["credits"]
    assert before_pro == after_pro


def test_export_fans_insufficient_credit_raises(link_db):
    link = smartlink.create_link(
        link_db, "Sanatci", "Sarki",
        {"spotify": "https://open.spotify.com/track/1"},
    )
    # Kredi yok (yeni kullanici) -> yetersiz kredi hatasi
    with pytest.raises(ValueError, match="kredi"):
        smartlink.export_fans(link_db, link["id"])


def test_fans_for_ownership_enforced(link_db):
    other_user = accounts.register("baska@test.com", "parola123", "Baska", "artist")
    link = smartlink.create_link(
        link_db, "Sanatci", "Sarki",
        {"spotify": "https://open.spotify.com/track/1"},
    )
    with pytest.raises(ValueError, match="Link bulunamadi"):
        smartlink.fans_for(other_user, link["id"])


# --- Affiliate ---------------------------------------------------------------

def test_affiliate_list_and_click(link_db):
    partners = affiliate.list_partners()
    assert len(partners) == 3
    keys = {p["key"] for p in partners}
    assert keys == {"distro", "mastering", "kapak-tasarim"}

    url = affiliate.record_click("distro")
    assert "ref=muzikseo" in url


def test_affiliate_unknown_key_raises(link_db):
    with pytest.raises(ValueError, match="Bilinmeyen ortak"):
        affiliate.record_click("nonexistent")
