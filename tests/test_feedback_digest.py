"""Geri bildirim sentez raporu testleri: MIN esigi, tema tespiti, stopword
filtresi, kredi dusumu + pro muafiyeti, fold ile aksan duyarsiz sayim.
Network YOK.
"""
from __future__ import annotations

import pytest

from marketplace import accounts, db, feedback_digest, pricing, service
from musical_seo.models import TrackInfo

# 120+ karakter zorunlu (accounts.QUALIFIED_FEEDBACK_MIN_CHARS) — respond() bunu ister.
FEEDBACK_INTRO = (
    "Intro suresi cok uzun kaliyor, dinleyici kaybediyorsun. Bunun disinda "
    "miks temiz ve nakarat guclu, genel olarak begendim."
)
FEEDBACK_INTRO_2 = (
    "Giris (intro) bolumu fazla uzun, kisaltmani oneririm. Vokal katmanlari "
    "iyi calisilmis ama tempo biraz dagitiyor enerjiyi."
)
FEEDBACK_PLAIN = (
    "Bu parca genel olarak iyi ama ozel bir sey sunmuyor, daha fazla calisma "
    "gerekiyor bence, tekrar dinlemeyi dusunurum ve baska sarkilarini da "
    "merakla bekliyorum."
)
FEEDBACK_ACCENTED = (
    "Güzel bir prodüksiyon olmus, güzel bir vokal performansi var, güzel "
    "davranmissiniz kayit surecinde, tekrar tekrar dinlemek istiyorum bunu."
)


@pytest.fixture()
def fd_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    monkeypatch.setattr(pricing, "LISTEN_GATE_SECONDS", 0)
    monkeypatch.setattr(
        service.deezer, "lookup",
        lambda artist, title: TrackInfo(
            source="deezer", found=True, title=title, artist=artist,
            url="https://www.deezer.com/track/1",
        ),
    )
    curator_id = db.add_curator(
        name="Kucuk Kurator", email="k@test.com", playlist_id="111",
        playlist_title="Kucuk Liste", playlist_url="https://deezer.com/playlist/111",
        fans=100, track_count=30, diversity=0.5, quality_score=30.0,
        status="approved", quality_passed=True,
    )
    artist = accounts.register(
        "artist@test.com", "sifre1234", "Test Sanatci", "artist"
    )
    return curator_id, artist


def _submit_with_feedback(curator_id, artist_user, title, feedback, action="accepted"):
    sub = service.create_submission(
        artist_user["name"], title, curator_id, artist_user_id=artist_user["id"],
    )
    return service.respond(sub["id"], action, feedback)


def _give_credits(user_id, amount):
    accounts.grant_credits(user_id, amount)


# --- MIN esigi -------------------------------------------------------------

def test_synthesize_raises_below_min_feedbacks(fd_db):
    curator_id, artist = fd_db
    _give_credits(artist["id"], 10)
    _submit_with_feedback(curator_id, artist, "Tek Sarki", FEEDBACK_PLAIN)
    with pytest.raises(ValueError, match="Yeterli geri bildirim yok"):
        feedback_digest.synthesize(accounts.get_user(artist["id"]))


# --- Tema tespiti ------------------------------------------------------------

def test_synthesize_detects_theme_when_two_feedbacks_mention_it(fd_db):
    curator_id, artist = fd_db
    _give_credits(artist["id"], 10)
    _submit_with_feedback(curator_id, artist, "Sarki 1", FEEDBACK_INTRO)
    _submit_with_feedback(curator_id, artist, "Sarki 2", FEEDBACK_INTRO_2)

    digest = feedback_digest.synthesize(accounts.get_user(artist["id"]))

    intro_theme = next((t for t in digest["themes"] if t["keyword"] == "intro"), None)
    assert intro_theme is not None
    assert intro_theme["mentions"] == 2
    assert intro_theme["action"] == feedback_digest.THEME_ACTIONS["intro"]


def test_synthesize_skips_theme_mentioned_only_once(fd_db):
    curator_id, artist = fd_db
    _give_credits(artist["id"], 10)
    _submit_with_feedback(curator_id, artist, "Sarki 1", FEEDBACK_INTRO)
    _submit_with_feedback(curator_id, artist, "Sarki 2", FEEDBACK_PLAIN)

    digest = feedback_digest.synthesize(accounts.get_user(artist["id"]))

    assert all(t["keyword"] != "intro" for t in digest["themes"])


# --- Stopword filtresi -------------------------------------------------------

def test_top_keywords_exclude_stopwords(fd_db):
    curator_id, artist = fd_db
    _give_credits(artist["id"], 10)
    _submit_with_feedback(curator_id, artist, "Sarki 1", FEEDBACK_INTRO)
    _submit_with_feedback(curator_id, artist, "Sarki 2", FEEDBACK_PLAIN)

    digest = feedback_digest.synthesize(accounts.get_user(artist["id"]))

    keywords = {k["keyword"] for k in digest["top_keywords"]}
    assert not (keywords & feedback_digest.TR_STOPWORDS)
    assert all(len(k) >= feedback_digest.MIN_KEYWORD_LEN for k in keywords)


# --- Kredi dusumu + pro muafiyeti --------------------------------------------

def test_synthesize_charges_credit_for_non_pro(fd_db):
    curator_id, artist = fd_db
    _give_credits(artist["id"], 10)
    _submit_with_feedback(curator_id, artist, "Sarki 1", FEEDBACK_INTRO)
    _submit_with_feedback(curator_id, artist, "Sarki 2", FEEDBACK_PLAIN)

    before = accounts.get_user(artist["id"])["credits"]
    feedback_digest.synthesize(accounts.get_user(artist["id"]))
    after = accounts.get_user(artist["id"])["credits"]

    assert after == before - feedback_digest.DIGEST_COST


def test_synthesize_free_for_pro_user(fd_db):
    curator_id, artist = fd_db
    _give_credits(artist["id"], 10)
    _submit_with_feedback(curator_id, artist, "Sarki 1", FEEDBACK_INTRO)
    _submit_with_feedback(curator_id, artist, "Sarki 2", FEEDBACK_PLAIN)

    from datetime import datetime, timedelta, timezone
    until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    accounts.set_pro_until(artist["id"], until)

    before = accounts.get_user(artist["id"])["credits"]
    feedback_digest.synthesize(accounts.get_user(artist["id"]))
    after = accounts.get_user(artist["id"])["credits"]

    assert after == before


def test_synthesize_does_not_charge_on_failure(fd_db):
    curator_id, artist = fd_db
    _give_credits(artist["id"], 10)
    _submit_with_feedback(curator_id, artist, "Tek Sarki", FEEDBACK_PLAIN)

    before = accounts.get_user(artist["id"])["credits"]
    with pytest.raises(ValueError):
        feedback_digest.synthesize(accounts.get_user(artist["id"]))
    after = accounts.get_user(artist["id"])["credits"]

    assert after == before


# --- Fold ile aksan duyarsiz sayim -------------------------------------------

def test_keyword_counting_is_accent_insensitive(fd_db):
    curator_id, artist = fd_db
    _give_credits(artist["id"], 10)
    _submit_with_feedback(curator_id, artist, "Sarki 1", FEEDBACK_ACCENTED)
    _submit_with_feedback(curator_id, artist, "Sarki 2", FEEDBACK_PLAIN)

    digest = feedback_digest.synthesize(accounts.get_user(artist["id"]))

    guzel_entry = next(
        (k for k in digest["top_keywords"] if k["keyword"] == "guzel"), None
    )
    assert guzel_entry is not None
    assert guzel_entry["count"] == 3  # "güzel" x3 (accent stripped -> "guzel")


# --- latest() ----------------------------------------------------------------

def test_latest_returns_none_when_no_digest(fd_db):
    _, artist = fd_db
    assert feedback_digest.latest(artist["id"]) is None


def test_latest_returns_last_synthesized_digest(fd_db):
    curator_id, artist = fd_db
    _give_credits(artist["id"], 10)
    _submit_with_feedback(curator_id, artist, "Sarki 1", FEEDBACK_INTRO)
    _submit_with_feedback(curator_id, artist, "Sarki 2", FEEDBACK_PLAIN)

    produced = feedback_digest.synthesize(accounts.get_user(artist["id"]))
    fetched = feedback_digest.latest(artist["id"])

    assert fetched == produced
