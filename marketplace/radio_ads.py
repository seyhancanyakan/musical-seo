"""Radyo reklam spotu mini-pazari: radyo turu kurator reklam envanteri acar
(sure/kusak/haftalik tekrar/fiyat), alici (sanatci/isletme) siparis verir,
kurator kabul/red eder, kabulde sozlesme metni uretilir, admin odemeyi
'paid' isaretler, kurator yayini 'record_air' ile dogrular.

Tablolar (marketplace.db):
    radio_ad_listings: radyo kuratorunun actigi reklam envanteri (spot suresi,
                        kusak, haftalik tekrar, haftalik fiyat).
    radio_ad_orders:   alici siparisi. price_try + commission_try siparis
                        aninda hesaplanip donmez degistirilir (fiyat degisse
                        de eski siparis etkilenmez). Kabulde contract_text
                        uretilir. record_air her cagrida verified_plays
                        sayacini artirir.

Komisyon: MuzikSEO, kabul edilen her siparisten COMMISSION_RATE pay alir.
Is kurali ihlalleri ValueError (aksanli Turkce) — router katmani 400'e cevirir.
"""
from __future__ import annotations

import sqlite3

from marketplace import db

COMMISSION_RATE = 0.18
SLOT_SECONDS = (15, 30, 60)
DAYPARTS = ("sabah", "gunduz", "drive", "aksam", "gece")
BUYER_KINDS = ("artist", "business")
MIN_WEEKS = 1
MAX_WEEKS = 12

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS radio_ad_listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        curator_id INTEGER NOT NULL,
        station_name TEXT NOT NULL,
        slot_seconds INTEGER NOT NULL,
        daypart TEXT NOT NULL,
        weekly_spots INTEGER NOT NULL,
        price_week_try INTEGER NOT NULL,
        description TEXT,
        status TEXT NOT NULL DEFAULT 'active'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS radio_ad_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        listing_id INTEGER NOT NULL REFERENCES radio_ad_listings(id),
        buyer_name TEXT NOT NULL,
        buyer_email TEXT NOT NULL,
        buyer_kind TEXT NOT NULL,
        weeks INTEGER NOT NULL,
        message TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        price_try INTEGER NOT NULL,
        commission_try INTEGER NOT NULL,
        contract_text TEXT,
        verified_plays INTEGER NOT NULL DEFAULT 0
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_radio_ad_listings_curator "
    "ON radio_ad_listings (curator_id);",
    "CREATE INDEX IF NOT EXISTS idx_radio_ad_orders_listing "
    "ON radio_ad_orders (listing_id);",
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema (curators dahil) hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    # Eski DB dosyalarina sonradan eklenen kolon (sehir filtresi/kampanya fan-out)
    lcols = {r[1] for r in conn.execute("PRAGMA table_info(radio_ad_listings)")}
    if "city" not in lcols:
        conn.execute("ALTER TABLE radio_ad_listings ADD COLUMN city TEXT DEFAULT NULL")
    return conn


# --- Envanter (radyo kuratoru) ----------------------------------------------

def city_key(city: str | None) -> str | None:
    """Sehir eslesmesi icin Turkce-duyarli normalizasyon: buyuk/kucuk + I/İ/ı
    farkini yok say ('İstanbul' == 'istanbul' == 'ISTANBUL'). Bosluk kirpilir."""
    if not city or not city.strip():
        return None
    s = city.strip()
    for a, b in (("İ", "i"), ("I", "i"), ("ı", "i"), ("Ş", "ş"), ("Ğ", "ğ"),
                 ("Ü", "ü"), ("Ö", "ö"), ("Ç", "ç")):
        s = s.replace(a, b)
    return s.lower()


def create_listing(
    user: dict, station_name: str, slot_seconds: int, daypart: str,
    weekly_spots: int, price_week_try: int, description: str | None = None,
    city: str | None = None,
) -> dict:
    """Yeni reklam envanteri acar. Sadece radyo turu kurator hesabi acabilir."""
    curator_id = user.get("curator_id")
    curator = db.get_curator(curator_id) if curator_id else None
    if curator is None or curator["curator_type"] != "radyo":
        raise ValueError(
            "Reklam envanteri sadece radyo türü kürator hesabıyla açılır"
        )
    if not station_name.strip():
        raise ValueError("İstasyon adı boş olamaz")
    if slot_seconds not in SLOT_SECONDS:
        raise ValueError(f"Geçersiz spot süresi: {slot_seconds}")
    if daypart not in DAYPARTS:
        raise ValueError(f"Geçersiz kuşak: {daypart}")
    if weekly_spots <= 0:
        raise ValueError("Haftalık spot sayısı pozitif olmalı")
    if price_week_try <= 0:
        raise ValueError("Fiyat pozitif olmalı")

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO radio_ad_listings
                    (created_at, curator_id, station_name, slot_seconds, daypart,
                     weekly_spots, price_week_try, description, city)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (db.now_iso(), curator_id, station_name.strip(), slot_seconds,
                 daypart, weekly_spots, price_week_try, description,
                 city_key(city)),
            )
            listing_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM radio_ad_listings WHERE id = ?", (listing_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_listing(listing_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM radio_ad_listings WHERE id = ?", (listing_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def my_listings(user: dict) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM radio_ad_listings WHERE curator_id = ? ORDER BY id DESC",
            (user.get("curator_id"),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _own_listing(listing_id: int, user: dict) -> dict:
    listing = get_listing(listing_id)
    if listing is None or listing["curator_id"] != user.get("curator_id"):
        raise ValueError(f"İlan bulunamadı: {listing_id}")
    return listing


def pause_listing(user: dict, listing_id: int) -> dict:
    _own_listing(listing_id, user)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE radio_ad_listings SET status = 'paused' WHERE id = ?",
                (listing_id,),
            )
        row = conn.execute(
            "SELECT * FROM radio_ad_listings WHERE id = ?", (listing_id,)
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
                "UPDATE radio_ad_listings SET status = 'active' WHERE id = ?",
                (listing_id,),
            )
        row = conn.execute(
            "SELECT * FROM radio_ad_listings WHERE id = ?", (listing_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def public_catalog(
    daypart: str | None = None, max_price: int | None = None,
    city: str | None = None,
) -> list[dict]:
    """Sadece active durumundaki ilanlar (pause edilenler katalogda gorunmez)."""
    conditions, params = ["status = 'active'"], []
    if daypart:
        if daypart not in DAYPARTS:
            raise ValueError(f"Geçersiz kuşak: {daypart}")
        conditions.append("daypart = ?")
        params.append(daypart)
    if max_price is not None:
        conditions.append("price_week_try <= ?")
        params.append(max_price)
    if city:
        conditions.append("city = ?")
        params.append(city_key(city))
    sql = "SELECT * FROM radio_ad_listings WHERE " + " AND ".join(conditions)
    sql += " ORDER BY id DESC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# --- Siparis (alici) --------------------------------------------------------

def place_order(
    listing_id: int, buyer_name: str, buyer_email: str, buyer_kind: str,
    weeks: int, message: str = "",
) -> dict:
    if buyer_kind not in BUYER_KINDS:
        raise ValueError(f"Geçersiz alıcı türü: {buyer_kind}")
    if "@" not in buyer_email.strip():
        raise ValueError("Geçerli bir e-posta gir")
    if not buyer_name.strip():
        raise ValueError("Alıcı adı boş olamaz")
    if not (MIN_WEEKS <= weeks <= MAX_WEEKS):
        raise ValueError(f"Hafta sayısı {MIN_WEEKS}-{MAX_WEEKS} arasında olmalı")
    listing = get_listing(listing_id)
    if listing is None or listing["status"] != "active":
        raise ValueError(f"İlan bulunamadı: {listing_id}")

    price_try = listing["price_week_try"] * weeks
    commission_try = round(price_try * COMMISSION_RATE)

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO radio_ad_orders
                    (created_at, listing_id, buyer_name, buyer_email, buyer_kind,
                     weeks, message, price_try, commission_try)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (db.now_iso(), listing_id, buyer_name.strip(), buyer_email.strip(),
                 buyer_kind, weeks, message, price_try, commission_try),
            )
            order_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM radio_ad_orders WHERE id = ?", (order_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_order(order_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM radio_ad_orders WHERE id = ?", (order_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def orders_for_owner(user: dict) -> list[dict]:
    """Kuratore (ilan sahibine) gelen tum siparisler, istasyon adiyla birlikte."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT o.*, l.station_name AS station_name FROM radio_ad_orders o
            JOIN radio_ad_listings l ON l.id = o.listing_id
            WHERE l.curator_id = ?
            ORDER BY o.id DESC
            """,
            (user.get("curator_id"),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


_CONTRACT_TEMPLATE = """RADYO REKLAM SÖZLEŞMESİ
(MüzikSEO aracılığıyla düzenlenmiştir)

TARAFLAR
  Yayıncı (Radyo İstasyonu): {station_name}
  Reklam Veren: {buyer_name} ({buyer_email})

SPOT BİLGİLERİ
  Spot Süresi: {slot_seconds} saniye
  Kuşak: {daypart}
  Haftalık Tekrar: {weekly_spots}
  Süre: {weeks} hafta

BEDEL
  Toplam Bedel: {price_try} TL (MüzikSEO komisyonu %18 dahil: {commission_try} TL)

NOT
  Yayınlar bağımsız izleme ile doğrulanabilir.

Bu belge MüzikSEO aracılığıyla düzenlenmiştir.
"""


def respond_order(user: dict, order_id: int, action: str) -> dict:
    """Kurator (ilan sahibi) siparise yanit verir: accepted/rejected.

    Kabulde contract_text standart Turkce sablondan uretilir.
    """
    if action not in ("accepted", "rejected"):
        raise ValueError(f"Geçersiz aksiyon: {action}")
    order = get_order(order_id)
    if order is None:
        raise ValueError(f"Sipariş bulunamadı: {order_id}")
    listing = get_listing(order["listing_id"])
    if listing is None or listing["curator_id"] != user.get("curator_id"):
        raise ValueError(f"Sipariş bulunamadı: {order_id}")
    if order["status"] != "pending":
        raise ValueError("Bu sipariş zaten yanıtlanmış")

    contract_text = None
    if action == "accepted":
        contract_text = _CONTRACT_TEMPLATE.format(
            station_name=listing["station_name"],
            buyer_name=order["buyer_name"],
            buyer_email=order["buyer_email"],
            slot_seconds=listing["slot_seconds"],
            daypart=listing["daypart"],
            weekly_spots=listing["weekly_spots"],
            weeks=order["weeks"],
            price_try=order["price_try"],
            commission_try=order["commission_try"],
        )

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE radio_ad_orders SET status = ?, contract_text = ? "
                "WHERE id = ? AND status = 'pending'",
                (action, contract_text, order_id),
            )
            if not cur.rowcount:
                raise ValueError("Bu sipariş zaten yanıtlanmış")
        row = conn.execute(
            "SELECT * FROM radio_ad_orders WHERE id = ?", (order_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def mark_paid(order_id: int) -> dict:
    """Admin: odeme alindi -> status 'paid'. Idempotent (zaten paid ise no-op)."""
    order = get_order(order_id)
    if order is None:
        raise ValueError(f"Sipariş bulunamadı: {order_id}")
    if order["status"] == "paid":
        return order
    if order["status"] != "accepted":
        raise ValueError("Sadece kabul edilmiş sipariş ödenebilir")
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE radio_ad_orders SET status = 'paid' WHERE id = ? "
                "AND status = 'accepted'",
                (order_id,),
            )
        row = conn.execute(
            "SELECT * FROM radio_ad_orders WHERE id = ?", (order_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def record_air(user: dict, order_id: int) -> dict:
    """Kurator (ilan sahibi) yayin dogrulamasi yapar: verified_plays sayacini
    artirir, ilk cagrida status 'airing'e cekilir. Odeme tamamlanmadan
    (status 'paid'/'airing' degilse) kayit alinamaz."""
    order = get_order(order_id)
    if order is None:
        raise ValueError(f"Sipariş bulunamadı: {order_id}")
    listing = get_listing(order["listing_id"])
    if listing is None or listing["curator_id"] != user.get("curator_id"):
        raise ValueError(f"Sipariş bulunamadı: {order_id}")
    if order["status"] not in ("paid", "airing"):
        raise ValueError("Önce ödeme tamamlanmalı")

    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE radio_ad_orders SET verified_plays = verified_plays + 1, "
                "status = 'airing' WHERE id = ?",
                (order_id,),
            )
        row = conn.execute(
            "SELECT * FROM radio_ad_orders WHERE id = ?", (order_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_admin_orders(status: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM radio_ad_orders", []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
