"""Deezer API istemcisi (anahtarsiz REST). requests, timeout=15, hatada found=False+note."""
from __future__ import annotations

import requests

from musical_seo.models import TrackInfo

_TIMEOUT = 15
_SEARCH_URL = "https://api.deezer.com/search"
_TRACK_URL = "https://api.deezer.com/track/{id}"


def _not_found(note: str) -> TrackInfo:
    return TrackInfo(source="deezer", found=False, note=note)


def _fetch_track_detail(track_id: int | str) -> dict | None:
    try:
        resp = requests.get(_TRACK_URL.format(id=track_id), timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict) or data.get("error"):
        return None
    return data


def _to_track_info(detail: dict) -> TrackInfo:
    album = detail.get("album") or {}
    artist = detail.get("artist") or {}
    duration = detail.get("duration")
    duration_ms = int(duration) * 1000 if isinstance(duration, (int, float)) else None
    return TrackInfo(
        source="deezer",
        found=True,
        title=detail.get("title"),
        artist=artist.get("name"),
        album=album.get("title"),
        isrc=detail.get("isrc"),
        release_date=detail.get("release_date"),
        duration_ms=duration_ms,
        popularity=detail.get("rank"),
        url=detail.get("link"),
        extra={"id": detail.get("id")},
    )


def _search_raw(params: dict) -> list | None:
    try:
        resp = requests.get(_SEARCH_URL, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    results = data.get("data")
    return results if isinstance(results, list) else None


def _first_result_to_track_info(results: list | None) -> TrackInfo:
    if not results:
        return _not_found("Deezer'da bulunamadi")
    first = results[0]
    track_id = first.get("id") if isinstance(first, dict) else None
    if track_id is None:
        return _not_found("Deezer'da bulunamadi")
    detail = _fetch_track_detail(track_id)
    if detail is None:
        return _not_found("Deezer detay istegi basarisiz")
    return _to_track_info(detail)


def search(query: str) -> TrackInfo:
    results = _search_raw({"q": query, "limit": 5})
    if results is None:
        return _not_found("Deezer istegi basarisiz")
    return _first_result_to_track_info(results)


def lookup(artist: str, title: str) -> TrackInfo:
    q = f'artist:"{artist}" track:"{title}"'
    results = _search_raw({"q": q, "limit": 5})
    if results is None:
        return _not_found("Deezer istegi basarisiz")
    if not results:
        results = _search_raw({"q": f"{artist} {title}", "limit": 5})
        if results is None:
            return _not_found("Deezer istegi basarisiz")
    return _first_result_to_track_info(results)
