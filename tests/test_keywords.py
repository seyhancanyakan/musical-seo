"""musical_seo.keywords.build_seeds icin testler (network YOK, saf fonksiyon)."""
from __future__ import annotations

from musical_seo.keywords import build_seeds


def test_build_seeds_returns_six_seeds_in_order():
    # Arrange
    artist = "Tarkan"
    title = "Kuzu Kuzu"

    # Act
    seeds = build_seeds(artist, title)

    # Assert
    assert seeds == [
        "Tarkan",
        "Tarkan Kuzu Kuzu",
        "Kuzu Kuzu",
        "Kuzu Kuzu sozleri",
        "Tarkan Kuzu Kuzu lyrics",
        "Kuzu Kuzu sarki",
    ]
    assert len(seeds) == 6


def test_build_seeds_includes_a_sozleri_seed():
    # Arrange
    artist = "Tarkan"
    title = "Kuzu Kuzu"

    # Act
    seeds = build_seeds(artist, title)

    # Assert
    assert any("sozleri" in seed for seed in seeds)


def test_build_seeds_skips_blank_title():
    # Arrange
    artist = "Tarkan"
    title = "   "

    # Act
    seeds = build_seeds(artist, title)

    # Assert
    assert "" not in seeds
    for seed in seeds:
        assert seed != ""
        assert seed == seed.strip()


def test_build_seeds_skips_blank_artist():
    # Arrange
    artist = ""
    title = "Kuzu Kuzu"

    # Act
    seeds = build_seeds(artist, title)

    # Assert
    assert "" not in seeds
    for seed in seeds:
        assert seed != ""
        assert seed == seed.strip()
