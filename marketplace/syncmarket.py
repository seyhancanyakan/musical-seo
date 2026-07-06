"""Sync/Lisans mini-marketplace: sanatci parca listeler, alici (marka/prodüktor/
yapimci) kullanim talebi acar, sanatci kabul/red eder, kabulde lisans metni
uretilir, admin odemeyi 'paid' isaretler.

Tablolar (marketplace.db):
    sync_listings:  sanatcinin lisansa actigi parca. Fiyatlar kullanim turune
                    gore (youtube/reklam/film); en az biri > 0 olmali.
    sync_requests:  alici talebi. price_try + commission_try talep aninda
                    hesaplanip donmez degistirilir (fiyat degisse de eski
                    talep etkilenmez). Kabulde license_text uretilir.

Komisyon: MUZIKSEO, kabul edilen her talepten COMMISSION_RATE pay alir
(gosterim amacli; gercek tahsilat/odeme entegrasyonu pilot sonrasi).
Is kurali ihlalleri ValueError (Turkce) — router katmani 400'e cevirir.
"""
from __future__ import annotations

import sqlite3

from marketplace import db

COMMISSION_RATE = 0.15
USE_KINDS = ("youtube", "reklam", "film", "podcast", "diger")
# use_kind -> sync_listings fiyat kolonu (podcast/diger icin ayri kolon yok,
# bu turler youtube fiyatini kullanir; ayri fiyatlandirma sonraki asama).
_PRICE_COLUMN = {
    "youtube": "price_youtube",
    "reklam": "price_reklam",
    "film": "price_film",
    "podcast": "price_youtube",
    "diger": "price_youtube",
}

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS sync_listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id),
        artist TEXT NOT NULL,
        title TEXT NOT NULL,
        track_url TEXT,
        genres TEXT,
        mood TEXT,
        description TEXT,
        price_youtube INTEGER,
        price_reklam INTEGER,
        price_film INTEGER,
        status TEXT NOT NULL DEFAULT 'active'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sync_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        listing_id INTEGER NOT NULL REFERENCES sync_listings(id),
        buyer_name TEXT NOT NULL,
        buyer_email TEXT NOT NULL,
        use_kind TEXT NOT NULL,
        message TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        price_try INTEGER NOT NULL,
        commission_try INTEGER NOT NULL,
        license_text TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_sync_listings_user ON sync_listings (user_id);",
    "CREATE INDEX IF NOT EXISTS idx_sync_requests_listing ON sync_requests (listing_id);",
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


# --- Listeleme (sanatci) ---------------------------------------------------

def create_listing(
    user: dict, artist: str, title: str, track_url: str | None = None,
    genres: str | None = None, mood: str | None = None,
    description: str | None = None,
    price_youtube: int | None = None, price_reklam: int | None = None,
    price_film: int | None = None,
) -> dict:
    """Yeni sync listing acar. Fiyatlardan en az biri > 0 olmali."""
    if not artist.strip() or not title.strip():
        raise ValueError("Sanatci ve parca adi bos olamaz")
    prices = [price_youtube, price_reklam, price_film]
    if not any((p or 0) > 0 for p in prices):
        raise ValueError("En az bir kullanim turu icin gecerli fiyat girmelisin")
    for p in prices:
        if p is not None and p < 0:
            raise ValueError("Fiyat negatif olamaz")
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO sync_listings
                    (created_at, user_id, artist, title, track_url, genres, mood,
                     description, price_youtube, price_reklam, price_film)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (db.now_iso(), user["id"], artist.strip(), title.strip(), track_url,
                 genres, mood, description, price_youtube, price_reklam, price_film),
            )
            listing_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM sync_listings WHERE id = ?", (listing_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_listing(listing_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM sync_listings WHERE id = ?", (listing_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_mine(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM sync_listings WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_public(use_kind: str | None = None, genre: str | None = None) -> list[dict]:
    """Sadece active durumundaki ilanlar (pause edilenler katalogda gorunmez)."""
    conditions, params = ["status = 'active'"], []
    if use_kind:
        col = _PRICE_COLUMN.get(use_kind)
        if col is None:
            raise ValueError(f"Gecersiz kullanim turu: {use_kind}")
        conditions.append(f"{col} IS NOT NULL AND {col} > 0")
    if genre:
        conditions.append("genres LIKE ?")
        params.append(f"%{genre}%")
    sql = "SELECT * FROM sync_listings WHERE " + " AND ".join(conditions)
    sql += " ORDER BY id DESC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _own_listing(listing_id: int, user: dict) -> dict:
    listing = get_listing(listing_id)
    if listing is None or listing["user_id"] != user["id"]:
        raise ValueError(f"Ilan bulunamadi: {listing_id}")
    return listing


def pause_listing(user: dict, listing_id: int) -> dict:
    _own_listing(listing_id, user)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE sync_listings SET status = 'paused' WHERE id = ?",
                (listing_id,),
            )
        row = conn.execute(
            "SELECT * FROM sync_listings WHERE id = ?", (listing_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def activate_listing(user: dict, listing_id: int) -> dict:
    _own_listing(listing_id, user)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE sync_listings SET status = 'active' WHERE id = ?",
                (listing_id,),
            )
        row = conn.execute(
            "SELECT * FROM sync_listings WHERE id = ?", (listing_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


# --- Talep (alici) ----------------------------------------------------------

def request_license(
    listing_id: int, buyer_name: str, buyer_email: str, use_kind: str,
    message: str | None = None,
) -> dict:
    """Alici lisans talebi acar. Fiyat, ilanin ilgili kullanim kolonundan
    okunur; yoksa (None ya da 0) ValueError."""
    if use_kind not in USE_KINDS:
        raise ValueError(f"Gecersiz kullanim turu: {use_kind}")
    if not buyer_name.strip() or not buyer_email.strip():
        raise ValueError("Alici adi ve e-posta bos olamaz")
    listing = get_listing(listing_id)
    if listing is None or listing["status"] != "active":
        raise ValueError(f"Ilan bulunamadi: {listing_id}")
    col = _PRICE_COLUMN[use_kind]
    price = listing.get(col)
    if not price:
        raise ValueError("bu kullanim icin fiyat yok")
    commission = round(price * COMMISSION_RATE)
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO sync_requests
                    (created_at, listing_id, buyer_name, buyer_email, use_kind,
                     message, price_try, commission_try)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (db.now_iso(), listing_id, buyer_name.strip(), buyer_email.strip(),
                 use_kind, message, price, commission),
            )
            request_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM sync_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_request(request_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM sync_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def requests_for_owner(user_id: int) -> list[dict]:
    """Sanatciya gelen tum talepler (kendi ilanlarina baglı)."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT r.* FROM sync_requests r
            JOIN sync_listings l ON l.id = r.listing_id
            WHERE l.user_id = ?
            ORDER BY r.id DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


_LICENSE_TEMPLATE = """MUZIK KULLANIM LISANSI
(MUZIKSEO araciligiyla duzenlenmistir)

TARAFLAR
  Lisans Veren (Sanatci): {artist}
  Lisans Alan: {buyer_name} ({buyer_email})

ESER
  Parca: "{title}"

KULLANIM TURU
  {use_kind}

BEDEL
  {price_try} TRY (MUZIKSEO komisyonu: {commission_try} TRY)

SURE VE KAPSAM
  Bu lisans, imza tarihinden itibaren 1 (bir) yil gecerlidir ve TEK KULLANIM
  icin verilmistir. Kapsam disi kullanim icin yeni lisans talebi gereklidir.

Bu belge MUZIKSEO araciligiyla duzenlenmistir.
"""


def respond_request(user: dict, request_id: int, action: str) -> dict:
    """Sanatci (ilan sahibi) talebe yanit verir: accepted/rejected.

    Kabulde license_text standart Turkce sablondan uretilir.
    """
    if action not in ("accepted", "rejected"):
        raise ValueError(f"Gecersiz aksiyon: {action}")
    request = get_request(request_id)
    if request is None:
        raise ValueError(f"Talep bulunamadi: {request_id}")
    listing = get_listing(request["listing_id"])
    if listing is None or listing["user_id"] != user["id"]:
        raise ValueError(f"Talep bulunamadi: {request_id}")
    if request["status"] != "pending":
        raise ValueError("Bu talep zaten yanitlanmis")

    license_text = None
    if action == "accepted":
        license_text = _LICENSE_TEMPLATE.format(
            artist=listing["artist"],
            buyer_name=request["buyer_name"],
            buyer_email=request["buyer_email"],
            title=listing["title"],
            use_kind=request["use_kind"],
            price_try=request["price_try"],
            commission_try=request["commission_try"],
        )

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE sync_requests SET status = ?, license_text = ? "
                "WHERE id = ? AND status = 'pending'",
                (action, license_text, request_id),
            )
            if not cur.rowcount:
                raise ValueError("Bu talep zaten yanitlanmis")
        row = conn.execute(
            "SELECT * FROM sync_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def mark_paid(request_id: int) -> dict:
    """Admin: odeme alindi -> status 'paid'. Idempotent (zaten paid ise no-op)."""
    request = get_request(request_id)
    if request is None:
        raise ValueError(f"Talep bulunamadi: {request_id}")
    if request["status"] == "paid":
        return request
    if request["status"] != "accepted":
        raise ValueError("Sadece kabul edilmis talep odenebilir")
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE sync_requests SET status = 'paid' WHERE id = ? "
                "AND status = 'accepted'",
                (request_id,),
            )
        row = conn.execute(
            "SELECT * FROM sync_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_admin_requests(status: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM sync_requests", []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
