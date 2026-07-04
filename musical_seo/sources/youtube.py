"""YouTube Data API v3 istemcisi — YOUTUBE_API_KEY opsiyonel.

- lookup(artist, title): anahtar yoksa TrackInfo(found=False, note=...) doner.
  Anahtar varsa search.list ile ilk video bulunur, sonra videos.list ile
  statistics/snippet cekilir; found=True TrackInfo doldurulur.
- Kota asimi veya HTTP/ag hatasi durumunda exception atmaz, found=False + note doner.
"""
from __future__ import annotations

import os
from typing import Any

import requests

from musical_seo import envutil
from musical_seo.models import TrackInfo

envutil.load_env()

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_TIMEOUT = 15

_NO_KEY_NOTE = "YouTube API anahtari yok (opsiyonel)"


def _search_video_id(artist: str, title: str, api_key: str) -> str | None:
    try:
        response = requests.get(
            _SEARCH_URL,
            params={
                "part": "snippet",
                "type": "video",
                "maxResults": 5,
                "q": f"{artist} {title}",
                "key": api_key,
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    items = payload.get("items") or []
    if not items:
        return None

    video_id = ((items[0].get("id")) or {}).get("videoId")
    return video_id


def _fetch_video_details(video_id: str, api_key: str) -> dict[str, Any] | None:
    try:
        response = requests.get(
            _VIDEOS_URL,
            params={
                "part": "statistics,snippet",
                "id": video_id,
                "key": api_key,
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    items = payload.get("items") or []
    return items[0] if items else None


def lookup(artist: str, title: str) -> TrackInfo:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return TrackInfo(source="youtube", found=False, note=_NO_KEY_NOTE)

    video_id = _search_video_id(artist, title, api_key)
    if not video_id:
        return TrackInfo(source="youtube", found=False, note="YouTube aramasinda sonuc bulunamadi")

    video = _fetch_video_details(video_id, api_key)
    if not video:
        return TrackInfo(source="youtube", found=False, note="YouTube video detayi alinamadi")

    snippet = video.get("snippet") or {}
    statistics = video.get("statistics") or {}

    view_count_raw = statistics.get("viewCount")
    try:
        view_count = int(view_count_raw) if view_count_raw is not None else None
    except (TypeError, ValueError):
        view_count = None

    return TrackInfo(
        source="youtube",
        found=True,
        title=snippet.get("title"),
        artist=snippet.get("channelTitle"),
        popularity=None,
        url=f"https://www.youtube.com/watch?v={video_id}",
        extra={
            "views": view_count,
            "videoId": video_id,
            "tags": snippet.get("tags") or [],
        },
    )
