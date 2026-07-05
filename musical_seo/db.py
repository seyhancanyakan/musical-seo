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
from datetime import datetime, timezone
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
    lastfm_listeners INTEGER,
    subscores_json TEXT NOT NULL,
    result_json TEXT NOT NULL
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_snapshots_artist_title_created_at
    ON snapshots (artist, title, created_at);
"""

_CREATE_PITCHES_SQL = """
CREATE TABLE IF NOT EXISTS pitches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    artist TEXT NOT NULL,
    title TEXT NOT NULL,
    playlist_id TEXT NOT NULL,
    playlist_title TEXT NOT NULL,
    playlist_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pitched',
    updated_at TEXT
);
"""

_CREATE_PITCHES_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_pitches_unique
    ON pitches (LOWER(artist), LOWER(title), playlist_id);
"""

PITCH_STATUSES = ("pitched", "accepted", "rejected")


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(_CREATE_TABLE_SQL)
    conn.execute(_CREATE_INDEX_SQL)
    conn.execute(_CREATE_PITCHES_SQL)
    conn.execute(_CREATE_PITCHES_INDEX_SQL)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Eski DB dosyalarina sonradan eklenen kolonlari tamamlar."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(snapshots)")}
    if "lastfm_listeners" not in columns:
        conn.execute("ALTER TABLE snapshots ADD COLUMN lastfm_listeners INTEGER")


def _find_source(sources: list, source_name: str):
    for src in sources:
        if src.source == source_name and src.found:
            return src
    return None


def save(result: AuditResult) -> int:
    spotify = _find_source(result.sources, "spotify")
    deezer = _find_source(result.sources, "deezer")
    youtube = _find_source(result.sources, "youtube")
    lastfm = _find_source(result.sources, "lastfm")

    spotify_popularity = spotify.popularity if spotify is not None else None
    deezer_rank = deezer.popularity if deezer is not None else None
    youtube_views = None
    if youtube is not None:
        youtube_views = youtube.extra.get("views")
    lastfm_listeners = lastfm.popularity if lastfm is not None else None

    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO snapshots (
                    created_at, query, artist, title, score,
                    spotify_popularity, deezer_rank, youtube_views, lastfm_listeners,
                    subscores_json, result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    lastfm_listeners,
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
                SELECT created_at, score, spotify_popularity, deezer_rank,
                       youtube_views, lastfm_listeners
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
            "lastfm_listeners": row["lastfm_listeners"],
        }
        for row in rows
    ]


def save_pitch(
    artist: str, title: str, playlist_id: str, playlist_title: str, playlist_url: str
) -> int:
    """Pitch kaydi ekler; ayni (artist, title, playlist_id) varsa mevcut id doner."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO pitches
                    (created_at, artist, title, playlist_id, playlist_title, playlist_url)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now, artist, title, playlist_id, playlist_title, playlist_url),
            )
            if cursor.rowcount:
                return int(cursor.lastrowid)
            row = conn.execute(
                """
                SELECT id FROM pitches
                WHERE LOWER(artist) = LOWER(?) AND LOWER(title) = LOWER(?)
                  AND playlist_id = ?
                """,
                (artist, title, playlist_id),
            ).fetchone()
            return int(row[0]) if row else 0
    finally:
        conn.close()


def update_pitch_status(pitch_id: int, status: str) -> bool:
    """Pitch durumunu gunceller; kayit yoksa False."""
    if status not in PITCH_STATUSES:
        raise ValueError(f"Gecersiz durum: {status} (gecerli: {', '.join(PITCH_STATUSES)})")
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE pitches SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, pitch_id),
            )
            return cursor.rowcount > 0
    finally:
        conn.close()


def list_pitches(artist: str | None = None, title: str | None = None) -> list[dict]:
    """Pitch kayitlari (istege bagli sanatci/sarki filtresi), kronolojik."""
    sql = (
        "SELECT id, created_at, artist, title, playlist_title, playlist_url, status "
        "FROM pitches"
    )
    conditions, params = [], []
    if artist:
        conditions.append("LOWER(artist) = LOWER(?)")
        params.append(artist)
    if title:
        conditions.append("LOWER(title) = LOWER(?)")
        params.append(title)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at ASC"

    conn = _connect()
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]
