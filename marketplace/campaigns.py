"""Radyo reklam kampanyasi fan-out: alici tek formda birden fazla sehir/kusaga
uygun radyo ilanina AYNI ANDA siparis verir (paket onerici + rapor + takip).

radio_ads.py'nin uzerine kurulu bir katman: gercek siparisler yine
radio_ads.place_order ile radio_ad_orders tablosuna yazilir (fiyat/komisyon
hesabi orada tek yerde kalir — burada tekrar hesaplanmaz). Bu modul sadece
"bir kampanyaya kac siparis bagli" bilgisini ad_campaign_orders ile tutar.

Tablolar (marketplace.db):
    ad_campaigns:       alicinin tek seferlik kampanya talebi (urun/spot/ses,
                        hedef sehir+kusak listesi, hafta, butce, kupon kodu,
                        toplam bedel+komisyon, TEK birlesik sozlesme metni).
    ad_campaign_orders: kampanya -> radio_ad_orders baglanti tablosu
                        (order_id UNIQUE: bir siparis yalniz bir kampanyaya ait).

Paket onerici (suggest_packages): aktif ilanlardan 3 hazir paket kurar —
alici hicbir ilan secmeden butcesine uygun bir baslangic noktasi gorur.

Fan-out disiplini (create_campaign): eslesen aktif ilanlar en ucuzdan pahaliya
siralanir, butce asilana KADAR siparis verilir (ilk asim noktasinda durulur —
"skip and continue" degil). En az bir siparis olusmazsa hicbir kayit
birakmadan ValueError firlatilir.

Is kurali ihlalleri ValueError (aksanli Turkce) — router katmani 400'e cevirir.
"""
from __future__ import annotations

import os
import secrets
import sqlite3

from marketplace import accounts, db, growth, radio_ads

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS ad_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        buyer_name TEXT NOT NULL,
        buyer_email TEXT NOT NULL,
        buyer_kind TEXT NOT NULL,
        product_name TEXT NOT NULL,
        spot_text TEXT NOT NULL,
        audio_url TEXT,
        jingle_url TEXT,
        coupon_code TEXT NOT NULL,
        cities TEXT,
        dayparts TEXT,
        weeks INTEGER NOT NULL,
        budget_try INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        total_try INTEGER NOT NULL DEFAULT 0,
        commission_try INTEGER NOT NULL DEFAULT 0,
        contract_text TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ad_campaign_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL REFERENCES ad_campaigns(id),
        order_id INTEGER NOT NULL UNIQUE REFERENCES radio_ad_orders(id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ad_campaign_orders_campaign "
    "ON ad_campaign_orders (campaign_id);",
]

_WEEKEND_DAYPARTS = ("drive", "aksam")
_OPENING_CAP = 3


def _connect() -> sqlite3.Connection:
    conn = accounts._connect()  # marketplace.db + ana sema + hesaplar hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


# --- Paket onerici ------------------------------------------------------------

def _fill_budget(candidates: list[dict], weeks: int, budget_try: int | None) -> dict:
    """En ucuzdan baslayarak butceye sigdigi kadar ilan secer (siralamaya gore
    ilk asim noktasinda durur — kirpma budur)."""
    ordered = sorted(candidates, key=lambda l: l["price_week_try"])
    selected: list[dict] = []
    total = 0
    for listing in ordered:
        price = listing["price_week_try"] * weeks
        if budget_try is not None and total + price > budget_try:
            break
        selected.append(listing)
        total += price
    return {
        "listings": selected,
        "weeks": weeks,
        "total_try": total,
        "est_weekly_spots": sum(l["weekly_spots"] for l in selected),
    }


def suggest_packages(
    city: str | None = None, budget_try: int | None = None,
    dayparts: list[str] | None = None,
) -> list[dict]:
    """Aktif ilanlardan 3 hazir paket: Acilis, Hafta Sonu, 1 Aylik Bilinirlik.
    Hic aktif ilan (ya da filtreye uyan ilan) yoksa hepsi bos listingle doner."""
    pool = radio_ads.public_catalog(city=city)
    if dayparts:
        valid = {d for d in dayparts if d in radio_ads.DAYPARTS}
        if valid:
            pool = [l for l in pool if l["daypart"] in valid]

    opening = _fill_budget(
        sorted(pool, key=lambda l: l["price_week_try"])[:_OPENING_CAP], 1, budget_try
    )
    weekend_pool = [l for l in pool if l["daypart"] in _WEEKEND_DAYPARTS]
    weekend = _fill_budget(weekend_pool, 1, budget_try)
    monthly = _fill_budget(pool, 4, budget_try)

    return [
        {"key": "opening", "label": "Açılış Paketi", **opening},
        {"key": "weekend", "label": "Hafta Sonu Kampanyası", **weekend},
        {"key": "monthly", "label": "1 Aylık Bilinirlik", **monthly},
    ]


# --- Kampanya olusturma (fan-out) --------------------------------------------

_CAMPAIGN_CONTRACT_HEADER = """RADYO KAMPANYASI SÖZLEŞMESİ
(MüzikSEO aracılığıyla düzenlenmiştir — {station_count} istasyon, tek kampanya)

TARAFLAR
  Reklam Veren: {buyer_name} ({buyer_email})
  Ürün/Sanatçı: {product_name}

SPOT
  Metin: {spot_text}
  Süre: {weeks} hafta
  Kupon Kodu: {coupon_code}

BEDEL
  Toplam Bedel: {total_try} TL (MüzikSEO komisyonu %{commission_pct:g} dahil: {commission_try} TL)

İSTASYONLAR
"""

_CAMPAIGN_CONTRACT_STATION_LINE = (
    "  - {station_name} ({city}): {slot_seconds}s / {daypart} kuşağı, "
    "haftalık {weekly_spots} tekrar, bedel {price_try} TL\n"
)

_CAMPAIGN_CONTRACT_FOOTER = """
NOT
  Yayınlar bağımsız izleme ile doğrulanabilir. Bu belge MüzikSEO aracılığıyla
  düzenlenmiştir.
"""


def _build_contract(
    buyer_name: str, buyer_email: str, product_name: str, spot_text: str,
    weeks: int, coupon_code: str, total_try: int, commission_try: int,
    orders: list[tuple[dict, dict]],
) -> str:
    text = _CAMPAIGN_CONTRACT_HEADER.format(
        station_count=len(orders), buyer_name=buyer_name, buyer_email=buyer_email,
        product_name=product_name, spot_text=spot_text, weeks=weeks,
        coupon_code=coupon_code, total_try=total_try,
        commission_pct=radio_ads.COMMISSION_RATE * 100, commission_try=commission_try,
    )
    for listing, order in orders:
        text += _CAMPAIGN_CONTRACT_STATION_LINE.format(
            station_name=listing["station_name"], city=listing.get("city") or "—",
            slot_seconds=listing["slot_seconds"], daypart=listing["daypart"],
            weekly_spots=listing["weekly_spots"], price_try=order["price_try"],
        )
    return text + _CAMPAIGN_CONTRACT_FOOTER


def create_campaign(
    buyer_name: str, buyer_email: str, buyer_kind: str, product_name: str,
    spot_text: str, cities: list[str], dayparts: list[str], weeks: int,
    budget_try: int, audio_url: str | None = None, jingle_url: str | None = None,
) -> dict:
    """Eslesen aktif ilanlara FAN-OUT siparis verir; en az bir siparis olusmazsa
    hicbir kayit birakmadan ValueError firlatir."""
    if buyer_kind not in radio_ads.BUYER_KINDS:
        raise ValueError(f"Geçersiz alıcı türü: {buyer_kind}")
    if "@" not in (buyer_email or "").strip():
        raise ValueError("Geçerli bir e-posta gir")
    if not buyer_name.strip():
        raise ValueError("Alıcı adı boş olamaz")
    if not product_name.strip():
        raise ValueError("Ürün/sanatçı adı boş olamaz")
    if not spot_text.strip():
        raise ValueError("Spot metni boş olamaz")
    if not (radio_ads.MIN_WEEKS <= weeks <= radio_ads.MAX_WEEKS):
        raise ValueError(
            f"Hafta sayısı {radio_ads.MIN_WEEKS}-{radio_ads.MAX_WEEKS} arasında olmalı"
        )
    if budget_try <= 0:
        raise ValueError("Bütçe pozitif olmalı")

    pool = radio_ads.public_catalog()
    if cities:
        cities_norm = {c.strip() for c in cities if c.strip()}
        if cities_norm:
            pool = [l for l in pool if (l.get("city") or "") in cities_norm]
    if dayparts:
        dayparts_norm = {d.strip() for d in dayparts if d.strip()}
        if dayparts_norm:
            pool = [l for l in pool if l["daypart"] in dayparts_norm]

    selection = _fill_budget(pool, weeks, budget_try)["listings"]
    if not selection:
        raise ValueError("bütçeye uyan ilan bulunamadı")

    coupon_code = "RADYO-" + secrets.token_hex(2).upper()
    message = spot_text.strip()
    if audio_url:
        message += f"\nSes dosyası: {audio_url}"
    if jingle_url:
        message += f"\nJingle: {jingle_url}"
    message += f"\nKupon: {coupon_code}"

    orders: list[tuple[dict, dict]] = []
    for listing in selection:
        order = radio_ads.place_order(
            listing["id"], buyer_name, buyer_email, buyer_kind, weeks, message,
        )
        orders.append((listing, order))

    total_try = sum(o["price_try"] for _, o in orders)
    commission_try = sum(o["commission_try"] for _, o in orders)
    contract_text = _build_contract(
        buyer_name.strip(), buyer_email.strip(), product_name.strip(),
        spot_text.strip(), weeks, coupon_code, total_try, commission_try, orders,
    )

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO ad_campaigns
                    (created_at, buyer_name, buyer_email, buyer_kind, product_name,
                     spot_text, audio_url, jingle_url, coupon_code, cities, dayparts,
                     weeks, budget_try, status, total_try, commission_try, contract_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (db.now_iso(), buyer_name.strip(), buyer_email.strip(), buyer_kind,
                 product_name.strip(), spot_text.strip(), audio_url, jingle_url,
                 coupon_code, ",".join(cities or []), ",".join(dayparts or []),
                 weeks, budget_try, total_try, commission_try, contract_text),
            )
            campaign_id = int(cur.lastrowid)
            for _listing, order in orders:
                conn.execute(
                    "INSERT INTO ad_campaign_orders (campaign_id, order_id) "
                    "VALUES (?, ?)",
                    (campaign_id, order["id"]),
                )
        row = conn.execute(
            "SELECT * FROM ad_campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        campaign = dict(row)
    finally:
        conn.close()

    for _listing, order in orders:
        notify_radio(order)

    return campaign


def _campaign_row(campaign_id: int) -> dict:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM ad_campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"Kampanya bulunamadı: {campaign_id}")
    return dict(row)


def get_campaign(campaign_id: int, buyer_email: str) -> dict:
    """Alici sadece kendi e-postasiyla kampanyasini gorebilir (varlik maskesi:
    bulunamadi/yanlis e-posta ayni hatayi doner)."""
    campaign = _campaign_row(campaign_id)
    if campaign["buyer_email"].strip().lower() != (buyer_email or "").strip().lower():
        raise ValueError(f"Kampanya bulunamadı: {campaign_id}")
    return campaign


def campaign_status(campaign_id: int) -> list[dict]:
    """Kampanyaya bagli siparis kirilimi: istasyon, durum, teyitli yayin sayisi."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT o.id AS order_id, l.station_name AS station, l.city AS city,
                   o.status AS status, o.verified_plays AS verified_plays,
                   o.price_try AS price_try, o.commission_try AS commission_try
            FROM ad_campaign_orders co
            JOIN radio_ad_orders o ON o.id = co.order_id
            JOIN radio_ad_listings l ON l.id = o.listing_id
            WHERE co.campaign_id = ?
            ORDER BY o.id
            """,
            (campaign_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def campaign_report(campaign_id: int) -> dict:
    """Denetim raporu: planlanan toplam spot vs teyitli yayin, istasyon bazinda
    kirilim, kupon kodu."""
    campaign = _campaign_row(campaign_id)
    breakdown = campaign_status(campaign_id)

    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT l.weekly_spots AS weekly_spots
            FROM ad_campaign_orders co
            JOIN radio_ad_orders o ON o.id = co.order_id
            JOIN radio_ad_listings l ON l.id = o.listing_id
            WHERE co.campaign_id = ?
            """,
            (campaign_id,),
        ).fetchall()
    finally:
        conn.close()

    planned_spots = sum(r["weekly_spots"] for r in rows) * campaign["weeks"]
    verified_plays = sum(b["verified_plays"] for b in breakdown)
    per_station = [
        {
            "station": b["station"],
            "city": b["city"],
            "status": b["status"],
            "verified_plays": b["verified_plays"],
            # Ayrintili yayin zaman-damgasi logu yok (radio_ads teyitli sayac
            # tutar) — burada ayni teyitli sayimin bir kopyasi kullanilir.
            "son_yayinlar": b["verified_plays"],
        }
        for b in breakdown
    ]
    return {
        "planned_spots": planned_spots,
        "verified_plays": verified_plays,
        "per_station": per_station,
        "coupon_code": campaign["coupon_code"],
    }


def list_admin_campaigns(status: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM ad_campaigns", []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def mark_campaign_paid(campaign_id: int) -> dict:
    """Admin: kampanyaya bagli tum siparisleri odendi isaretler, kampanya
    'active' olur. Baglı siparislerden biri henuz kabul edilmemisse
    radio_ads.mark_paid o siparis icin ValueError firlatir (yukari tasinir)."""
    campaign = _campaign_row(campaign_id)
    breakdown = campaign_status(campaign_id)
    for row in breakdown:
        radio_ads.mark_paid(row["order_id"])

    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE ad_campaigns SET status = 'active' WHERE id = ?",
                (campaign_id,),
            )
        updated = conn.execute(
            "SELECT * FROM ad_campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        return dict(updated)
    finally:
        conn.close()


# --- Kurator bildirimi --------------------------------------------------------

def notify_radio(order: dict) -> None:
    """Radyo kuratorune uygulama-ici bildirim + (env doluysa) e-posta.
    Basarisizlik fan-out akisini bozmaz (try/except ile yutulur)."""
    listing = radio_ads.get_listing(order["listing_id"])
    if listing is None:
        return
    curator_id = listing["curator_id"]
    station_name = listing["station_name"]
    user = accounts.user_for_curator(curator_id)
    if user is None:
        return
    try:
        growth.add_notification(
            user["id"], "radio_campaign_order",
            f"{station_name}: yeni kampanya siparişi alındı (#{order['id']})",
            dedupe_same_day=False,
        )
    except Exception:
        pass
    _maybe_email_curator(user, station_name, order)


def _maybe_email_curator(user: dict, station_name: str, order: dict) -> None:
    host = os.environ.get("MUZIKSEO_SMTP_HOST")
    port = os.environ.get("MUZIKSEO_SMTP_PORT")
    smtp_user = os.environ.get("MUZIKSEO_SMTP_USER")
    smtp_pass = os.environ.get("MUZIKSEO_SMTP_PASS")
    to_email = (user or {}).get("email")
    if not (host and port and smtp_user and smtp_pass and to_email):
        return
    try:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = f"Yeni radyo kampanya siparişi — {station_name}"
        msg["From"] = smtp_user
        msg["To"] = to_email
        msg.set_content(
            f"{station_name} için yeni bir kampanya siparişi alındı "
            f"(#{order['id']}).\nDetaylar için MüzikSEO panelinize giriş yapın."
        )
        with smtplib.SMTP(host, int(port), timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception:
        pass  # e-posta basarisizligi fan-out akisini bozmamali
