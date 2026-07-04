"""playlists.score_playlist saf skor testleri (network yok)."""
from musical_seo.playlists import score_playlist


def test_more_matched_artists_beats_fans():
    # 3 eslesme + 0 fan, 1 eslesme + tavan fan'i gecer
    assert score_playlist(3, 0, False) > score_playlist(1, 200_000, False)


def test_fan_component_capped():
    assert score_playlist(1, 200_000, False) == score_playlist(1, 5_000_000, False)


def test_contains_track_bonus():
    base = score_playlist(2, 1000, False)
    with_track = score_playlist(2, 1000, True)
    assert with_track == base + 2.0


def test_zero_everything():
    assert score_playlist(0, 0, False) == 0.0


def test_negative_fans_clamped():
    assert score_playlist(1, -50, False) == score_playlist(1, 0, False)


def test_ordering_example():
    scores = [
        score_playlist(4, 50_000, True),   # en iyi
        score_playlist(2, 100_000, False),
        score_playlist(1, 10_000, False),  # en zayif
    ]
    assert scores == sorted(scores, reverse=True)
