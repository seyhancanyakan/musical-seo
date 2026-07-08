"""E-posta kapisi lead yakalama — donusum huninin girisi.

Programatik SEO sayfalari (sanatci/sarki/playlist) ucretsiz bir on-izleme
gosterir, tam rapor icin e-posta ister ("E-posta kapisi"). Bu modul o
e-postalari `leads` tablosuna (marketplace.db) yazar; `growth`/`accounts`
akislari daha sonra bu lead'leri hesaba/uyeye cevirir.

Is kurali ihlalleri ValueError (aksanli Turkce) — API katmani 400'e cevirir.
Ayni (email, source) ikilisi son 24 saat icinde tekrar gelirse yeni satir
acilmaz, mevcut kayit donulur (idempotent-ye-yakin — spam/cift kayit onlenir).
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone

from marketplace import db

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        email TEXT NOT NULL,
        source TEXT NOT NULL,
        context_json TEXT NOT NULL DEFAULT '{}'
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_leads_email ON leads (email);",
]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir (row_factory=Row)
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["context"] = json.loads(d.get("context_json") or "{}")
    return d


def capture_lead(email: str, source: str, context: dict | None = None) -> dict:
    """E-posta yakalar. Gecersiz e-posta -> ValueError. Ayni e-posta+kaynak
    son 24 saatte tekrar gelirse mevcut kayit donulur, yeni satir acilmaz."""
    if not email or not _EMAIL_RE.match(email.strip()):
        raise ValueError("Gecersiz e-posta adresi")
    if not source or not source.strip():
        raise ValueError("Kaynak (source) bos olamaz")

    email_norm = email.strip().lower()
    source_norm = source.strip()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    conn = _connect()
    try:
        existing = conn.execute(
            """
            SELECT * FROM leads
            WHERE email = ? AND source = ? AND created_at >= ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (email_norm, source_norm, cutoff),
        ).fetchone()
        if existing is not None:
            return _row_to_dict(existing)

        now = datetime.now(timezone.utc).isoformat()
        context_json = json.dumps(context or {}, ensure_ascii=False)
        with conn:
            cursor = conn.execute(
                "INSERT INTO leads (created_at, email, source, context_json) "
                "VALUES (?, ?, ?, ?)",
                (now, email_norm, source_norm, context_json),
            )
        row = conn.execute(
            "SELECT * FROM leads WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_dict(row)


def leads_count() -> int:
    conn = _connect()
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM leads").fetchone()
    finally:
        conn.close()
    return int(row["c"])


def recent_leads(limit: int = 50) -> list[dict]:
    if limit <= 0:
        raise ValueError("limit pozitif olmali")
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM leads ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]
