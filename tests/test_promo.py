"""Promo (otomatik tanitim / animasyonlu kanit karti) testleri.

Kapsam: kredi dusumu + pro muafiyeti, SVG icerigi (artist/title + escape),
cover_url (network YOK, monkeypatch'li), token uniklik, dogrulanmis yerlesim
rozeti.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from marketplace import accounts, db, promo


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._data


@pytest.fixture()
def promo_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


@pytest.fixture()
def artist_user(promo_db):
    user = accounts.register("sanatci@test.com", "parola123", "Sanatci", "artist")
    accounts.grant_credits(user["id"], 5)
    return user


# --- Kredi dusumu + pro muafiyeti --------------------------------------------

def test_create_promo_charges_credit(artist_user):
    before = accounts.get_user(artist_user["id"])["credits"]
    asset = promo.create_promo(artist_user, "Sanatci", "Sarki")
    after = accounts.get_user(artist_user["id"])["credits"]
    assert before - after == promo.PROMO_COST
    assert asset["artist"] == "Sanatci"
    assert asset["title"] == "Sarki"
    assert asset["style"] == "dark"
    assert asset["token"].startswith("PRM-")


def test_create_promo_free_for_pro(promo_db):
    user = accounts.register("pro@test.com", "parola123", "Pro Sanatci", "artist")
    accounts.grant_credits(user["id"], 3)
    until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    accounts.set_pro_until(user["id"], until)
    pro_user = accounts.get_user(user["id"])
    assert accounts.is_pro(pro_user)

    before = accounts.get_user(user["id"])["credits"]
    promo.create_promo(pro_user, "Pro Sanatci", "Hit")
    after = accounts.get_user(user["id"])["credits"]
    assert before == after  # ucret alinmadi


def test_create_promo_insufficient_credits_raises(promo_db):
    user = accounts.register("fakir@test.com", "parola123", "Fakir", "artist")
    with pytest.raises(ValueError, match="[Kk]redi"):
        promo.create_promo(user, "Fakir", "Sarki")


def test_create_promo_invalid_style_rejected(artist_user):
    with pytest.raises(ValueError, match="[Ss]til"):
        promo.create_promo(artist_user, "Sanatci", "Sarki", style="neon")


# --- Token uniklik -------------------------------------------------------------

def test_promo_tokens_are_unique(artist_user):
    a = promo.create_promo(artist_user, "Sanatci", "Sarki 1")
    b = promo.create_promo(artist_user, "Sanatci", "Sarki 2")
    assert a["token"] != b["token"]
    items = promo.list_promos(artist_user["id"])
    assert {i["token"] for i in items} == {a["token"], b["token"]}


# --- Sahiplik ------------------------------------------------------------------

def test_get_promo_ownership_enforced(promo_db):
    owner = accounts.register("sahip@test.com", "parola123", "Sahip", "artist")
    accounts.grant_credits(owner["id"], 2)
    other = accounts.register("baskasi@test.com", "parola123", "Baskasi", "artist")
    asset = promo.create_promo(owner, "Sahip", "Sarki")

    fetched = promo.get_promo(asset["token"], owner)
    assert fetched["token"] == asset["token"]

    with pytest.raises(ValueError, match="bulunamadi"):
        promo.get_promo(asset["token"], other)

    with pytest.raises(ValueError, match="bulunamadi"):
        promo.get_promo("PRM-yok", owner)


# --- cover_url (network YOK) ----------------------------------------------------

def test_cover_url_returns_cover_xl(monkeypatch):
    monkeypatch.setattr(
        promo.requests, "get",
        lambda *a, **k: _FakeResponse(
            {"data": [{"album": {"cover_xl": "https://cdn.example/cover.jpg"}}]}
        ),
    )
    assert promo.cover_url("Sanatci", "Sarki") == "https://cdn.example/cover.jpg"


def test_cover_url_tolerates_empty_results(monkeypatch):
    monkeypatch.setattr(
        promo.requests, "get", lambda *a, **k: _FakeResponse({"data": []})
    )
    assert promo.cover_url("Sanatci", "Sarki") is None


def test_cover_url_tolerates_errors(monkeypatch):
    def _boom(*a, **k):
        raise promo.requests.RequestException("network down")

    monkeypatch.setattr(promo.requests, "get", _boom)
    assert promo.cover_url("Sanatci", "Sarki") is None


# --- SVG render: icerik + escape -------------------------------------------------

def test_render_svg_contains_artist_title_and_starts_with_svg_tag():
    asset = {"artist": "Sanatci", "title": "Sarki", "style": "dark"}
    svg = promo.render_svg(asset, cover=None, score=72.3, placements=2)
    assert svg.startswith("<svg")
    assert "Sanatci" in svg
    assert "Sarki" in svg
    assert "x2" in svg  # dogrulanmis yerlesim rozeti


def test_render_svg_escapes_html_in_artist_and_title():
    asset = {"artist": "<X&Y>", "title": '"Z" <script>', "style": "dark"}
    svg = promo.render_svg(asset, cover=None, score=None, placements=0)
    assert "<X&Y>" not in svg
    assert "<script>" not in svg
    assert "&lt;X&amp;Y&gt;" in svg


def test_render_svg_light_style_and_no_score_or_badge():
    asset = {"artist": "Sanatci", "title": "Sarki", "style": "light"}
    svg = promo.render_svg(asset, cover=None, score=None, placements=0)
    assert svg.startswith("<svg")
    assert "SEO SKORU" not in svg
    assert "DOGRULANMIS YERLESIM" not in svg


def test_render_svg_uses_cover_image_when_provided():
    asset = {"artist": "Sanatci", "title": "Sarki", "style": "dark"}
    svg = promo.render_svg(
        asset, cover="https://cdn.example/cover.jpg", score=None, placements=0
    )
    assert "https://cdn.example/cover.jpg" in svg


# --- Dogrulanmis yerlesim sayisi -------------------------------------------------

def test_verified_placement_count(promo_db):
    artist = accounts.register("dogrula@test.com", "parola123", "Dogrula", "artist")
    curator_id = db.add_curator(
        name="Kurator", email="kur@test.com", playlist_id="999",
        playlist_title="Liste", playlist_url="https://deezer.com/playlist/999",
        fans=500, track_count=20, diversity=0.4, quality_score=20.0,
        status="approved", quality_passed=True,
    )
    deadline = (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat()
    sub_id_1 = db.add_submission(
        "Dogrula", "Sarki 1", None, curator_id, "mesaj", deadline,
        artist_user_id=artist["id"],
    )
    db.add_submission(
        "Dogrula", "Sarki 2", None, curator_id, "mesaj", deadline,
        artist_user_id=artist["id"],
    )
    assert promo.verified_placement_count(artist["id"]) == 0

    db.set_placement_verified(sub_id_1)
    assert promo.verified_placement_count(artist["id"]) == 1


# --- latest_score hata tolerans ------------------------------------------------

def test_latest_score_tolerates_missing_history(promo_db):
    assert promo.latest_score("Bilinmeyen", "Sarki") is None
