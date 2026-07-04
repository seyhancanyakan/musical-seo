"""YouTube Data API v3 istemcisi — YOUTUBE_API_KEY opsiyonel.

- lookup(artist, title): anahtar yoksa TrackInfo(found=False, note=...) doner.
  Anahtar varsa search.list ile ilk video bulunur, sonra videos.list ile
  statistics/snippet cekilir; found=True TrackInfo doldurulur.
- Kota asimi veya HTTP/ag hatasi durumunda exception atmaz, found=False + note doner.
- KOTA BEKCISI: gunluk birim sayaci (data/youtube_quota.json). Tavan
  (YOUTUBE_DAILY_CAP, varsayilan 9500 — 10k'nin altinda guvenli marj) asilacaksa
  API HIC CAGRILMAZ. YouTube Data API aşimda ucret ISTEMEZ (sert tavan, 403 doner),
  bu bekci yine de fazladan koruma + audit'i temiz tutar.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from musical_seo import envutil
from musical_seo.models import TrackInfo

envutil.load_env()

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_TIMEOUT = 15

_NO_KEY_NOTE = "YouTube API anahtari yok (opsiyonel)"
_QUOTA_NOTE = "YouTube kota bekcisi: gunluk limite yaklasildi, cagri atlandi"

# YouTube Data API v3 birim maliyetleri.
_SEARCH_COST = 100
_DETAILS_COST = 1
_DEFAULT_CAP = 9500  # 10.000'in altinda guvenli marj
_QUOTA_PATH = Path(__file__).resolve().parents[2] / "data" / "youtube_quota.json"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _daily_cap() -> int:
    try:
        return int(os.environ.get("YOUTUBE_DAILY_CAP", _DEFAULT_CAP))
    except (TypeError, ValueError):
        return _DEFAULT_CAP


def _load_quota() -> dict:
    try:
        data = json.loads(_QUOTA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if data.get("date") != _today():
        return {"date": _today(), "units": 0}
    return {"date": data["date"], "units": int(data.get("units", 0))}


def _can_spend(units: int) -> bool:
    return _load_quota()["units"] + units <= _daily_cap()


def _spend(units: int) -> None:
    q = _load_quota()
    q["units"] += units
    try:
        _QUOTA_PATH.parent.mkdir(parents=True, exist_ok=True)
        _QUOTA_PATH.write_text(json.dumps(q), encoding="utf-8")
    except OSError:
        pass


def units_used_today() -> int:
    """Bugun harcanan YouTube API birimi (izleme/hata ayiklama icin)."""
    return _load_quota()["units"]


def _search_video_id(artist: str, title: str, api_key: str) -> str | None:
    if not _can_spend(_SEARCH_COST):
        return None
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

    _spend(_SEARCH_COST)
    items = payload.get("items") or []
    if not items:
        return None

    video_id = ((items[0].get("id")) or {}).get("videoId")
    return video_id


def _fetch_video_details(video_id: str, api_key: str) -> dict[str, Any] | None:
    if not _can_spend(_DETAILS_COST):
        return None
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

    _spend(_DETAILS_COST)
    items = payload.get("items") or []
    return items[0] if items else None


def lookup(artist: str, title: str) -> TrackInfo:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return TrackInfo(source="youtube", found=False, note=_NO_KEY_NOTE)

    # Kota bekcisi: tavan asilacaksa API'yi hic cagirma.
    if not _can_spend(_SEARCH_COST):
        return TrackInfo(source="youtube", found=False, note=_QUOTA_NOTE)

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
