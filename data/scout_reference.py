#!/usr/bin/env python3
"""MuzikSEO curator scout — Deezer acik API'sinden TR playlist/curator kesfi.

Gecelik cron ile calisir. Sadece Deezer'in halka acik API verisini toplar
(playlist metadata + sahip gorunen adi). Kisisel veri (email/telefon) TOPLAMAZ.
Cikti: /opt/muzikseo-scout/curators.db (SQLite) + curators.csv
"""
import csv
import sqlite3
import sys
import time
from datetime import datetime, timezone

import requests

API = "https://api.deezer.com"
HEADERS = {"User-Agent": "muzikseo-scout/0.1"}
SLEEP = 0.2               # Deezer kota nezaketi (50 istek / 5 sn)
SEED_LIMIT = 25           # her calismada islenen tohum sanatci sayisi
PLAYLIST_PER_ARTIST = 10  # sanatci basina taranan playlist
MAX_NEW_PER_RUN = 400     # tur basina yeni playlist tavani
DB = "/opt/muzikseo-scout/curators.db"
CSV = "/opt/muzikseo-scout/curators.csv"
SEEDS = "/opt/muzikseo-scout/seeds.txt"


def get(path, **params):
    for attempt in range(3):
        try:
            r = requests.get(f"{API}{path}", params=params, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and data.get("error"):
                    code = data["error"].get("code")
                    if code == 4:  # quota
                        time.sleep(5)
                        continue
                    return {}
                return data
        except Exception:
            time.sleep(2)
    return {}


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS playlists (
            playlist_id TEXT PRIMARY KEY,
            title TEXT, url TEXT,
            fans INTEGER, nb_tracks INTEGER,
            owner_id TEXT, owner_name TEXT,
            seed_artist TEXT,
            first_seen TEXT, last_seen TEXT
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seed_progress (
            artist TEXT PRIMARY KEY, processed_at TEXT
        )""")
    return conn


def load_seeds(conn):
    """seeds.txt'ten islenMEmis tohumlari al; dosya yoksa Deezer TR chart'tan uret."""
    seeds = []
    try:
        with open(SEEDS, encoding="utf-8") as f:
            seeds = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except FileNotFoundError:
        pass
    if not seeds:
        chart = get("/chart/0/artists", limit=50)
        seeds = [a.get("name", "") for a in chart.get("data", []) if a.get("name")]
        with open(SEEDS, "w", encoding="utf-8") as f:
            f.write("\n".join(seeds) + "\n")
    done = {r[0] for r in conn.execute("SELECT artist FROM seed_progress")}
    pending = [s for s in seeds if s not in done]
    if not pending:  # tur bitti, bastan basla (guncelleme turu)
        conn.execute("DELETE FROM seed_progress")
        conn.commit()
        pending = seeds
    return pending[:SEED_LIMIT]


def expand_artist(name):
    """sanatci -> kendisi + benzerleri (isim listesi)"""
    data = get("/search/artist", q=name, limit=1)
    items = data.get("data") or []
    if not items:
        return [name]
    time.sleep(SLEEP)
    rel = get(f"/artist/{items[0]['id']}/related", limit=8)
    names = [name] + [a.get("name", "") for a in rel.get("data", [])]
    return [n for n in names if n]


def main():
    conn = connect()
    seeds = load_seeds(conn)
    new_count, seen_count = 0, 0
    print(f"[{now()}] scout basladi — {len(seeds)} tohum")

    for seed in seeds:
        if new_count >= MAX_NEW_PER_RUN:
            break
        for artist in expand_artist(seed)[:4]:
            time.sleep(SLEEP)
            data = get("/search/playlist", q=artist, limit=PLAYLIST_PER_ARTIST)
            for pl in data.get("data") or []:
                pid = str(pl.get("id") or "")
                nb = pl.get("nb_tracks") or 0
                if not pid or not 10 <= nb <= 1000:
                    continue
                user = pl.get("user") or {}
                row = conn.execute(
                    "SELECT 1 FROM playlists WHERE playlist_id=?", (pid,)
                ).fetchone()
                if row:
                    conn.execute(
                        "UPDATE playlists SET fans=?, nb_tracks=?, last_seen=? "
                        "WHERE playlist_id=?",
                        (pl.get("fans") or 0, nb, now(), pid),
                    )
                    seen_count += 1
                else:
                    conn.execute(
                        "INSERT INTO playlists VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (pid, pl.get("title") or "", pl.get("link") or
                         f"https://www.deezer.com/playlist/{pid}",
                         pl.get("fans") or 0, nb,
                         str(user.get("id") or ""), user.get("name") or "",
                         seed, now(), now()),
                    )
                    new_count += 1
        conn.execute(
            "INSERT OR REPLACE INTO seed_progress VALUES (?, ?)", (seed, now())
        )
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
    owners = conn.execute(
        "SELECT COUNT(DISTINCT owner_id) FROM playlists WHERE owner_id != ''"
    ).fetchone()[0]

    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["playlist_id", "title", "url", "fans", "nb_tracks",
                    "owner_id", "owner_name", "seed_artist", "first_seen"])
        for r in conn.execute(
            "SELECT playlist_id,title,url,fans,nb_tracks,owner_id,owner_name,"
            "seed_artist,first_seen FROM playlists ORDER BY fans DESC"
        ):
            w.writerow(r)

    conn.close()
    print(f"[{now()}] bitti — yeni:{new_count} guncellenen:{seen_count} "
          f"toplam:{total} tekil-sahip:{owners}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
