"""Programatik SEO sayfa uretim motoru.

`musical_seo.audit.run_audit()` ciktisini statik sayfalar icin cache'lenmis
veri modeline cevirir. Sayfa veri modelleri KENDI veritabaninda
(`data/seo_pages.db`) tutulur; Next.js ISR bu tabloları `marketplace/api_seo.py`
uzerinden okur.

Asamali uretim: `build_next_batch()` kuyruktan (build_queue) N kayit alir,
audit calistirir, basarili olanlari seo_*_pages tablolarina yazar. Boylece
gunde/ayda sinirli sayida yeni sayfa yayina girer (Google'a spam sinyali
vermemek icin).

Thin-content korumasi: audit skor uretemezse veya hicbir platformda kayit
bulunamazsa (`platform_count == 0`) sayfa YAZILMAZ, kuyruk satiri 'thin'
olarak isaretlenir (Google thin-content cezasindan kacis).

Hata sozlesmesi: is kurali ihlalleri ValueError (aksanli Turkce) — API
katmani bunu 400'e cevirir. audit.run_audit ag erisimi gerektirebilir; bu
modul asla onun yuzunden cokmez (try/except ile 'failed' olarak isaretler).
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from musical_seo import audit

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "seo_pages.db"

_CREATE_ARTIST_SQL = """
CREATE TABLE IF NOT EXISTS seo_artist_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    artist_name TEXT NOT NULL,
    isni TEXT,
    score REAL,
    platform_count INTEGER NOT NULL DEFAULT 0,
    findings_json TEXT NOT NULL DEFAULT '[]',
    data_json TEXT NOT NULL DEFAULT '{}',
    first_built_at TEXT NOT NULL,
    last_refreshed_at TEXT NOT NULL,
    indexed INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_SONG_SQL = """
CREATE TABLE IF NOT EXISTS seo_song_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isrc TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL,
    artist TEXT NOT NULL,
    title TEXT NOT NULL,
    score REAL,
    bpm REAL,
    song_key TEXT,
    data_json TEXT NOT NULL DEFAULT '{}',
    last_refreshed_at TEXT NOT NULL,
    indexed INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_PLAYLIST_SQL = """
CREATE TABLE IF NOT EXISTS seo_playlist_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_playlist_id TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    fraud_score REAL,
    verdict TEXT,
    data_json TEXT NOT NULL DEFAULT '{}',
    last_refreshed_at TEXT NOT NULL,
    indexed INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_QUEUE_SQL = """
CREATE TABLE IF NOT EXISTS build_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_type TEXT NOT NULL,
    ref TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
"""

# Ayni (page_type, ref) icin bekleyen (pending) ikinci bir kayit olusmasin —
# enqueue_* fonksiyonlari idempotent olsun diye kismi (partial) unique index.
_CREATE_QUEUE_PENDING_UNIQUE_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_build_queue_pending_unique
    ON build_queue (page_type, ref)
    WHERE status = 'pending';
"""

PAGE_TYPES = ("artist", "song", "playlist")
QUEUE_STATUSES = ("pending", "done", "thin", "failed")

_TURKISH_SLUG_MAP = {
    "ç": "c", "Ç": "c",
    "ğ": "g", "Ğ": "g",
    "ı": "i", "İ": "i",
    "ö": "o", "Ö": "o",
    "ş": "s", "Ş": "s",
    "ü": "u", "Ü": "u",
}
_SLUG_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_ARTIST_SQL)
    conn.execute(_CREATE_SONG_SQL)
    conn.execute(_CREATE_PLAYLIST_SQL)
    conn.execute(_CREATE_QUEUE_SQL)
    conn.execute(_CREATE_QUEUE_PENDING_UNIQUE_SQL)
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Saf yardimcilar ----------------------------------------------------------

def slugify(name: str) -> str:
    """Url-guvenli kucuk harf slug uretir. Turkce karakterler ASCII'ye
    cevrilir, bosluk/noktalama '-' olur, bas/son '-' kirpilir. Saf fonksiyon."""
    if not name or not name.strip():
        raise ValueError("Slug icin ad bos olamaz")
    text = name.strip()
    for src, dst in _TURKISH_SLUG_MAP.items():
        text = text.replace(src, dst)
    text = text.lower()
    text = _SLUG_NON_ALNUM_RE.sub("-", text).strip("-")
    if not text:
        raise ValueError(f"Gecerli bir slug uretilemedi: {name!r}")
    return text


# --- Kuyruk (build_queue) -----------------------------------------------------

def enqueue_artist(artist_name: str, isni: str | None = None, priority: int = 0) -> dict:
    """Sanatciyi uretim kuyruguna ekler. Ayni sanatci icin bekleyen (pending)
    kayit varsa yeni satir acmaz, mevcut olani doner (idempotent)."""
    if not artist_name or not artist_name.strip():
        raise ValueError("Sanatci adi bos olamaz")
    name = artist_name.strip()
    now = _now_iso()
    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO build_queue "
                "(page_type, ref, priority, status, created_at) "
                "VALUES ('artist', ?, ?, 'pending', ?)",
                (name, priority, now),
            )
            if cursor.rowcount:
                row = conn.execute(
                    "SELECT * FROM build_queue WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
            else:
                # Zaten bekleyen bir kayit var (UNIQUE ihlali yutuldu) — onu don.
                row = conn.execute(
                    "SELECT * FROM build_queue WHERE page_type = 'artist' "
                    "AND ref = ? AND status = 'pending'",
                    (name,),
                ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else {}


def _top_findings(findings: list) -> list[dict]:
    top: list[dict] = []
    for f in list(findings)[:3]:
        if hasattr(f, "severity"):
            top.append(
                {
                    "severity": getattr(f, "severity", None),
                    "category": getattr(f, "category", None),
                    "message": getattr(f, "message", None),
                    "action": getattr(f, "action", None),
                }
            )
        elif isinstance(f, dict):
            top.append(f)
    return top


def _result_to_data(result: Any) -> dict:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return dict(getattr(result, "__dict__", {}))


def build_next_batch(limit: int = 100) -> dict:
    """Kuyruktan en fazla `limit` bekleyen kaydi alir, isler. 'artist' disindaki
    turler Faz 1'de desteklenmiyor (failed olarak isaretlenir, cokme YOK).
    audit.run_audit ag hatasi firlatirsa satir 'failed' olur, dongu devam eder.
    Skor yoksa veya hicbir platformda bulunamadiysa (platform_count == 0)
    satir 'thin' olarak isaretlenir, sayfa YAZILMAZ."""
    if limit <= 0:
        raise ValueError("limit pozitif bir sayi olmali")

    conn = _connect()
    processed = built = thin = failed = 0
    now = _now_iso()
    try:
        rows = conn.execute(
            "SELECT * FROM build_queue WHERE status = 'pending' "
            "ORDER BY priority DESC, id ASC LIMIT ?",
            (limit,),
        ).fetchall()

        for row in rows:
            processed += 1

            if row["page_type"] != "artist":
                with conn:
                    conn.execute(
                        "UPDATE build_queue SET status = 'failed' WHERE id = ?",
                        (row["id"],),
                    )
                failed += 1
                continue

            artist_name = row["ref"]
            try:
                result = audit.run_audit(artist_name)
            except Exception:
                with conn:
                    conn.execute(
                        "UPDATE build_queue SET status = 'failed' WHERE id = ?",
                        (row["id"],),
                    )
                failed += 1
                continue

            sources = getattr(result, "sources", None) or []
            platform_count = sum(1 for s in sources if getattr(s, "found", False))
            score = getattr(result, "score", None)

            if score is None or platform_count == 0:
                with conn:
                    conn.execute(
                        "UPDATE build_queue SET status = 'thin' WHERE id = ?",
                        (row["id"],),
                    )
                thin += 1
                continue

            resolved_artist = getattr(result, "resolved_artist", None) or artist_name
            slug = slugify(resolved_artist)
            findings_json = json.dumps(
                _top_findings(getattr(result, "findings", []) or []), ensure_ascii=False
            )
            data_json = json.dumps(_result_to_data(result), ensure_ascii=False)

            existing = conn.execute(
                "SELECT id FROM seo_artist_pages WHERE slug = ?", (slug,)
            ).fetchone()
            with conn:
                if existing:
                    conn.execute(
                        """
                        UPDATE seo_artist_pages
                        SET artist_name = ?, score = ?, platform_count = ?,
                            findings_json = ?, data_json = ?, last_refreshed_at = ?
                        WHERE slug = ?
                        """,
                        (
                            resolved_artist, score, platform_count,
                            findings_json, data_json, now, slug,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO seo_artist_pages (
                            slug, artist_name, isni, score, platform_count,
                            findings_json, data_json, first_built_at,
                            last_refreshed_at, indexed
                        ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, 0)
                        """,
                        (
                            slug, resolved_artist, score, platform_count,
                            findings_json, data_json, now, now,
                        ),
                    )
                conn.execute(
                    "UPDATE build_queue SET status = 'done' WHERE id = ?",
                    (row["id"],),
                )
            built += 1
    finally:
        conn.close()

    return {"processed": processed, "built": built, "thin": thin, "failed": failed}


# --- Okuma (Next.js ISR data fetch) -------------------------------------------

def _parse_json_fields(row: dict, fields: tuple[str, ...]) -> dict:
    d = dict(row)
    for field_name in fields:
        raw = d.get(field_name)
        d[field_name] = json.loads(raw) if raw else ({} if field_name.endswith("data_json") else [])
    return d


def get_artist_page(slug: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM seo_artist_pages WHERE slug = ?", (slug,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return _parse_json_fields(dict(row), ("findings_json", "data_json"))


def get_song_page(isrc: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM seo_song_pages WHERE isrc = ?", (isrc,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return _parse_json_fields(dict(row), ("data_json",))


def get_playlist_page(pid: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM seo_playlist_pages WHERE platform_playlist_id = ?", (pid,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return _parse_json_fields(dict(row), ("data_json",))


# --- Yazma yardimcilari (song/playlist sayfalari baska modullerce doldurulur) -

def upsert_song_page(
    isrc: str,
    slug: str,
    artist: str,
    title: str,
    score: float | None = None,
    bpm: float | None = None,
    song_key: str | None = None,
    data: dict | None = None,
) -> dict:
    """Sarki sayfasini olusturur/gunceller. score yoksa thin-content korumasi
    geregi YAZMAZ, {'skipped': True, 'reason': 'thin'} doner."""
    if not isrc or not isrc.strip():
        raise ValueError("ISRC bos olamaz")
    if not slug or not slug.strip():
        raise ValueError("Slug bos olamaz")
    if not artist or not title:
        raise ValueError("Sanatci ve sarki adi bos olamaz")
    if score is None:
        return {"skipped": True, "reason": "thin", "isrc": isrc}

    now = _now_iso()
    data_json = json.dumps(data or {}, ensure_ascii=False)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO seo_song_pages (
                    isrc, slug, artist, title, score, bpm, song_key,
                    data_json, last_refreshed_at, indexed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(isrc) DO UPDATE SET
                    slug = excluded.slug, artist = excluded.artist,
                    title = excluded.title, score = excluded.score,
                    bpm = excluded.bpm, song_key = excluded.song_key,
                    data_json = excluded.data_json,
                    last_refreshed_at = excluded.last_refreshed_at
                """,
                (isrc, slug, artist, title, score, bpm, song_key, data_json, now),
            )
        row = conn.execute(
            "SELECT * FROM seo_song_pages WHERE isrc = ?", (isrc,)
        ).fetchone()
    finally:
        conn.close()
    return _parse_json_fields(dict(row), ("data_json",))


def upsert_playlist_page(
    platform_playlist_id: str,
    slug: str,
    title: str,
    fraud_score: float | None = None,
    verdict: str | None = None,
    data: dict | None = None,
) -> dict:
    """Playlist sayfasini olusturur/gunceller. fraud_score yoksa thin-content
    korumasi geregi YAZMAZ, {'skipped': True, 'reason': 'thin'} doner."""
    if not platform_playlist_id or not platform_playlist_id.strip():
        raise ValueError("Playlist kimligi bos olamaz")
    if not slug or not slug.strip():
        raise ValueError("Slug bos olamaz")
    if not title:
        raise ValueError("Baslik bos olamaz")
    if fraud_score is None:
        return {"skipped": True, "reason": "thin", "platform_playlist_id": platform_playlist_id}

    now = _now_iso()
    data_json = json.dumps(data or {}, ensure_ascii=False)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO seo_playlist_pages (
                    platform_playlist_id, slug, title, fraud_score, verdict,
                    data_json, last_refreshed_at, indexed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(platform_playlist_id) DO UPDATE SET
                    slug = excluded.slug, title = excluded.title,
                    fraud_score = excluded.fraud_score, verdict = excluded.verdict,
                    data_json = excluded.data_json,
                    last_refreshed_at = excluded.last_refreshed_at
                """,
                (platform_playlist_id, slug, title, fraud_score, verdict, data_json, now),
            )
        row = conn.execute(
            "SELECT * FROM seo_playlist_pages WHERE platform_playlist_id = ?",
            (platform_playlist_id,),
        ).fetchone()
    finally:
        conn.close()
    return _parse_json_fields(dict(row), ("data_json",))


# --- Sitemap ------------------------------------------------------------------

_SITEMAP_TABLES = {
    "artist": ("seo_artist_pages", "slug", "slug"),
    "song": ("seo_song_pages", "isrc", "isrc"),
    "playlist": ("seo_playlist_pages", "platform_playlist_id", "pid"),
}


def pages_for_sitemap(page_type: str, offset: int = 0, limit: int = 50000) -> list[dict]:
    """Sitemap shard'lari icin sayfa kimlikleri + son yenileme zamani."""
    if page_type not in _SITEMAP_TABLES:
        raise ValueError(
            f"Gecersiz sayfa turu: {page_type} (gecerli: {', '.join(PAGE_TYPES)})"
        )
    if offset < 0:
        raise ValueError("offset negatif olamaz")
    if limit <= 0:
        raise ValueError("limit pozitif olmali")

    table, column, key_name = _SITEMAP_TABLES[page_type]
    conn = _connect()
    try:
        rows = conn.execute(
            f"SELECT {column} AS ref, last_refreshed_at FROM {table} "
            "ORDER BY id ASC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    finally:
        conn.close()
    return [
        {key_name: row["ref"], "last_refreshed_at": row["last_refreshed_at"]}
        for row in rows
    ]
