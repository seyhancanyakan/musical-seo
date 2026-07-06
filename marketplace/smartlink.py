"""Akilli link (smart link) + pre-save + hayran e-posta toplama.

Sanatci tek link uzerinden tum platformlarina (Spotify, Deezer, YouTube,
Apple Music, diger) yonlendirir. Cikis tarihi gelecekteyse presave modu
otomatik acilir. Her goruntuleme ve platform tiklamasi sayilir; hayran
e-postalari (opt-in consent) export edilebilir — export ucretlidir (pro
kullanicilara ucretsiz).

Tablolar (marketplace.db):
    smart_links:  slug -> sanatci/sarki/links_json/views/clicks_json.
    fan_contacts: link_id + email (UNIQUE) — ayni hayran iki kez sayilmaz.

Is kurali ihlalleri ValueError (Turkce) — router katmani 400'e cevirir.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timezone

from marketplace import accounts, db, service

EXPORT_COST = 2  # fan listesi disa aktarim ucreti (kredi); pro muaf
ALLOWED_PLATFORMS = ("spotify", "deezer", "youtube", "apple", "other")

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS smart_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        artist TEXT NOT NULL,
        title TEXT NOT NULL,
        release_date TEXT,
        links_json TEXT NOT NULL DEFAULT '{}',
        presave INTEGER NOT NULL DEFAULT 0,
        views INTEGER NOT NULL DEFAULT 0,
        clicks_json TEXT NOT NULL DEFAULT '{}'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS fan_contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        link_id INTEGER NOT NULL REFERENCES smart_links(id),
        email TEXT NOT NULL,
        consent INTEGER NOT NULL DEFAULT 1,
        UNIQUE(link_id, email)
    );
    """,
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


def _validate_links(links: dict) -> dict:
    """Sadece izinli platform anahtarlari + http(s) URL kabul edilir."""
    if not links:
        raise ValueError("En az bir platform linki gerekli")
    cleaned: dict[str, str] = {}
    for key, url in links.items():
        if key not in ALLOWED_PLATFORMS:
            raise ValueError(f"Gecersiz platform: {key}")
        url = (url or "").strip()
        if not url.startswith("http"):
            raise ValueError(f"{key} icin gecerli bir URL gir (http ile baslamali)")
        cleaned[key] = url
    return cleaned


def _serialize(row: dict) -> dict:
    row = dict(row)
    row["links"] = json.loads(row.pop("links_json") or "{}")
    row["clicks"] = json.loads(row.pop("clicks_json") or "{}")
    return row


def create_link(user: dict, artist: str, title: str, links: dict,
                release_date: str | None = None) -> dict:
    """Yeni akilli link olustur. Slug: fold('artist-title') + '-' + 4 hex."""
    artist, title = artist.strip(), title.strip()
    if not artist or not title:
        raise ValueError("Sanatci ve sarki adi bos olamaz")
    cleaned_links = _validate_links(links)

    presave = 0
    if release_date:
        try:
            release = datetime.fromisoformat(release_date)
        except ValueError:
            raise ValueError("Gecersiz cikis tarihi (ISO format gerekli)")
        if release.tzinfo is None:
            release = release.replace(tzinfo=timezone.utc)
        presave = int(release > datetime.now(timezone.utc))

    base = service.fold(f"{artist}-{title}").replace(" ", "-")
    slug = f"{base}-{secrets.token_hex(2)}"

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO smart_links
                    (created_at, user_id, slug, artist, title, release_date,
                     links_json, presave)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (db.now_iso(), user["id"], slug, artist, title, release_date,
                 json.dumps(cleaned_links, ensure_ascii=False), presave),
            )
            link_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM smart_links WHERE id = ?", (link_id,)
        ).fetchone()
        return _serialize(dict(row))
    finally:
        conn.close()


def list_links(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM smart_links WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [_serialize(dict(r)) for r in rows]
    finally:
        conn.close()


def _get_link_row(conn: sqlite3.Connection, slug: str) -> dict:
    row = conn.execute(
        "SELECT * FROM smart_links WHERE slug = ?", (slug,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Link bulunamadi: {slug}")
    return dict(row)


def get_by_slug(slug: str) -> dict:
    """Public sayfa: goruntuleme sayaci atomik artar."""
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE smart_links SET views = views + 1 WHERE slug = ?", (slug,)
            )
            if not cur.rowcount:
                raise ValueError(f"Link bulunamadi: {slug}")
        row = conn.execute(
            "SELECT * FROM smart_links WHERE slug = ?", (slug,)
        ).fetchone()
        return _serialize(dict(row))
    finally:
        conn.close()


def record_click(slug: str, platform: str) -> dict:
    """Platform bazli tiklama sayaci (clicks_json icinde artan sayac)."""
    if platform not in ALLOWED_PLATFORMS:
        raise ValueError(f"Gecersiz platform: {platform}")
    conn = _connect()
    try:
        with conn:
            row = _get_link_row(conn, slug)
            clicks = json.loads(row["clicks_json"] or "{}")
            clicks[platform] = clicks.get(platform, 0) + 1
            conn.execute(
                "UPDATE smart_links SET clicks_json = ? WHERE id = ?",
                (json.dumps(clicks, ensure_ascii=False), row["id"]),
            )
        updated = conn.execute(
            "SELECT * FROM smart_links WHERE slug = ?", (slug,)
        ).fetchone()
        return _serialize(dict(updated))
    finally:
        conn.close()


def add_fan(slug: str, email: str) -> bool:
    """Hayran e-postasini kaydet; ayni link+email zaten varsa False (dedupe)."""
    email = email.strip().lower()
    if "@" not in email or len(email) < 4:
        raise ValueError("Gecerli bir e-posta gir")
    conn = _connect()
    try:
        row = _get_link_row(conn, slug)
        with conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO fan_contacts (created_at, link_id, email) "
                "VALUES (?, ?, ?)",
                (db.now_iso(), row["id"], email),
            )
            return bool(cur.rowcount)
    finally:
        conn.close()


def _own_link(user: dict, link_id: int) -> dict:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM smart_links WHERE id = ?", (link_id,)
        ).fetchone()
        if row is None or row["user_id"] != user["id"]:
            raise ValueError(f"Link bulunamadi: {link_id}")
        return dict(row)
    finally:
        conn.close()


def fans_for(user: dict, link_id: int) -> list[dict]:
    """Sahiplik kontrollu hayran listesi (export'un temel verisi)."""
    _own_link(user, link_id)
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM fan_contacts WHERE link_id = ? ORDER BY id DESC",
            (link_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def export_fans(user: dict, link_id: int) -> list[dict]:
    """Fan listesi disa aktarimi: pro ucretsiz, digerine EXPORT_COST kredi."""
    fans = fans_for(user, link_id)
    if not accounts.is_pro(user):
        accounts.charge_credits(user["id"], EXPORT_COST, "fan_export")
    return fans
