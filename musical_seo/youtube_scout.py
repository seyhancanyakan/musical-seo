"""YouTube curator scout — muzik-promo kanallarini kesfet.

YouTube'da 'curator' = playlist/mix kanallari. Spotify/Deezer'dan ustunlukleri:
  - GERCEK abone + goruntulenme sayisi (kalite metrigi, public)
  - Kanal About/aciklamasinda sik sik submission iletisimi (yasal — yayinlanmis)

Akis:
  1. Tohum sorgularla kanal aramasi (search.list type=channel) — 100 birim/arama
  2. channels.list ile abone/view/video + aciklama (1 birim)
  3. Aciklamadan iletisim ayikla (email/IG/link)
  4. marketplace.db'ye 'lead' yaz; abone=fans, quality=abone-log, iletisim bulunduysa doldur

KOTA: youtube.py'nin gunluk bekcisini kullanir (YOUTUBE_DAILY_CAP, varsayilan 9500).
Tavan asilacaksa API HIC cagrilmaz. Ucret riski yok.

Kullanim:
    python -m musical_seo.youtube_scout [seeds.txt]
"""
from __future__ import annotations

import math
import os
import sqlite3
import sys
import time

import requests

from marketplace import db
from marketplace.enrich_contacts import extract_contact
from musical_seo import envutil
from musical_seo.sources import youtube as yt

envutil.load_env()

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
_TIMEOUT = 15
_SLEEP = 0.2
_PER_SEED = 15  # tohum basina kanal

DEFAULT_SEEDS = [
    "türkçe pop playlist", "türkçe rap mix", "türkçe rock mix",
    "anadolu rock playlist", "türkçe akustik", "türkçe arabesk mix",
    "turkish music playlist", "türkçe indie",
]


def quality_from(subs: int) -> float:
    return round(min(100.0, math.log10(subs + 1) * 14.0), 1)


def _ensure_columns() -> None:
    conn = sqlite3.connect(db._DB_PATH)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(curators)")}
        for col, typ in (("contact_source", "TEXT"), ("source_url", "TEXT")):
            if col not in cols:
                conn.execute(f"ALTER TABLE curators ADD COLUMN {col} {typ}")
        conn.commit()
    finally:
        conn.close()


def _search_channel_ids(query: str, api_key: str, limit: int) -> list[str]:
    if not yt._can_spend(yt._SEARCH_COST):
        return []
    try:
        r = requests.get(
            _SEARCH_URL,
            params={"part": "snippet", "type": "channel", "maxResults": min(limit, 50),
                    "q": query, "key": api_key},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        payload = r.json()
    except (requests.RequestException, ValueError):
        return []
    yt._spend(yt._SEARCH_COST)
    ids = []
    for item in payload.get("items") or []:
        cid = (item.get("id") or {}).get("channelId")
        if cid:
            ids.append(cid)
    return ids


def _fetch_channels(channel_ids: list[str], api_key: str) -> list[dict]:
    if not channel_ids or not yt._can_spend(1):
        return []
    try:
        r = requests.get(
            _CHANNELS_URL,
            params={"part": "snippet,statistics", "id": ",".join(channel_ids[:50]),
                    "key": api_key},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        payload = r.json()
    except (requests.RequestException, ValueError):
        return []
    yt._spend(1)
    return payload.get("items") or []


def _set_source(curator_id: int, source: str | None, source_url: str) -> None:
    conn = sqlite3.connect(db._DB_PATH)
    try:
        conn.execute(
            "UPDATE curators SET contact_source=?, source_url=? WHERE id=?",
            (source, source_url, curator_id),
        )
        conn.commit()
    finally:
        conn.close()


def _import_channel(ch: dict) -> str:
    cid = ch.get("id") or ""
    if not cid:
        return "skip"
    snippet = ch.get("snippet") or {}
    stats = ch.get("statistics") or {}
    name = (snippet.get("title") or "Bilinmeyen").strip() or "Bilinmeyen"
    desc = snippet.get("description") or ""
    custom = snippet.get("customUrl") or ""
    url = f"https://www.youtube.com/channel/{cid}"
    try:
        subs = int(stats.get("subscriberCount") or 0)
    except (TypeError, ValueError):
        subs = 0
    try:
        videos = int(stats.get("videoCount") or 0)
    except (TypeError, ValueError):
        videos = 0

    contact = extract_contact(f"{name} {desc} {custom}")
    email, source = "", None
    if contact:
        email, src = contact
        source = "youtube_about_" + src.split("_")[-1]

    new_id = db.add_curator(
        name=name, email=email, playlist_id=f"yt_{cid}",
        playlist_title=(snippet.get("title") or name)[:120],
        playlist_url=url, fans=subs, track_count=videos,
        diversity=0.0, quality_score=quality_from(subs), status="lead",
    )
    if not new_id:
        return "dup"
    if email or source:
        _set_source(new_id, source, url)
    return "found" if email else "lead"


def run(seeds: list[str], per_seed: int = _PER_SEED) -> dict:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return {"error": "YOUTUBE_API_KEY yok (.env)"}
    _ensure_columns()
    stats = {"channels": 0, "leads": 0, "found": 0, "dup": 0, "quota_stop": False}
    for seed in seeds:
        ids = _search_channel_ids(seed, api_key, per_seed)
        if not ids and not yt._can_spend(yt._SEARCH_COST):
            stats["quota_stop"] = True
            break
        for ch in _fetch_channels(ids, api_key):
            result = _import_channel(ch)
            stats["channels"] += 1
            if result == "found":
                stats["found"] += 1
                stats["leads"] += 1
            elif result == "lead":
                stats["leads"] += 1
            elif result == "dup":
                stats["dup"] += 1
        time.sleep(_SLEEP)
    stats["quota_used"] = yt.units_used_today()
    return stats


def main(argv: list[str]) -> int:
    seeds = DEFAULT_SEEDS
    if len(argv) > 1 and not argv[1].startswith("--"):
        with open(argv[1], encoding="utf-8") as fh:
            seeds = [ln.strip() for ln in fh if ln.strip()]
    result = run(seeds)
    if result.get("error"):
        print("HATA:", result["error"])
        return 1
    print(f"youtube scout — kanal:{result['channels']} lead:{result['leads']} "
          f"iletisim:{result['found']} tekrar:{result['dup']} "
          f"kota:{result.get('quota_used')} durdu:{result.get('quota_stop')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
