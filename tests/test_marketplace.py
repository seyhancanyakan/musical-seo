"""marketplace.service saf fonksiyon testleri (network yok)."""
from marketplace.service import (
    compute_deadline,
    curator_quality,
    is_expired,
    parse_playlist_id,
    should_auto_approve,
)


def test_curator_quality_bounds():
    assert curator_quality(0, 0, 0.0) == 0.0
    assert curator_quality(10_000, 100, 1.0) == 100.0
    # tavanlar: daha fazlasi puani artirmaz
    assert curator_quality(999_999, 5000, 1.0) == 100.0


def test_curator_quality_diversity_dominates():
    diverse = curator_quality(0, 50, 0.9)             # cesitli, fansiz
    big_but_flat = curator_quality(10_000, 100, 0.1)  # buyuk ama tek tip
    assert diverse > big_but_flat


def test_should_auto_approve_thresholds():
    assert should_auto_approve(20, 0.25, 20.0)
    assert should_auto_approve(47, 0.277, 25.6)     # gercek ornek: "Türk" playlist'i
    assert not should_auto_approve(19, 0.9, 90.0)   # az parca
    assert not should_auto_approve(50, 0.2, 90.0)   # dusuk cesitlilik
    assert not should_auto_approve(50, 0.5, 19.9)   # dusuk kalite


def test_compute_deadline_adds_72h():
    assert compute_deadline("2026-07-04T10:00:00+00:00") == "2026-07-07T10:00:00+00:00"


def test_is_expired():
    assert is_expired("2026-07-04T10:00:00+00:00", "2026-07-04T10:00:01+00:00")
    assert not is_expired("2026-07-04T10:00:00+00:00", "2026-07-04T09:59:59+00:00")


def test_parse_playlist_id():
    assert parse_playlist_id("14500506743") == "14500506743"
    assert parse_playlist_id("https://www.deezer.com/playlist/14500506743") == "14500506743"
    assert parse_playlist_id("https://www.deezer.com/tr/playlist/123?utm=x") == "123"
    assert parse_playlist_id("https://ornek.com/liste/5") is None
    assert parse_playlist_id("abc") is None
