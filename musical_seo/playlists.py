"""Playlist eslestirme — Deezer uzerinden benzer-sanatci playlist kesfi (anahtarsiz).

Akis: sanatciyi Deezer'da coz -> benzer sanatcilar (/artist/{id}/related) ->
havuzdaki isimlerle playlist aramasi -> her aday playlist'in parcalarini cek ->
havuzla kesisime gore skorla. Cikti: pitch onceligine gore sirali PlaylistMatch listesi.
Kutuphane modulu: print yok; network hatalari sessizce atlanir (aday dusurulur).
"""
from __future__ import annotations

import time
from typing import Any

import requests

from musical_seo.models import PlaylistMatch

_API = "https://api.deezer.com"
_HEADERS = {"User-Agent": "musical-seo/0.1"}
_SLEEP = 0.15          # Deezer kota nezaketi (50 istek / 5 sn siniri var)
_FAN_CAP = 200_000     # fan katkisi tavani (dev listeler skoru domine etmesin)


def _get(path: str, **params: Any) -> dict:
    try:
        resp = requests.get(f"{_API}{path}", params=params, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and not data.get("error"):
            return data
    except Exception:
        pass
    return {}


def _artist_id(artist: str) -> tuple[int | None, str]:
    data = _get("/search/artist", q=artist, limit=1)
    items = data.get("data") or []
    if not items:
        return None, artist
    return items[0].get("id"), items[0].get("name") or artist


def related_artists(artist_id: int, limit: int = 10) -> list[str]:
    data = _get(f"/artist/{artist_id}/related", limit=limit)
    names = [a.get("name", "") for a in (data.get("data") or [])]
    return [n for n in names if n][:limit]


def score_playlist(matched_count: int, fans: int, contains_track: bool) -> float:
    """SAF skor: eslesen benzer-sanatci sayisi agir basar (x10), fan sayisi
    tavanli dogrusal katki (0-10), sarki zaten listedeyse +2 (uyum kaniti)."""
    fan_component = min(max(fans, 0), _FAN_CAP) / (_FAN_CAP / 10)
    return matched_count * 10 + fan_component + (2.0 if contains_track else 0.0)


def find_playlists(
    artist: str,
    title: str,
    limit: int = 15,
    per_query: int = 8,
    max_candidates: int = 20,
) -> list[PlaylistMatch]:
    """Sanatci+sarki icin pitch onceligine gore sirali playlist adaylari."""
    artist_id, canonical = _artist_id(artist)
    pool: list[str] = [canonical]
    if artist_id:
        time.sleep(_SLEEP)
        pool.extend(related_artists(artist_id, limit=10))

    # Aday toplama: havuzun ilk 5 ismiyle playlist aramasi, id bazinda tekilsiz.
    candidates: dict[int, dict] = {}
    for name in pool[:5]:
        time.sleep(_SLEEP)
        data = _get("/search/playlist", q=name, limit=per_query)
        for pl in data.get("data") or []:
            pid = pl.get("id")
            nb_tracks = pl.get("nb_tracks") or 0
            if not pid or pid in candidates or not 10 <= nb_tracks <= 1000:
                continue
            candidates[pid] = pl
            if len(candidates) >= max_candidates:
                break
        if len(candidates) >= max_candidates:
            break

    canonical_cf = canonical.casefold()
    title_cf = title.casefold()

    matches: list[PlaylistMatch] = []
    for pid, pl in candidates.items():
        time.sleep(_SLEEP)
        detail = _get(f"/playlist/{pid}")
        tracks = ((detail.get("tracks") or {}).get("data")) or []
        if not tracks:
            extra = _get(f"/playlist/{pid}/tracks", limit=100)
            tracks = extra.get("data") or []
        if not tracks:
            continue

        track_artists_cf = {
            (t.get("artist") or {}).get("name", "").casefold() for t in tracks
        }
        track_artists_cf.discard("")
        matched = sorted({p for p in pool if p.casefold() in track_artists_cf})
        contains = any(
            title_cf == (t.get("title") or "").casefold()
            and canonical_cf == (t.get("artist") or {}).get("name", "").casefold()
            for t in tracks
        )
        if not matched and not contains:
            continue

        fans = int(detail.get("fans") or 0)
        creator = detail.get("creator") or pl.get("user") or {}
        matches.append(
            PlaylistMatch(
                source="deezer",
                playlist_id=str(pid),
                title=pl.get("title") or "",
                url=pl.get("link") or f"https://www.deezer.com/playlist/{pid}",
                fans=fans,
                track_count=int(detail.get("nb_tracks") or pl.get("nb_tracks") or 0),
                matched_artists=matched,
                contains_track=contains,
                score=score_playlist(len(matched), fans, contains),
                owner_name=creator.get("name"),
                owner_id=str(creator["id"]) if creator.get("id") else None,
            )
        )

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:limit]
