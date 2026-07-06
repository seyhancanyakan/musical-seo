"""Radyo airplay takibi testleri: abonelik kredi dusumu, poll_once esleme,
dedupe penceresi, suresi dolmus abonelik, icecast/shoutcast parse.

Network YOK — requests.get airplay modulu icinde monkeypatch'lenir.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from marketplace import accounts, airplay, db


@pytest.fixture()
def air_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    user = accounts.register(
        email="sanatci@test.com", password="parola123",
        name="Test Sanatci", role="artist",
    )
    accounts.grant_credits(user["id"], 10, "grant")
    return user


def _make_station(kind: str = "icecast") -> dict:
    return airplay.add_station("Test FM", "http://example.com/meta", kind)


# --- Abonelik + kredi dusumu -------------------------------------------------

def test_subscribe_charges_credits_and_sets_expiry(air_db):
    user = air_db
    before = accounts.get_user(user["id"])["credits"]

    sub = airplay.subscribe(user, "Guzel Sanatci", "Guzel Sarki")

    after = accounts.get_user(user["id"])["credits"]
    assert before - after == airplay.SUBSCRIPTION_COST
    assert sub["artist"] == "Guzel Sanatci"
    assert sub["title"] == "Guzel Sarki"
    assert sub["active"] == 1
    expires = datetime.fromisoformat(sub["expires_at"])
    assert expires > datetime.now(timezone.utc) + timedelta(days=29)


def test_subscribe_insufficient_credits_raises(air_db):
    user = air_db
    # Bakiyeyi tuket
    accounts.charge_credits(user["id"], 10, "test_drain")
    with pytest.raises(ValueError):
        airplay.subscribe(user, "Sanatci", "Sarki")


def test_subscribe_blank_fields_raise(air_db):
    user = air_db
    with pytest.raises(ValueError):
        airplay.subscribe(user, "", "Sarki")
    with pytest.raises(ValueError):
        airplay.subscribe(user, "Sanatci", "   ")


# --- poll_once: esleme + fold (aksan-duyarsiz) -------------------------------

def test_poll_once_matches_accented_title_case_insensitive(air_db):
    user = air_db
    airplay.subscribe(user, "Ajda", "Güzel Günler")  # aksanli abonelik
    station = _make_station()

    def fake_fetch(_station: dict) -> str:
        return "AJDA - Guzel Gunler (canli yayin)"  # aksansiz + buyuk harf

    result = airplay.poll_once(fetch_fn=fake_fetch)

    assert result["checked_stations"] == 1
    assert len(result["hits"]) == 1
    hits = airplay.my_hits(user["id"])
    assert len(hits) == 1
    assert hits[0]["station_name"] == station["name"]


def test_poll_once_no_match_when_raw_missing_title(air_db):
    user = air_db
    airplay.subscribe(user, "Ajda", "Güzel Günler")
    _make_station()

    result = airplay.poll_once(fetch_fn=lambda s: "Baska Sanatci - Baska Sarki")

    assert result["hits"] == []
    assert airplay.my_hits(user["id"]) == []


def test_poll_once_skips_when_fetch_returns_none(air_db):
    user = air_db
    airplay.subscribe(user, "Ajda", "Güzel Günler")
    _make_station()

    result = airplay.poll_once(fetch_fn=lambda s: None)

    assert result["checked_stations"] == 1
    assert result["hits"] == []


# --- Dedupe penceresi ---------------------------------------------------------

def test_poll_once_dedupes_within_window(air_db):
    user = air_db
    airplay.subscribe(user, "Ajda", "Güzel Günler")
    _make_station()
    fake_fetch = lambda s: "Ajda - Guzel Gunler"

    first = airplay.poll_once(fetch_fn=fake_fetch)
    second = airplay.poll_once(fetch_fn=fake_fetch)

    assert len(first["hits"]) == 1
    assert len(second["hits"]) == 0  # ayni pencere icinde ikinci hit yazilmadi
    assert len(airplay.my_hits(user["id"])) == 1


def test_poll_once_writes_new_hit_after_dedupe_window_passes(air_db):
    user = air_db
    airplay.subscribe(user, "Ajda", "Güzel Günler")
    _make_station()
    fake_fetch = lambda s: "Ajda - Guzel Gunler"

    airplay.poll_once(fetch_fn=fake_fetch)

    # Dedupe penceresini simule et: mevcut hit'in created_at'ini geriye al.
    conn = airplay._connect()
    try:
        with conn:
            old = (
                datetime.now(timezone.utc)
                - timedelta(minutes=airplay.DEDUPE_MINUTES + 1)
            ).isoformat()
            conn.execute("UPDATE airplay_hits SET created_at = ?", (old,))
    finally:
        conn.close()

    second = airplay.poll_once(fetch_fn=fake_fetch)
    assert len(second["hits"]) == 1
    assert len(airplay.my_hits(user["id"])) == 2


# --- Suresi dolmus abonelik eslesmez ------------------------------------------

def test_poll_once_ignores_expired_subscription(air_db):
    user = air_db
    sub = airplay.subscribe(user, "Ajda", "Güzel Günler")
    _make_station()

    conn = airplay._connect()
    try:
        with conn:
            expired = (
                datetime.now(timezone.utc) - timedelta(days=1)
            ).isoformat()
            conn.execute(
                "UPDATE airplay_subscriptions SET expires_at = ? WHERE id = ?",
                (expired, sub["id"]),
            )
    finally:
        conn.close()

    result = airplay.poll_once(fetch_fn=lambda s: "Ajda - Guzel Gunler")

    assert result["hits"] == []
    assert airplay.my_hits(user["id"]) == []


def test_poll_once_ignores_inactive_station(air_db):
    user = air_db
    airplay.subscribe(user, "Ajda", "Güzel Günler")
    station = _make_station()

    conn = airplay._connect()
    try:
        with conn:
            conn.execute(
                "UPDATE airplay_stations SET active = 0 WHERE id = ?",
                (station["id"],),
            )
    finally:
        conn.close()

    result = airplay.poll_once(fetch_fn=lambda s: "Ajda - Guzel Gunler")

    assert result["checked_stations"] == 0
    assert result["hits"] == []


# --- Istasyon parse: icecast / shoutcast --------------------------------------

class _FakeResponse:
    def __init__(self, json_data=None, text_data: str = ""):
        self._json_data = json_data
        self.text = text_data

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._json_data


ICECAST_JSON_SINGLE = {
    "icestats": {
        "source": {"title": "Guzel Gunler", "artist": "Ajda"}
    }
}

ICECAST_JSON_LIST = {
    "icestats": {
        "source": [
            {"title": "Ilk Kanal Sarkisi", "artist": "Sanatci A"},
            {"title": "Guzel Gunler", "artist": "Ajda"},
        ]
    }
}

SHOUTCAST_7HTML = "68,0,3,1732,,Ajda - Guzel Gunler"


def test_icecast_now_playing_parses_single_source(monkeypatch):
    monkeypatch.setattr(
        airplay.requests, "get",
        lambda url, timeout: _FakeResponse(json_data=ICECAST_JSON_SINGLE),
    )
    result = airplay.now_playing({"kind": "icecast", "meta_url": "http://x/status-json.xsl"})
    assert "Ajda" in result
    assert "Guzel Gunler" in result


def test_icecast_now_playing_parses_source_list(monkeypatch):
    monkeypatch.setattr(
        airplay.requests, "get",
        lambda url, timeout: _FakeResponse(json_data=ICECAST_JSON_LIST),
    )
    result = airplay.now_playing({"kind": "icecast", "meta_url": "http://x/status-json.xsl"})
    assert "Ajda" in result
    assert "Guzel Gunler" in result


def test_shoutcast_now_playing_parses_last_field(monkeypatch):
    monkeypatch.setattr(
        airplay.requests, "get",
        lambda url, timeout: _FakeResponse(text_data=SHOUTCAST_7HTML),
    )
    result = airplay.now_playing({"kind": "shoutcast", "meta_url": "http://x/7.html"})
    assert result == "Ajda - Guzel Gunler"


def test_now_playing_returns_none_on_error(monkeypatch):
    def _raise(url, timeout):
        raise ConnectionError("baglanti yok")

    monkeypatch.setattr(airplay.requests, "get", _raise)
    result = airplay.now_playing({"kind": "icecast", "meta_url": "http://x"})
    assert result is None


# --- Istasyon yonetimi (saf dogrulama) ----------------------------------------

def test_add_station_validates_kind(air_db):
    with pytest.raises(ValueError):
        airplay.add_station("Radyo X", "http://x", kind="invalid")


def test_add_station_and_list(air_db):
    airplay.add_station("Radyo A", "http://a", "icecast")
    airplay.add_station("Radyo B", "http://b", "shoutcast")
    stations = airplay.list_stations()
    assert len(stations) == 2
    assert {s["kind"] for s in stations} == {"icecast", "shoutcast"}
