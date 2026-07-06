"""Radyo airplay takibi — abonelik bazli, periyodik yoklama (poll) ile.

Akis: sanatci artist+title icin abone olur (SUBSCRIPTION_COST kredi, 30 gun
gecerli) -> arka plandaki poll_once() aktif istasyonlari gezer, "su an calan"
metnini cekip aktif aboneliklerle esler -> eslesme varsa airplay_hits'e yazar
(DEDUPE_MINUTES icinde ayni istasyon+abonelik icin tekrar yazmaz).

Tablolar (marketplace.db):
    airplay_stations:      admin tarafindan eklenen radyo/istasyon kaydi.
    airplay_subscriptions: sanatcinin artist/title takip aboneligi.
    airplay_hits:          tespit edilen calinma kaydi (istasyon + abonelik).

Istasyon turleri:
    icecast   -> meta_url, /status-json.xsl ciktisi (icestats.source).
    shoutcast -> meta_url, /7.html ciktisi (virgulle ayrilmis, son alan sarki).

Hata sozlesmesi: is kurali ihlalleri ValueError (Turkce) — API katmani 400'e
cevirir. Ag/parse hatalari sessizce None doner (poll dongusu tek istasyon
hatasiyla durmaz).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Callable

import requests

from marketplace import accounts, db, service

SUBSCRIPTION_COST = 2       # kredi, 30 gunluk abonelik ucreti
SUBSCRIPTION_DAYS = 30
DEDUPE_MINUTES = 30         # ayni istasyon+abonelik icin tekrar hit yazma penceresi
STATION_KINDS = ("icecast", "shoutcast")
FETCH_TIMEOUT_SECONDS = 8

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS airplay_stations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        name TEXT NOT NULL,
        meta_url TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'icecast',
        active INTEGER NOT NULL DEFAULT 1
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS airplay_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        artist TEXT NOT NULL,
        title TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS airplay_hits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        station_id INTEGER NOT NULL REFERENCES airplay_stations(id),
        subscription_id INTEGER NOT NULL REFERENCES airplay_subscriptions(id),
        raw_title TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_airplay_hits_dedupe "
    "ON airplay_hits (station_id, subscription_id, created_at);",
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


# --- Istasyon yonetimi (admin) ---------------------------------------------

def add_station(name: str, meta_url: str, kind: str = "icecast") -> dict:
    """Admin: yeni radyo istasyonu ekle. kind icecast|shoutcast olmali."""
    if not name.strip():
        raise ValueError("Istasyon adi bos olamaz")
    if not meta_url.strip():
        raise ValueError("meta_url bos olamaz")
    if kind not in STATION_KINDS:
        raise ValueError(f"Gecersiz istasyon turu: {kind}")
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO airplay_stations (created_at, name, meta_url, kind) "
                "VALUES (?, ?, ?, ?)",
                (db.now_iso(), name.strip(), meta_url.strip(), kind),
            )
            station_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM airplay_stations WHERE id = ?", (station_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_stations() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM airplay_stations ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Abonelik ---------------------------------------------------------------

def subscribe(user: dict, artist: str, title: str) -> dict:
    """Sanatci artist/title icin abone olur. SUBSCRIPTION_COST kredi dusulur
    (pro'ya da ucretli — istasyon yoklamasinin sunucu maliyeti var).
    30 gunluk gecerlilik doner."""
    artist = artist.strip()
    title = title.strip()
    if not artist or not title:
        raise ValueError("Sanatci ve sarki adi bos olamaz")
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=SUBSCRIPTION_DAYS)
    ).isoformat()
    accounts.charge_credits(user["id"], SUBSCRIPTION_COST, "airplay")
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO airplay_subscriptions "
                "(created_at, user_id, artist, title, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (db.now_iso(), user["id"], artist, title, expires_at),
            )
            sub_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM airplay_subscriptions WHERE id = ?", (sub_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def my_subscriptions(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM airplay_subscriptions WHERE user_id = ? "
            "ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def my_hits(user_id: int) -> list[dict]:
    """Kullanicinin aboneliklerine denk gelen calinma kayitlari, istasyon
    adiyla birlikte."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT h.*, s.artist AS artist, s.title AS title,
                   st.name AS station_name, st.kind AS station_kind
            FROM airplay_hits h
            JOIN airplay_subscriptions s ON s.id = h.subscription_id
            JOIN airplay_stations st ON st.id = h.station_id
            WHERE s.user_id = ?
            ORDER BY h.id DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- "Su an calan" parse ----------------------------------------------------

def _icecast_now_playing(meta_url: str) -> str | None:
    """Icecast status-json.xsl: icestats.source tek nesne veya liste olabilir;
    her kaynaktan title (veya artist + title) birlestirilir."""
    resp = requests.get(meta_url, timeout=FETCH_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    source = data.get("icestats", {}).get("source")
    if source is None:
        return None
    sources = source if isinstance(source, list) else [source]
    parts = []
    for src in sources:
        if not isinstance(src, dict):
            continue
        title = (src.get("title") or "").strip()
        artist = (src.get("artist") or "").strip()
        combined = f"{artist} {title}".strip() if artist else title
        if combined:
            parts.append(combined)
    return " | ".join(parts) if parts else None


def _shoutcast_now_playing(meta_url: str) -> str | None:
    """Shoutcast /7.html: virgulle ayrilmis alanlar, son alan sarki basligi."""
    resp = requests.get(meta_url, timeout=FETCH_TIMEOUT_SECONDS)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        return None
    fields = text.split(",")
    title = fields[-1].strip()
    return title or None


def now_playing(station: dict) -> str | None:
    """Istasyonda su an calan parca stringi; hata durumunda None."""
    try:
        if station["kind"] == "shoutcast":
            return _shoutcast_now_playing(station["meta_url"])
        return _icecast_now_playing(station["meta_url"])
    except Exception:
        return None


# --- Yoklama (poll) ----------------------------------------------------------

def _active_subscriptions(now_iso: str) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM airplay_subscriptions "
            "WHERE active = 1 AND expires_at > ?",
            (now_iso,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _recent_hit_exists(station_id: int, subscription_id: int, now_iso: str) -> bool:
    since = (
        datetime.fromisoformat(now_iso) - timedelta(minutes=DEDUPE_MINUTES)
    ).isoformat()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT 1 FROM airplay_hits "
            "WHERE station_id = ? AND subscription_id = ? AND created_at > ? "
            "LIMIT 1",
            (station_id, subscription_id, since),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _insert_hit(station_id: int, subscription_id: int, raw_title: str) -> dict:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO airplay_hits "
                "(created_at, station_id, subscription_id, raw_title) "
                "VALUES (?, ?, ?, ?)",
                (db.now_iso(), station_id, subscription_id, raw_title),
            )
            hit_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM airplay_hits WHERE id = ?", (hit_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def poll_once(fetch_fn: Callable[[dict], str | None] | None = None) -> dict:
    """Aktif istasyonlari gezer, aktif+suresi gecmemis aboneliklerle esler.
    fetch_fn enjekte edilebilir (test icin): (station) -> str | None.
    Esleme: artist VE title (aksan-duyarsiz) raw stringde gecmeli. Ayni
    (istasyon, abonelik) icin DEDUPE_MINUTES icinde ikinci hit yazilmaz."""
    fetch = fetch_fn or now_playing
    stations = [s for s in list_stations() if s["active"]]
    now_iso = db.now_iso()
    subscriptions = _active_subscriptions(now_iso)

    hits: list[dict] = []
    for station in stations:
        raw = fetch(station)
        if not raw:
            continue
        raw_fold = service.fold(raw)
        for sub in subscriptions:
            if service.fold(sub["artist"]) not in raw_fold:
                continue
            if service.fold(sub["title"]) not in raw_fold:
                continue
            if _recent_hit_exists(station["id"], sub["id"], now_iso):
                continue
            hits.append(_insert_hit(station["id"], sub["id"], raw))

    return {"checked_stations": len(stations), "hits": hits}
