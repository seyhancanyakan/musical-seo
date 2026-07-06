"""Sarkilarim kutuphanesi testleri — network YOK."""
from __future__ import annotations

import pytest

from marketplace import db, tracks
from musical_seo.models import TrackInfo


@pytest.fixture()
def trk_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    return None


def _found(artist, title, url="https://www.deezer.com/track/1"):
    return TrackInfo(source="deezer", found=True, title=title, artist=artist, url=url)


def _not_found(artist, title):
    return TrackInfo(source="deezer", found=False, title=None, artist=None, url=None)


def test_add_track_resolves_and_dedupes(trk_db, monkeypatch):
    # Cozumleyici resmi yazimi dondurur -> varyasyonlar tekillesir
    monkeypatch.setattr(
        tracks.deezer, "lookup", lambda a, t: _found("Duman", "Senden Daha Güzel")
    )
    t1 = tracks.add_track(1, "duman", "senden daha guzel")
    assert t1["artist"] == "Duman"
    assert t1["track_url"]
    t2 = tracks.add_track(1, "DUMAN", "SENDEN DAHA GUZEL")
    assert t2["id"] == t1["id"]  # ayni kayit, kopya yok
    assert len(tracks.list_tracks(1)) == 1


def test_add_track_rejects_wrong_artist(trk_db, monkeypatch):
    """Serbest-metin fallback yanlis sanatciyi getirirse kayit REDDEDILIR
    (gercek vaka: 'Seyhan Canyakan - Yar dedim' -> Sebnem Kisaparmak / Yar)."""
    monkeypatch.setattr(
        tracks.deezer, "lookup",
        lambda a, t: _found("Şebnem Kısaparmak", "Yar"),
    )
    with pytest.raises(ValueError, match="farklı sanatçıya ait"):
        tracks.add_track(1, "Seyhan Canyakan", "Yar dedim")
    assert tracks.list_tracks(1) == []


def test_add_track_accent_tolerant_artist_match(trk_db, monkeypatch):
    """Aksan/buyuk-kucuk farki eslesmeyi bozmaz: 'sebnem kisaparmak' ==
    'Şebnem Kısaparmak'."""
    monkeypatch.setattr(
        tracks.deezer, "lookup",
        lambda a, t: _found("Şebnem Kısaparmak", "Yar"),
    )
    t = tracks.add_track(1, "sebnem kisaparmak", "yar")
    assert t["artist"] == "Şebnem Kısaparmak"


def test_add_track_not_found_raises_turkish(trk_db, monkeypatch):
    monkeypatch.setattr(tracks.deezer, "lookup", _not_found)
    monkeypatch.setattr(tracks.spotify_source, "lookup", _not_found)
    with pytest.raises(ValueError, match="bulunamadı"):
        tracks.add_track(1, "Bilinmeyen", "Demo Sarki")


def test_spotify_fallback(trk_db, monkeypatch):
    monkeypatch.setattr(tracks.deezer, "lookup", _not_found)
    monkeypatch.setattr(
        tracks.spotify_source, "lookup",
        lambda a, t: TrackInfo(source="spotify", found=True, title=t, artist=a,
                               url="https://open.spotify.com/track/x"),
    )
    t = tracks.add_track(1, "Sanatci", "Sarki")
    assert t["source"] == "spotify"


def test_delete_track_ownership(trk_db, monkeypatch):
    monkeypatch.setattr(tracks.deezer, "lookup", lambda a, t: _found(a, t))
    t = tracks.add_track(1, "A", "S")
    assert tracks.delete_track(2, t["id"]) is False  # baskasinin kaydi silinemez
    assert tracks.delete_track(1, t["id"]) is True
    assert tracks.list_tracks(1) == []
