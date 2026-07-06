"""Affiliate ortakliklari: distro, mastering, kapak tasarim yonlendirmeleri.

Sanatciya tavsiye edilen ucuncu parti hizmetler; tiklama sayaci ile hangi
ortagin trafik aldigi izlenir (komisyon raporlamasi icin taban veri).
"""
from __future__ import annotations

import sqlite3

from marketplace import db

PARTNERS = {
    "distro": {
        "name": "DistroKit",
        "category": "distro",
        "description": "Muzigini Spotify, Deezer, Apple Music'e dagit",
        "url": "https://distrokit.example.com/?ref=muzikseo",
    },
    "mastering": {
        "name": "MasterLab",
        "category": "mastering",
        "description": "Yapay zeka destekli online mastering",
        "url": "https://masterlab.example.com/?ref=muzikseo",
    },
    "kapak-tasarim": {
        "name": "KapakStudyo",
        "category": "kapak-tasarim",
        "description": "Profesyonel single/album kapak tasarimi",
        "url": "https://kapakstudyo.example.com/?ref=muzikseo",
    },
}

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS affiliate_clicks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        partner_key TEXT NOT NULL
    );
    """,
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


def list_partners() -> list[dict]:
    return [{"key": k, **v} for k, v in PARTNERS.items()]


def record_click(key: str) -> str:
    """Tiklamayi kaydet, ortagin yonlendirme URL'ini dondur.

    Bilinmeyen anahtar ValueError firlatir (router 400'e cevirir).
    """
    partner = PARTNERS.get(key)
    if partner is None:
        raise ValueError(f"Bilinmeyen ortak: {key}")
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO affiliate_clicks (created_at, partner_key) VALUES (?, ?)",
                (db.now_iso(), key),
            )
    finally:
        conn.close()
    return partner["url"]
