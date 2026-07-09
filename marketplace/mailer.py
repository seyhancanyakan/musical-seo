"""Resend e-posta gonderim katmani — retention alert'leri + lead karsilama
maillerini GERCEKTEN gonderir, ucretsiz katman tavanina SIKI SIKIYA baglı
kalarak (asla asilmaz).

Ortam degiskenleri (hepsi opsiyonel, env-driven):
    RESEND_API_KEY   - yoksa modul TAMAMEN devre disi: her send_email
                        cagrisi agsiz, guarded {"ok": False,
                        "skipped": "no_key"} doner (mevcut davranis
                        DEGISMEZ — anahtar yoksa hicbir sey postalanmaz).
    RESEND_FROM      - gonderen adresi (varsayilan:
                        "Songdeck <onboarding@resend.dev>").
    MAIL_MONTHLY_CAP - aylik gonderim tavani (varsayilan 2900 — Resend
                        ucretsiz katmaninin 3000/ay sinirinin ALTINDA
                        tampon payi birakir).
    MAIL_DAILY_CAP   - gunluk gonderim tavani (varsayilan 95 — Resend'in
                        100/gun ucretsiz sinirinin ALTINDA tampon payi).

email_log tablosu (marketplace.db): her deneme (basarili/basarisiz/atlanmis
fark etmeksizin) kayit altina alinir; status sutunu:
    sent            - Resend'e basariyla POST edildi (2xx yanit).
    skipped_no_key  - RESEND_API_KEY tanimli degil, hic ag istegi atilmadi.
    skipped_dupe    - ayni (category, to_email) icin BUGUN zaten 'sent' var.
    skipped_cap     - aylik/gunluk tavan doldu (ucretsiz katman korumasi).
    failed          - ag hatasi veya Resend HTTP hata kodu.

Tavan mantigi (free-tier koruması): send_email() gonderim yapmadan HEMEN
once _sent_this_month()/_sent_today() sayaclarini kontrol eder; tavana
ulasilmissa POST hic atilmaz — bu sayede Resend'in ucretsiz kotasi (3000/ay,
100/gun) hicbir kosulda asilamaz (MAIL_MONTHLY_CAP/MAIL_DAILY_CAP zaten bu
sinirlarin altinda varsayilanlarla gelir).

Guvence: send_email() ASLA istisna firlatmaz. Network/JSON/HTTP hatalari
guarded'dir; cagiran taraf (marketplace.alerts / marketplace.leads) mail
gonderimi basarisiz olsa bile kendi ana is akisini (alert kaydi, lead
capture) asla kesintiye ugratmaz. Testler agsizdir: RESEND_API_KEY
tanimlanmadigi surece hicbir `requests` cagrisi tetiklenmez.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

import requests

from marketplace import db
from musical_seo import envutil

envutil.load_env()  # RESEND_API_KEY / RESEND_FROM / MAIL_*_CAP .env'den gelsin

_RESEND_URL = "https://api.resend.com/emails"
_REQUEST_TIMEOUT_SECONDS = 10

_DEFAULT_FROM = "Songdeck <onboarding@resend.dev>"
_DEFAULT_MONTHLY_CAP = 2900   # Resend ucretsiz katman: 3000/ay — tampon payi
_DEFAULT_DAILY_CAP = 95       # Resend ucretsiz katman: 100/gun — tampon payi

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS email_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        to_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        category TEXT,
        status TEXT NOT NULL,
        provider_id TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_email_log_status_time "
    "ON email_log (status, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_email_log_dedupe "
    "ON email_log (category, to_email, status, created_at);",
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


# --- Ortam okuma (her cagrida taze — testlerde monkeypatch/env kolay) -------

def _api_key() -> str | None:
    key = os.environ.get("RESEND_API_KEY")
    return key.strip() if key and key.strip() else None


def _from_address() -> str:
    return os.environ.get("RESEND_FROM", _DEFAULT_FROM)


def _monthly_cap() -> int:
    try:
        return int(os.environ.get("MAIL_MONTHLY_CAP", _DEFAULT_MONTHLY_CAP))
    except (TypeError, ValueError):
        return _DEFAULT_MONTHLY_CAP


def _daily_cap() -> int:
    try:
        return int(os.environ.get("MAIL_DAILY_CAP", _DEFAULT_DAILY_CAP))
    except (TypeError, ValueError):
        return _DEFAULT_DAILY_CAP


# --- Sayaclar ----------------------------------------------------------------

def _sent_this_month(conn: sqlite3.Connection) -> int:
    """Bu (UTC) ay icinde status='sent' olan e-posta sayisi."""
    month = datetime.now(timezone.utc).isoformat()[:7]  # 'YYYY-MM'
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM email_log "
        "WHERE status = 'sent' AND substr(created_at, 1, 7) = ?",
        (month,),
    ).fetchone()
    return int(row["c"])


def _sent_today(conn: sqlite3.Connection) -> int:
    """Bugun (UTC) status='sent' olan e-posta sayisi."""
    day = datetime.now(timezone.utc).isoformat()[:10]  # 'YYYY-MM-DD'
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM email_log "
        "WHERE status = 'sent' AND substr(created_at, 1, 10) = ?",
        (day,),
    ).fetchone()
    return int(row["c"])


def _dedupe_hit(conn: sqlite3.Connection, to_email: str, category: str | None) -> bool:
    """Ayni (category, to_email) icin BUGUN zaten 'sent' statuslu kayit var mi?
    (SQLite'ta 'IS ?' hem NULL hem de deger karsilastirmasini dogru yapar.)"""
    day = datetime.now(timezone.utc).isoformat()[:10]
    row = conn.execute(
        "SELECT 1 FROM email_log WHERE to_email = ? AND category IS ? "
        "AND status = 'sent' AND substr(created_at, 1, 10) = ? LIMIT 1",
        (to_email, category, day),
    ).fetchone()
    return row is not None


def _log(conn: sqlite3.Connection, to_email: str, subject: str,
         category: str | None, status: str, provider_id: str | None = None) -> None:
    with conn:
        conn.execute(
            "INSERT INTO email_log "
            "(created_at, to_email, subject, category, status, provider_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (db.now_iso(), to_email, subject, category, status, provider_id),
        )


# --- Ana gonderim fonksiyonu ---------------------------------------------------

def send_email(to: str, subject: str, html: str, category: str | None = None,
               dedupe_key: str | None = None) -> dict:
    """Tek bir e-posta gondermeyi dener. ASLA istisna firlatmaz.

    Pipeline (sirayla):
        1) RESEND_API_KEY tanimli degilse -> agsiz no-op, 'skipped_no_key'.
        2) dedupe_key verildiyse VE (category, to) icin BUGUN zaten 'sent'
           bir kayit varsa -> 'skipped_dupe' (ayni alert gunde bir kez gider).
        3) aylik veya gunluk tavan dolmussa -> 'skipped_cap' — ucretsiz
           katman BU KONTROL sayesinde hicbir kosulda asilmaz.
        4) aksi halde Resend API'sine kisa timeout'lu POST atilir (guarded);
           2xx yanitta -> 'sent' + saglayici id'si, aksi halde 'failed'.

    dedupe_key'in kendisi (icerigi) email_log'a yazilmaz — sadece "bu
    cagriyi dedupe kontroluyle mi calistir" sinyalidir; asil dedupe anahtari
    (category, to_email, gun) ucluisudur. Boylece ayni alert_log.ref'in
    farkli gunlerde tekrar tetiklenmesi (skor tekrar degisirse) engellenmez,
    sadece AYNI GUN icinde tekrar tekrar mail atilmasi engellenir.

    Donen sozluk en az {"ok": bool} icerir; basarisizlikta "skipped" veya
    "error" anahtari, basarida saglayici id'si "id" anahtarinda gelir.
    """
    try:
        api_key = _api_key()
        if not api_key:
            conn = _connect()
            try:
                _log(conn, to, subject, category, "skipped_no_key")
            finally:
                conn.close()
            return {"ok": False, "skipped": "no_key"}

        conn = _connect()
        try:
            if dedupe_key and _dedupe_hit(conn, to, category):
                _log(conn, to, subject, category, "skipped_dupe")
                return {"ok": False, "skipped": "dupe"}

            if (_sent_this_month(conn) >= _monthly_cap()
                    or _sent_today(conn) >= _daily_cap()):
                _log(conn, to, subject, category, "skipped_cap")
                return {"ok": False, "skipped": "cap"}

            try:
                resp = requests.post(
                    _RESEND_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "from": _from_address(),
                        "to": to,
                        "subject": subject,
                        "html": html,
                    },
                    timeout=_REQUEST_TIMEOUT_SECONDS,
                )
            except requests.RequestException as exc:
                _log(conn, to, subject, category, "failed")
                return {"ok": False, "error": str(exc)}

            if 200 <= resp.status_code < 300:
                provider_id = None
                try:
                    provider_id = resp.json().get("id")
                except Exception:
                    provider_id = None
                _log(conn, to, subject, category, "sent", provider_id)
                return {"ok": True, "id": provider_id}

            _log(conn, to, subject, category, "failed")
            return {
                "ok": False,
                "error": f"Resend HTTP {resp.status_code}: {resp.text[:200]}",
            }
        finally:
            conn.close()
    except Exception as exc:  # son care — hicbir kosulda cokme
        return {"ok": False, "error": str(exc)}


def mail_stats() -> dict:
    """Admin gozlemlenebilirligi: bu ay/bugun kac mail 'sent' oldu + tavanlar
    + gonderimin aktif olup olmadigi (RESEND_API_KEY tanimli mi)."""
    conn = _connect()
    try:
        sent_month = _sent_this_month(conn)
        sent_day = _sent_today(conn)
    finally:
        conn.close()
    return {
        "sent_this_month": sent_month,
        "sent_today": sent_day,
        "monthly_cap": _monthly_cap(),
        "daily_cap": _daily_cap(),
        "enabled": _api_key() is not None,
    }
