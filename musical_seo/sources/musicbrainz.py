"""MusicBrainz WS/2 istemcisi — otoriter metadata + ISRC + ilk-yayin tarihi.

Anahtar GEREKMEZ. Kurallar: aciklayici User-Agent zorunlu, ~1 istek/sn rate limit.
MusicBrainz surum karisikligini cozer: her platformun kendi eslesmesi farkli sürüm
(farkli tarih/ISRC) getirebiliyor; MusicBrainz'in canonical recording'i otorite kabul
edilir (ISRC + first-release-date). audit consistency bunu referans alir.

- lookup(artist, title): en iyi eslesen recording'i bulur, ISRC'yi ikinci cagriyla
  ceker. Bulunamazsa / hata / rate-limit durumunda exception atmaz, found=False doner.
"""
from __future__ import annotations

import time

import requests

from musical_seo.models import TrackInfo

_BASE = "https://musicbrainz.org/ws/2"
# MusicBrainz aciklayici User-Agent ISTER (yoksa 403). Iletisim + uygulama adi.
_HEADERS = {"User-Agent": "musical-seo/0.1 (https://github.com/musical-seo; audit)"}
_TIMEOUT = 15
_RATE_SLEEP = 1.1  # ~1 istek/sn kurali


def _search_recording(artist: str, title: str) -> dict | None:
    query = f'artist:"{artist}" AND recording:"{title}"'
    try:
        r = requests.get(
            f"{_BASE}/recording",
            params={"query": query, "fmt": "json", "limit": 5},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        recordings = r.json().get("recordings") or []
    except (requests.RequestException, ValueError):
        return None
    if not recordings:
        return None
    # En yuksek skorlu (MB arama skoru) eslesme.
    recordings.sort(key=lambda rec: int(rec.get("score", 0)), reverse=True)
    return recordings[0]


def _fetch_isrc(recording_id: str) -> str | None:
    try:
        r = requests.get(
            f"{_BASE}/recording/{recording_id}",
            params={"fmt": "json", "inc": "isrcs"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        isrcs = r.json().get("isrcs") or []
    except (requests.RequestException, ValueError):
        return None
    return isrcs[0] if isrcs else None


def _artist_name(rec: dict) -> str | None:
    credits = rec.get("artist-credit") or []
    if credits and isinstance(credits[0], dict):
        artist = credits[0].get("artist") or {}
        return artist.get("name") or credits[0].get("name")
    return None


def lookup(artist: str, title: str) -> TrackInfo:
    rec = _search_recording(artist, title)
    if not rec:
        return TrackInfo(source="musicbrainz", found=False,
                         note="MusicBrainz'de kayit bulunamadi")

    recording_id = rec.get("id")
    time.sleep(_RATE_SLEEP)  # ikinci cagri oncesi rate limit nezaketi
    isrc = _fetch_isrc(recording_id) if recording_id else None

    # first-release-date: recording seviyesinde ya da ilk release'te.
    release_date = rec.get("first-release-date")
    if not release_date:
        releases = rec.get("releases") or []
        dates = [rl.get("date") for rl in releases if rl.get("date")]
        release_date = min(dates) if dates else None

    return TrackInfo(
        source="musicbrainz",
        found=True,
        title=rec.get("title"),
        artist=_artist_name(rec),
        isrc=isrc,
        release_date=release_date,
        url=f"https://musicbrainz.org/recording/{recording_id}" if recording_id else None,
        extra={"mbid": recording_id, "score": rec.get("score")},
    )
