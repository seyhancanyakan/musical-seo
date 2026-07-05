"""Curator iletisim ayiklama — SADECE kendi yayinladiklari bilgiden.

Kaynak: playlist aciklamalari (Spotify/Deezer) + sahibin diger listelerinin
aciklamalari. Ciddi curator'lar buraya bilerek iletisim yazar ("submit:
mail@x.com", Instagram, Linktree, SubmitHub). Kazima/tahmin YOK; aciklamada
yoksa yok kabul edilir — o durumda panel "platforma davet et" akisina duser.

extract(text): metinden e-posta / instagram / link ayiklar.
for_playlist(source, playlist_id, owner_id): kaynaga gore aciklamalari
toplayip ayiklar; hicbir sey bulunamazsa None doner (istisna atmaz).
"""
from __future__ import annotations

import re
from typing import Any

import requests

from musical_seo.sources import spotify as spotify_source

_TIMEOUT = 15
_DEEZER_API = "https://api.deezer.com"

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}")
_IG_URL_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]{2,30})", re.IGNORECASE)
_IG_HANDLE_RE = re.compile(
    r"(?:\big\b|\binsta(?:gram)?\b)\s*[:\-]?\s*@([A-Za-z0-9_.]{2,30})",
    re.IGNORECASE,
)
_LINK_RE = re.compile(
    r"https?://(?:www\.)?(?:linktr\.ee|submithub\.com|tunemymusic|"
    r"beacons\.ai|lnk\.bio|linkin\.bio|forms\.gle|docs\.google\.com/forms)"
    r"[^\s\"'<>]*",
    re.IGNORECASE,
)

# Instagram URL'lerinde kullanici adi olmayan yollar
_IG_NON_PROFILE = {"p", "reel", "stories", "explore", "accounts"}


def extract(text: str) -> dict[str, list[str]]:
    """Metinden iletisim sinyalleri. Anahtarlar: emails, instagram, links."""
    if not text:
        return {"emails": [], "instagram": [], "links": []}

    emails = sorted({m.lower() for m in _EMAIL_RE.findall(text)})

    handles: set[str] = set()
    for m in _IG_URL_RE.findall(text):
        if m.lower() not in _IG_NON_PROFILE:
            handles.add(m.lower())
    for m in _IG_HANDLE_RE.findall(text):
        handles.add(m.lower())

    links = sorted({m.rstrip(".,)") for m in _LINK_RE.findall(text)})

    return {"emails": emails, "instagram": sorted(handles), "links": links}


def _merge(base: dict[str, list[str]], extra: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        key: sorted(set(base[key]) | set(extra[key]))
        for key in ("emails", "instagram", "links")
    }


def _has_any(contacts: dict[str, list[str]]) -> bool:
    return any(contacts.values())


def _deezer_playlist_description(playlist_id: str) -> str:
    try:
        resp = requests.get(
            f"{_DEEZER_API}/playlist/{playlist_id}",
            params={"limit": 1},
            timeout=_TIMEOUT,
        )
        data = resp.json() if resp.status_code == 200 else {}
        if isinstance(data, dict) and not data.get("error"):
            return data.get("description") or ""
    except (requests.RequestException, ValueError):
        pass
    return ""


def for_playlist(
    source: str, playlist_id: str, owner_id: str | None
) -> dict[str, Any] | None:
    """Playlist + (gerekirse) sahibin diger listelerinden iletisim topla.

    Donen sekil: {"emails": [...], "instagram": [...], "links": [...],
    "source_hint": "description" | "owner_playlists"}. Bos ise None.
    """
    contacts = {"emails": [], "instagram": [], "links": []}
    hint = None

    if source == "spotify":
        contacts = _merge(contacts, extract(spotify_source.playlist_description(playlist_id)))
        if _has_any(contacts):
            hint = "description"
        elif owner_id:
            for pl in spotify_source.user_playlists(owner_id, limit=10):
                contacts = _merge(contacts, extract(pl["description"]))
            if _has_any(contacts):
                hint = "owner_playlists"
    elif source == "deezer":
        contacts = _merge(contacts, extract(_deezer_playlist_description(playlist_id)))
        if _has_any(contacts):
            hint = "description"

    if not _has_any(contacts):
        return None
    return {**contacts, "source_hint": hint}
