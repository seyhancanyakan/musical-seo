"""musical_seo.contacts.extract testleri (network YOK)."""
from __future__ import annotations

from musical_seo.contacts import extract


def test_extract_email_and_instagram_url():
    text = ("Submit your music: Curator@Playlist.com | "
            "follow https://instagram.com/flyingfingers")
    result = extract(text)
    assert result["emails"] == ["curator@playlist.com"]
    assert result["instagram"] == ["flyingfingers"]


def test_extract_ig_handle_shorthand():
    result = extract("kabul icin IG: @lux.music yaz")
    assert "lux.music" in result["instagram"]


def test_extract_linktree_and_form_links():
    text = "submissions -> https://linktr.ee/oceanify ve https://forms.gle/abc123"
    result = extract(text)
    assert "https://linktr.ee/oceanify" in result["links"]
    assert "https://forms.gle/abc123" in result["links"]


def test_extract_ignores_instagram_post_paths():
    result = extract("bak: https://instagram.com/p/Xyz123")
    assert result["instagram"] == []


def test_extract_empty_text():
    assert extract("") == {"emails": [], "instagram": [], "links": []}
