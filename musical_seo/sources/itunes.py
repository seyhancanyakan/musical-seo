"""iTunes Search API istemcisi (anahtarsiz REST). requests, timeout=15, hatada found=False+note."""
from __future__ import annotations

import requests

from musical_seo.models import TrackInfo

_TIMEOUT = 15
_SEARCH_URL = "https://itunes.apple.com/search"


def _not_found(note: str) -> TrackInfo:
    return TrackInfo(source="itunes", found=False, note=note)


def _to_track_info(item: dict) -> TrackInfo:
    release_date = item.get("releaseDate")
    release_date = release_date[:10] if isinstance(release_date, str) else None
    return TrackInfo(
        source="itunes",
        found=True,
        title=item.get("trackName"),
        artist=item.get("artistName"),
        album=item.get("collectionName"),
        isrc=None,
        release_date=release_date,
        duration_ms=item.get("trackTimeMillis"),
        popularity=None,
        url=item.get("trackViewUrl"),
        extra={
            "trackId": item.get("trackId"),
            "primaryGenreName": item.get("primaryGenreName"),
        },
    )


def _search_raw(term: str) -> list | None:
    params = {"term": term, "entity": "song", "limit": 5, "country": "TR"}
    try:
        resp = requests.get(_SEARCH_URL, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    results = data.get("results")
    return results if isinstance(results, list) else None


def search(query: str) -> TrackInfo:
    results = _search_raw(query)
    if results is None:
        return _not_found("iTunes istegi basarisiz")
    if not results:
        return _not_found("iTunes'ta bulunamadi")
    return _to_track_info(results[0])


def lookup(artist: str, title: str) -> TrackInfo:
    results = _search_raw(f"{artist} {title}")
    if results is None:
        return _not_found("iTunes istegi basarisiz")
    if not results:
        return _not_found("iTunes'ta bulunamadi")
    artist_norm = artist.strip().lower()
    for item in results:
        item_artist = item.get("artistName")
        if isinstance(item_artist, str) and item_artist.strip().lower() == artist_norm:
            return _to_track_info(item)
    return _to_track_info(results[0])
