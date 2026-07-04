"""SQLite snapshot deposu - zaman serisi birikimi.

DB dosyasi <proje-koku>/data/snapshots.db yolunda tutulur; data/ dizini
otomatik olusturulur. save() her AuditResult'i bir satir olarak ekler,
history() ayni (artist, title) icin kronolojik ozet dondurur.
Kutuphane modulu: print yok, hatalar sessizce yutulmaz (sqlite3 hatalari
oldugu gibi yukari firlatilir).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from musical_seo.models import AuditResult

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "snapshots.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    query TEXT NOT NULL,
    artist TEXT NOT NULL,
    title TEXT NOT NULL,
    score INTEGER NOT NULL,
    spotify_popularity INTEGER,
    deezer_rank INTEGER,
    youtube_views INTEGER,
    subscores_json TEXT NOT NULL,
    result_json TEXT NOT NULL
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_snapshots_artist_title_created_at
    ON snapshots (artist, title, created_at);
"""


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(_CREATE_TABLE_SQL)
    conn.execute(_CREATE_INDEX_SQL)
    return conn


def _find_source(sources: list, source_name: str):
    for src in sources:
        if src.source == source_name and src.found:
            return src
    return None


def save(result: AuditResult) -> int:
    spotify = _find_source(result.sources, "spotify")
    deezer = _find_source(result.sources, "deezer")
    youtube = _find_source(result.sources, "youtube")

    spotify_popularity = spotify.popularity if spotify is not None else None
    deezer_rank = deezer.popularity if deezer is not None else None
    youtube_views = None
    if youtube is not None:
        youtube_views = youtube.extra.get("views")

    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO snapshots (
                    created_at, query, artist, title, score,
                    spotify_popularity, deezer_rank, youtube_views,
                    subscores_json, result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.created_at,
                    result.query,
                    result.resolved_artist,
                    result.resolved_title,
                    result.score,
                    spotify_popularity,
                    deezer_rank,
                    youtube_views,
                    json.dumps(result.subscores, ensure_ascii=False),
                    json.dumps(result.to_dict(), ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)
    finally:
        conn.close()


def history(artist: str, title: str) -> list[dict]:
    conn = _connect()
    try:
        conn.row_factory = sqlite3.Row
        with conn:
            rows = conn.execute(
                """
                SELECT created_at, score, spotify_popularity, deezer_rank, youtube_views
                FROM snapshots
                WHERE LOWER(artist) = LOWER(?) AND LOWER(title) = LOWER(?)
                ORDER BY created_at ASC
                """,
                (artist, title),
            ).fetchall()
    finally:
        conn.close()

    return [
        {
            "created_at": row["created_at"],
            "score": row["score"],
            "spotify_popularity": row["spotify_popularity"],
            "deezer_rank": row["deezer_rank"],
            "youtube_views": row["youtube_views"],
        }
        for row in rows
    ]
