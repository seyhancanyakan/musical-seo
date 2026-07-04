"""Spotify curator scout — profesyonel curator playlist'lerini kesfet.

Deezer scout'un Spotify muadili. Spotify'da submission-curator ekosistemi cok
daha zengin: playlist ACIKLAMASI'nda curator sik sik gonderim iletisimini yazar
("submit: mail@", "DM @handle", linktr.ee). Bu YASAL — curator'in gonderim icin
kendi yayinladigi veri.

Akis:
  1. Tohum sorgularla Spotify playlist aramasi (/v1/search?type=playlist)
  2. Her playlist: ad + sahip + aciklama + parca sayisi
  3. Aciklamadan iletisim ayikla (email/IG/link)
  4. marketplace.db'ye 'lead' yaz; iletisim bulunduysa email+source doldur

Gereksinim: SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET (.env). Yoksa erken cikar.

Kullanim:
    python -m musical_seo.spotify_scout [seeds.txt]
"""
from __future__ import annotations

import sqlite3
import sys
import time

import requests

from marketplace import db
from marketplace.enrich_contacts import extract_contact
from musical_seo.sources import spotify

SEARCH_URL = "https://api.spotify.com/v1/search"
SLEEP = 0.2
PER_SEED = 20  # tohum basina cekilen playlist

DEFAULT_SEEDS = [
    "turkish indie", "turkce pop", "anadolu rock", "turkish rap",
    "turkce akustik", "turkish electronic", "turkce arabesk", "turkce rock",
]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def search_playlists(token: str, query: str, limit: int) -> list[dict]:
    try:
        r = requests.get(
            SEARCH_URL,
            headers=_headers(token),
            params={"q": query, "type": "playlist", "limit": min(limit, 50)},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        items = (r.json().get("playlists") or {}).get("items") or []
        return [p for p in items if p]
    except Exception:
        return []


def quality_from(tracks: int) -> float:
    return round(min(100.0, min(tracks, 200) * 0.5), 1)


def _set_source(curator_id: int, source: str | None) -> None:
    conn = sqlite3.connect(db._DB_PATH)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(curators)")}
        if "contact_source" not in cols:
            conn.execute("ALTER TABLE curators ADD COLUMN contact_source TEXT")
        conn.execute("UPDATE curators SET contact_source=? WHERE id=?", (source, curator_id))
        conn.commit()
    finally:
        conn.close()


def import_playlist(p: dict) -> str:
    """Playlist'i lead olarak yaz; iletisim bulunduysa 'found', yoksa 'lead' doner."""
    pid = str(p.get("id") or "")
    if not pid:
        return "skip"
    owner = p.get("owner") or {}
    name = (owner.get("display_name") or "Bilinmeyen").strip() or "Bilinmeyen"
    title = (p.get("name") or f"Playlist {pid}").strip()
    url = ((p.get("external_urls") or {}).get("spotify") or "").strip()
    tracks = int((p.get("tracks") or {}).get("total") or 0)
    desc = p.get("description") or ""

    contact = extract_contact(f"{title} {desc}")
    email, source = "", None
    if contact:
        email, src = contact
        source = "spotify_desc_" + src.split("_")[-1]  # email/link/instagram

    cid = db.add_curator(
        name=name, email=email, playlist_id=f"sp_{pid}",
        playlist_title=title, playlist_url=url, fans=0,
        track_count=tracks, diversity=0.0,
        quality_score=quality_from(tracks),
        status="lead",
    )
    if not cid:
        return "dup"
    if email:
        _set_source(cid, source)
        return "found"
    return "lead"


def run(seeds: list[str], per_seed: int = PER_SEED) -> dict:
    token = spotify._get_access_token()
    if not token:
        return {"error": "SPOTIFY_CLIENT_ID/SECRET yok (.env)"}
    stats = {"playlists": 0, "leads": 0, "found": 0, "dup": 0}
    for seed in seeds:
        for p in search_playlists(token, seed, per_seed):
            result = import_playlist(p)
            stats["playlists"] += 1
            if result == "found":
                stats["found"] += 1
                stats["leads"] += 1
            elif result == "lead":
                stats["leads"] += 1
            elif result == "dup":
                stats["dup"] += 1
            time.sleep(SLEEP)
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
    print(f"spotify scout — playlist:{result['playlists']} "
          f"lead:{result['leads']} iletisim-bulunan:{result['found']} tekrar:{result['dup']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
