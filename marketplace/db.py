"""Marketplace SQLite deposu — curators + submissions tablolari (data/marketplace.db)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "marketplace.db"

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS curators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        deezer_playlist_id TEXT NOT NULL UNIQUE,
        playlist_title TEXT NOT NULL,
        playlist_url TEXT NOT NULL,
        fans INTEGER NOT NULL DEFAULT 0,
        track_count INTEGER NOT NULL DEFAULT 0,
        diversity REAL NOT NULL DEFAULT 0,
        quality_score REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        artist TEXT NOT NULL,
        title TEXT NOT NULL,
        track_url TEXT,
        curator_id INTEGER NOT NULL REFERENCES curators(id),
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        feedback TEXT,
        responded_at TEXT,
        deadline TEXT NOT NULL,
        placement_verified INTEGER NOT NULL DEFAULT 0,
        artist_user_id INTEGER
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_submissions_curator ON submissions (curator_id, status);",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    for stmt in _SCHEMA:
        conn.execute(stmt)
    # Eski DB dosyalarina sonradan eklenen kolonlar
    cols = {r[1] for r in conn.execute("PRAGMA table_info(submissions)")}
    if "artist_user_id" not in cols:
        conn.execute("ALTER TABLE submissions ADD COLUMN artist_user_id INTEGER")
    ccols = {r[1] for r in conn.execute("PRAGMA table_info(curators)")}
    if "verify_code" not in ccols:
        conn.execute("ALTER TABLE curators ADD COLUMN verify_code TEXT")
    if "ownership_verified" not in ccols:
        conn.execute(
            "ALTER TABLE curators ADD COLUMN ownership_verified INTEGER NOT NULL DEFAULT 0"
        )
    return conn


def add_curator(
    name: str, email: str, playlist_id: str, playlist_title: str, playlist_url: str,
    fans: int, track_count: int, diversity: float, quality_score: float, status: str,
) -> int:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO curators
                    (created_at, name, email, deezer_playlist_id, playlist_title,
                     playlist_url, fans, track_count, diversity, quality_score, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now_iso(), name, email, playlist_id, playlist_title, playlist_url,
                 fans, track_count, diversity, quality_score, status),
            )
            if cur.rowcount:
                return int(cur.lastrowid)
            row = conn.execute(
                "SELECT id FROM curators WHERE deezer_playlist_id = ?", (playlist_id,)
            ).fetchone()
            return int(row["id"]) if row else 0
    finally:
        conn.close()


def get_curator(curator_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM curators WHERE id = ?", (curator_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_curators(status: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM curators", []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY quality_score DESC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def update_curator_status(curator_id: int, status: str) -> bool:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE curators SET status = ? WHERE id = ?", (status, curator_id)
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def add_submission(
    artist: str, title: str, track_url: str | None, curator_id: int,
    message: str, deadline: str, artist_user_id: int | None = None,
) -> int:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO submissions
                    (created_at, artist, title, track_url, curator_id, message,
                     deadline, artist_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now_iso(), artist, title, track_url, curator_id, message,
                 deadline, artist_user_id),
            )
            return int(cur.lastrowid)
    finally:
        conn.close()


def get_submission(submission_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_verify_code(curator_id: int, code: str) -> None:
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE curators SET verify_code = ? WHERE id = ?", (code, curator_id)
            )
    finally:
        conn.close()


def mark_ownership_verified(curator_id: int) -> None:
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE curators SET ownership_verified = 1 WHERE id = ?", (curator_id,)
            )
    finally:
        conn.close()


def list_submissions(
    curator_id: int | None = None, status: str | None = None,
    artist_user_id: int | None = None,
) -> list[dict]:
    conditions, params = [], []
    if curator_id is not None:
        conditions.append("curator_id = ?")
        params.append(curator_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if artist_user_id is not None:
        conditions.append("artist_user_id = ?")
        params.append(artist_user_id)
    sql = "SELECT * FROM submissions"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at ASC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def set_submission_response(submission_id: int, status: str, feedback: str) -> bool:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                UPDATE submissions SET status = ?, feedback = ?, responded_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, feedback, now_iso(), submission_id),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def expire_overdue(now: str | None = None) -> int:
    """SLA'si dolan pending gonderimleri expired isaretler; sayisini doner."""
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE submissions SET status = 'expired' "
                "WHERE status = 'pending' AND deadline < ?",
                (now or now_iso(),),
            )
            return cur.rowcount
    finally:
        conn.close()


def set_placement_verified(submission_id: int) -> bool:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE submissions SET placement_verified = 1 WHERE id = ?",
                (submission_id,),
            )
            return cur.rowcount > 0
    finally:
        conn.close()
