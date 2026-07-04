"""Spotify Web API istemcisi (Client Credentials flow).

- resolve(query_or_url): "open.spotify.com/track/<id>" veya "spotify:track:<id>" ise
  track'i ID ile ceker; degilse "Sanatci - Sarki" kalibini ayristirip artist:/track:
  alanli aramayi dener, bulunamazsa serbest metin aramasina duser.
- lookup(artist, title): dogrudan artist:/track: aramasi ile en iyi eslesmeyi bulur.
- API anahtari (SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET) yoksa veya herhangi bir
  agdaki/HTTP hata durumunda exception atmaz; TrackInfo(found=False, note=...) doner.
- Token modul seviyesinde cache'lenir (expires_at, 60 sn guvenlik payi).
"""
from __future__ import annotations

import os
import re
import time
from typing import Any

import requests

from musical_seo import envutil
from musical_seo.models import TrackInfo

envutil.load_env()

_TOKEN_URL = "https://accounts.spotify.com/api/token"
_SEARCH_URL = "https://api.spotify.com/v1/search"
_TRACK_URL = "https://api.spotify.com/v1/tracks/{track_id}"
_TIMEOUT = 15
_TOKEN_EXPIRY_SAFETY_SECONDS = 60

_NO_KEY_NOTE = "Spotify API anahtari yok (.env)"

_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}

_TRACK_ID_RE = re.compile(
    r"open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([A-Za-z0-9]+)"
)
_TRACK_URI_RE = re.compile(r"spotify:track:([A-Za-z0-9]+)")


def _extract_track_id(query_or_url: str) -> str | None:
    match = _TRACK_ID_RE.search(query_or_url)
    if match:
        return match.group(1)
    match = _TRACK_URI_RE.search(query_or_url)
    if match:
        return match.group(1)
    return None


def _get_access_token() -> str | None:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    now = time.time()
    cached_token = _token_cache.get("access_token")
    if cached_token and now < _token_cache.get("expires_at", 0.0):
        return cached_token

    try:
        response = requests.post(
            _TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in", 0)
    if not access_token:
        return None

    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = now + expires_in - _TOKEN_EXPIRY_SAFETY_SECONDS
    return access_token


def _track_json_to_info(track: dict[str, Any]) -> TrackInfo:
    artists = track.get("artists") or []
    artist_names = [a.get("name") for a in artists if a.get("name")]
    album = track.get("album") or {}
    external_ids = track.get("external_ids") or {}
    external_urls = track.get("external_urls") or {}

    return TrackInfo(
        source="spotify",
        found=True,
        title=track.get("name"),
        artist=artist_names[0] if artist_names else None,
        album=album.get("name"),
        isrc=external_ids.get("isrc"),
        release_date=album.get("release_date"),
        duration_ms=track.get("duration_ms"),
        popularity=track.get("popularity"),
        url=external_urls.get("spotify"),
        extra={"id": track.get("id"), "artists": artist_names},
    )


def _fetch_track_by_id(track_id: str, access_token: str) -> TrackInfo:
    try:
        response = requests.get(
            _TRACK_URL.format(track_id=track_id),
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        track = response.json()
    except (requests.RequestException, ValueError) as exc:
        return TrackInfo(source="spotify", found=False, note=f"Spotify istegi basarisiz: {exc}")

    return _track_json_to_info(track)


def _search(q: str, access_token: str) -> dict[str, Any] | None:
    try:
        response = requests.get(
            _SEARCH_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"q": q, "type": "track", "limit": 1},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    items = ((payload.get("tracks") or {}).get("items")) or []
    return items[0] if items else None


def _search_with_fallback(primary_q: str, fallback_q: str | None, access_token: str) -> TrackInfo:
    track = _search(primary_q, access_token)
    if not track and fallback_q:
        track = _search(fallback_q, access_token)

    if not track:
        return TrackInfo(source="spotify", found=False, note="Spotify aramasinda sonuc bulunamadi")

    return _track_json_to_info(track)


def resolve(query_or_url: str) -> TrackInfo:
    access_token = _get_access_token()
    if not access_token:
        return TrackInfo(source="spotify", found=False, note=_NO_KEY_NOTE)

    track_id = _extract_track_id(query_or_url)
    if track_id:
        return _fetch_track_by_id(track_id, access_token)

    if " - " in query_or_url:
        artist, _, title = query_or_url.partition(" - ")
        artist = artist.strip()
        title = title.strip()
        structured_q = f'artist:"{artist}" track:"{title}"'
        return _search_with_fallback(structured_q, query_or_url, access_token)

    return _search_with_fallback(query_or_url, None, access_token)


def lookup(artist: str, title: str) -> TrackInfo:
    access_token = _get_access_token()
    if not access_token:
        return TrackInfo(source="spotify", found=False, note=_NO_KEY_NOTE)

    structured_q = f'artist:"{artist}" track:"{title}"'
    free_text_q = f"{artist} {title}"
    return _search_with_fallback(structured_q, free_text_q, access_token)
