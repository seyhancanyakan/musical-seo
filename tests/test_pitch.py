"""pitch.build_message saf sablon testleri (network yok)."""
from musical_seo.models import PlaylistMatch
from musical_seo.pitch import build_message


def _match(**kw) -> PlaylistMatch:
    base = dict(
        source="deezer",
        playlist_id="1",
        title="Turkce Rock Seckisi",
        url="https://www.deezer.com/playlist/1",
    )
    base.update(kw)
    return PlaylistMatch(**base)


def test_message_mentions_playlist_and_artist():
    msg = build_message("Duman", "Senden Daha Guzel", _match())
    assert "Turkce Rock Seckisi" in msg
    assert "Duman" in msg
    assert "Senden Daha Guzel" in msg


def test_at_most_three_matched_artists_named():
    m = _match(matched_artists=["A1", "A2", "A3", "A4", "A5"])
    msg = build_message("Duman", "Sarki", m)
    assert "A1, A2, A3" in msg
    assert "A4" not in msg
    assert "5 sanatciyla" in msg  # toplam sayi yine de anilir


def test_empty_matched_artists_uses_generic_hook():
    msg = build_message("Duman", "Sarki", _match(matched_artists=[]))
    assert "seckini cok begendim" in msg


def test_track_url_included_when_given():
    msg = build_message("Duman", "Sarki", _match(), track_url="https://dz.example/t/9")
    assert "https://dz.example/t/9" in msg
    msg_without = build_message("Duman", "Sarki", _match())
    assert "Dinlemek icin" not in msg_without
