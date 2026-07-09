"""marketplace.tracking testleri: takip edilen ogeler (tracked_items) --
idempotent ekleme, gecersiz kind ValueError, kullanici/tur bazli sorgular,
skor guncelleme. Network YOK, DB tmp_path'e izole (marketplace.db)."""
from __future__ import annotations

import pytest

from marketplace import db, tracking


@pytest.fixture()
def tracking_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


# --- track() ------------------------------------------------------------------

def test_track_creates_row_with_expected_fields(tracking_db):
    row = tracking.track(1, "song", "Artist - Song", label="Ilk Sarkim")
    assert row["user_id"] == 1
    assert row["kind"] == "song"
    assert row["ref"] == "Artist - Song"
    assert row["label"] == "Ilk Sarkim"
    assert row["last_score"] is None
    assert row["last_checked_at"] is None
    assert row["id"] > 0


def test_track_is_idempotent_same_user_kind_ref(tracking_db):
    first = tracking.track(1, "song", "Artist - Song")
    second = tracking.track(1, "song", "Artist - Song", label="ikinci deneme")

    assert first["id"] == second["id"]
    # Ikinci cagri INSERT OR IGNORE oldugu icin label guncellenmez.
    assert second["label"] is None
    assert len(tracking.tracked_for(1)) == 1


def test_track_allows_same_ref_for_different_users(tracking_db):
    tracking.track(1, "song", "Artist - Song")
    tracking.track(2, "song", "Artist - Song")

    assert len(tracking.tracked_for(1)) == 1
    assert len(tracking.tracked_for(2)) == 1


def test_track_invalid_kind_raises_value_error(tracking_db):
    with pytest.raises(ValueError):
        tracking.track(1, "album", "Artist - Album")


@pytest.mark.parametrize("kind", ["song", "artist", "playlist"])
def test_track_accepts_all_allowed_kinds(tracking_db, kind):
    row = tracking.track(1, kind, f"ref-{kind}")
    assert row["kind"] == kind


# --- untrack() ------------------------------------------------------------------

def test_untrack_removes_row_and_returns_true(tracking_db):
    tracking.track(1, "artist", "Some Artist")

    assert tracking.untrack(1, "artist", "Some Artist") is True
    assert tracking.tracked_for(1) == []


def test_untrack_returns_false_when_not_found(tracking_db):
    assert tracking.untrack(1, "artist", "Nobody") is False


# --- tracked_for() / all_tracked() ----------------------------------------------

def test_tracked_for_returns_only_that_user(tracking_db):
    tracking.track(1, "song", "A - A")
    tracking.track(2, "song", "B - B")

    result = tracking.tracked_for(1)
    assert len(result) == 1
    assert result[0]["ref"] == "A - A"


def test_tracked_for_unknown_user_returns_empty(tracking_db):
    assert tracking.tracked_for(999) == []


def test_all_tracked_returns_everyone_when_kind_omitted(tracking_db):
    tracking.track(1, "song", "A - A")
    tracking.track(2, "artist", "Some Artist")
    tracking.track(3, "playlist", "Some Playlist")

    result = tracking.all_tracked()
    assert len(result) == 3


def test_all_tracked_filters_by_kind(tracking_db):
    tracking.track(1, "song", "A - A")
    tracking.track(2, "artist", "Some Artist")

    songs = tracking.all_tracked(kind="song")
    assert len(songs) == 1
    assert songs[0]["kind"] == "song"


def test_all_tracked_empty_db_returns_empty_list(tracking_db):
    assert tracking.all_tracked() == []
    assert tracking.all_tracked(kind="song") == []


# --- update_score() -------------------------------------------------------------

def test_update_score_sets_last_score_and_checked_at(tracking_db):
    row = tracking.track(1, "song", "Artist - Song")
    assert row["last_score"] is None

    tracking.update_score(row["id"], 42.0)

    updated = tracking.tracked_for(1)[0]
    assert updated["last_score"] == 42.0
    assert updated["last_checked_at"] is not None


def test_update_score_overwrites_previous_value(tracking_db):
    row = tracking.track(1, "song", "Artist - Song")
    tracking.update_score(row["id"], 42.0)
    tracking.update_score(row["id"], 55.0)

    updated = tracking.tracked_for(1)[0]
    assert updated["last_score"] == 55.0


# --- import sanity ---------------------------------------------------------------

def test_module_imports_without_network():
    import marketplace.tracking  # noqa: F401
