"""Takip edilen ogeler (tracked items) — retention alert'lerinin hedef listesi.

Kullanici hangi sarki/sanatci/playlist'i takip ediyor sorusunun cevabi burada
tutulur. marketplace/alerts.py run_daily() bu tabloyu tarayarak "takip edilen
bir sarkinin SEO skoru degisti mi" sorusunu her kullanici icin ayri ayri
cevaplayabilir (onceden bu iliski hic bir yerde yoktu — alerts.py'deki score
TODO'sunun sebebi buydu). API katmani (marketplace/api.py, bu modulun disinda)
/me/track uc noktalarini buraya baglayacak; bu dosya sadece depo (repository)
katmanidir, HTTP/route bilgisi icermez.

Tablo (marketplace.db):
    tracked_items: (user_id, kind, ref) UNIQUE — ayni kullanici ayni ogeyi
        iki kez takip edemez (track() idempotent). kind ∈ {'song', 'artist',
        'playlist'}. ref serbest metin (sarki icin 'Sanatci - Sarki' formati
        beklenir — bkz. alerts.py _parse_song_ref). last_score/last_checked_at
        sadece 'song' turu icin run_daily tarafindan guncellenir (baseline +
        degisim tespiti).
"""
from __future__ import annotations

import sqlite3

from marketplace import db

ALLOWED_KINDS = ("song", "artist", "playlist")

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS tracked_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        ref TEXT NOT NULL,
        label TEXT,
        last_score REAL,
        last_checked_at TEXT,
        UNIQUE(user_id, kind, ref)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_tracked_items_user ON tracked_items (user_id);",
    "CREATE INDEX IF NOT EXISTS idx_tracked_items_kind ON tracked_items (kind);",
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


def track(user_id: int, kind: str, ref: str, label: str | None = None) -> dict:
    """Kullanici icin bir ogeyi takip listesine ekler (idempotent).

    Ayni (user_id, kind, ref) zaten varsa mevcut satir aynen doner (INSERT OR
    IGNORE) — ikinci cagri hata vermez, tekrar takip etme isteklerinde guvenli.
    kind gecersizse ValueError (Turkce)."""
    if kind not in ALLOWED_KINDS:
        raise ValueError(
            f"Gecersiz takip turu: {kind} (gecerli: {', '.join(ALLOWED_KINDS)})"
        )
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO tracked_items
                    (created_at, user_id, kind, ref, label)
                VALUES (?, ?, ?, ?, ?)
                """,
                (db.now_iso(), user_id, kind, ref, label),
            )
        row = conn.execute(
            "SELECT * FROM tracked_items WHERE user_id = ? AND kind = ? AND ref = ?",
            (user_id, kind, ref),
        ).fetchone()
        assert row is not None
        return dict(row)
    finally:
        conn.close()


def untrack(user_id: int, kind: str, ref: str) -> bool:
    """Takipten cikar; satir bulunup silinirse True."""
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "DELETE FROM tracked_items WHERE user_id = ? AND kind = ? AND ref = ?",
                (user_id, kind, ref),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def tracked_for(user_id: int) -> list[dict]:
    """Bir kullanicinin tum takip ettigi ogeler (en yeniden eskiye)."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM tracked_items WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def all_tracked(kind: str | None = None) -> list[dict]:
    """Tum kullanicilarin takip ettigi ogeler — gunluk tarama (run_daily) icin.

    kind verilirse (orn. 'song') sadece o turdeki ogeler donusu."""
    sql = "SELECT * FROM tracked_items"
    params: list = []
    if kind is not None:
        sql += " WHERE kind = ?"
        params.append(kind)
    sql += " ORDER BY id ASC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def update_score(item_id: int, new_score: float) -> None:
    """Bir ogenin son bilinen SEO skorunu + kontrol zamanini gunceller.

    run_daily() her tarama turunda (baseline ya da degisim tespiti sonrasi)
    bunu cagirir; boylece bir sonraki calistirmada 'onceki skor' dogru olur."""
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE tracked_items SET last_score = ?, last_checked_at = ? "
                "WHERE id = ?",
                (new_score, db.now_iso(), item_id),
            )
    finally:
        conn.close()
