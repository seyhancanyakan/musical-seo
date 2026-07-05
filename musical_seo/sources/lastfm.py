"""Last.fm API istemcisi — dinleyici/calma sayisi + etiketler (yasal, resmi API).

API anahtari gerekir: LASTFM_API_KEY (.env). Ucretsiz: https://www.last.fm/api/account/create
Anahtar yoksa veya herhangi bir ag/HTTP hatasinda exception atmaz,
TrackInfo(found=False, note=...) doner (spotify/musicbrainz ile ayni sozlesme).

Last.fm'in katkisi: platformlardan bagimsiz gercek dinlenme sinyali
(listeners + playcount) ve topluluk etiketleri. ISRC/yayin tarihi VERMEZ;
o alanlar icin otorite MusicBrainz'dir.

- lookup(artist, title): track.getInfo (autocorrect=1) ile en iyi eslesme.
"""
from __future__ import annotations

import os

import requests

from musical_seo import envutil
from musical_seo.models import TrackInfo

envutil.load_env()

_BASE = "https://ws.audioscrobbler.com/2.0/"
_TIMEOUT = 15

_NO_KEY_NOTE = "Last.fm API anahtari yok (.env: LASTFM_API_KEY)"


def _to_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def similar_artists(artist: str, limit: int = 10) -> list[str]:
    """Last.fm artist.getSimilar — benzer sanatci adlari. Kucuk sanatcilarda
    Deezer'in related grafigi bos kalirken Last.fm genelde sonuc verir
    (playlist eslestirme havuzu icin fallback). Anahtar yok / hata -> []."""
    api_key = os.environ.get("LASTFM_API_KEY")
    if not api_key:
        return []
    try:
        r = requests.get(
            _BASE,
            params={
                "method": "artist.getSimilar",
                "api_key": api_key,
                "artist": artist,
                "autocorrect": "1",
                "limit": str(limit),
                "format": "json",
            },
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        items = (r.json().get("similarartists") or {}).get("artist", [])
    except (requests.RequestException, ValueError):
        return []
    names = [a.get("name") for a in items if isinstance(a, dict) and a.get("name")]
    return names[:limit]


def lookup(artist: str, title: str) -> TrackInfo:
    api_key = os.environ.get("LASTFM_API_KEY")
    if not api_key:
        return TrackInfo(source="lastfm", found=False, note=_NO_KEY_NOTE)

    try:
        r = requests.get(
            _BASE,
            params={
                "method": "track.getInfo",
                "api_key": api_key,
                "artist": artist,
                "track": title,
                "autocorrect": "1",
                "format": "json",
            },
            timeout=_TIMEOUT,
        )
        payload = r.json()
    except (requests.RequestException, ValueError):
        return TrackInfo(source="lastfm", found=False, note="Last.fm istegi basarisiz")

    track = payload.get("track")
    if r.status_code != 200 or not isinstance(track, dict):
        note = payload.get("message") or "Last.fm'de kayit bulunamadi"
        return TrackInfo(source="lastfm", found=False, note=note)

    artist_info = track.get("artist") or {}
    album_info = track.get("album") or {}
    duration_ms = _to_int(track.get("duration"))
    listeners = _to_int(track.get("listeners"))
    playcount = _to_int(track.get("playcount"))

    tags = [
        t.get("name")
        for t in (track.get("toptags") or {}).get("tag", [])
        if isinstance(t, dict) and t.get("name")
    ]

    return TrackInfo(
        source="lastfm",
        found=True,
        title=track.get("name"),
        artist=artist_info.get("name") if isinstance(artist_info, dict) else None,
        album=album_info.get("title") if isinstance(album_info, dict) else None,
        duration_ms=duration_ms or None,
        popularity=listeners,  # kaynak olceginde ham deger: Last.fm dinleyici sayisi
        url=track.get("url"),
        extra={"listeners": listeners, "playcount": playcount, "tags": tags[:5]},
    )
