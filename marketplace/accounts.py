"""Hesaplar + kredi cuzdani + kurator kazanclari — cekirdek dongunun para katmani.

Dongu: sanatci kredi alir -> gonderimde 1 kredi harcanir -> kurator nitelikli
geri bildirim verirse kazanc tahakkuk eder -> SLA dolarsa kredi otomatik iade.

Tablolar (marketplace.db):
    users:        artist | curator | admin. Kurator hesabi curators tablosuna
                  curator_id ile baglanir. credits = kalan gonderim hakki.
    sessions:     token -> user (basit oturum; token = secrets.token_hex).
    transactions: her kredi hareketi (purchase/grant/submission/refund) —
                  cuzdan bakiyesi bu deftere gore denetlenebilir.
    earnings:     kurator basina tahakkuk; submission_id UNIQUE (ayni gonderim
                  iki kez odenmez). status: accrued -> paid (manuel payout).

Guvenlik: parola PBKDF2-HMAC-SHA256 (120k tur, per-user salt). Is kurali
ihlalleri ValueError (Turkce) — API katmani 400'e cevirir.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from marketplace import db

PBKDF2_ITERATIONS = 120_000
SESSION_TTL_DAYS = 30                # oturum omru; gecince token gecersiz
LOGIN_MAX_FAILURES = 5               # e-posta basina ardisik hatali giris
LOGIN_LOCK_SECONDS = 15 * 60         # kilit suresi
QUALIFIED_FEEDBACK_MIN_CHARS = 120   # "nitelikli" esigi: bos/tek cumle odenmez
FEEDBACK_EARNING_USD = 1.0           # nitelikli degerlendirme basina kurator payi
ROLES = ("artist", "curator", "admin")

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        name TEXT NOT NULL,
        curator_id INTEGER REFERENCES curators(id),
        credits INTEGER NOT NULL DEFAULT 0
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL,
        expires_at TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id),
        delta INTEGER NOT NULL,
        reason TEXT NOT NULL,
        submission_id INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS earnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        curator_user_id INTEGER NOT NULL REFERENCES users(id),
        submission_id INTEGER NOT NULL UNIQUE,
        amount_usd REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'accrued'
    );
    """,
    # Cift iade DB seviyesinde imkansiz: ayni submission icin ikinci 'refund'
    # satiri unique partial index'e takilir (es zamanli cron'lar dahil).
    # (transactions tablosundan SONRA gelmeli.)
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_refund_once
        ON transactions (submission_id) WHERE reason = 'refund';
    """,
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
    if "expires_at" not in cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN expires_at TEXT")
    return conn


# Basit giris rate-limit'i (surec ici; pilot olcegi icin yeterli).
# e-posta -> (ardisik hata sayisi, kilit bitis epoch'u)
_login_failures: dict[str, tuple[int, float]] = {}


def _check_login_lock(email: str) -> None:
    count, locked_until = _login_failures.get(email, (0, 0.0))
    if count >= LOGIN_MAX_FAILURES and time.time() < locked_until:
        raise ValueError("Cok fazla hatali deneme — 15 dakika sonra tekrar dene")


def _record_login_failure(email: str) -> None:
    count, _ = _login_failures.get(email, (0, 0.0))
    _login_failures[email] = (count + 1, time.time() + LOGIN_LOCK_SECONDS)


def _clear_login_failures(email: str) -> None:
    _login_failures.pop(email, None)


# --- Parola / oturum ------------------------------------------------------

def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    salt, _, _ = stored.partition("$")
    return secrets.compare_digest(_hash_password(password, salt), stored)


def register(email: str, password: str, name: str, role: str,
             curator_id: int | None = None) -> dict:
    email = email.strip().lower()
    if role not in ROLES:
        raise ValueError(f"Gecersiz rol: {role}")
    if role == "admin":
        raise ValueError("Admin hesabi kayit formundan acilamaz")
    if "@" not in email or len(email) < 6:
        raise ValueError("Gecerli bir e-posta gir")
    if len(password) < 8:
        raise ValueError("Parola en az 8 karakter olmali")
    if not name.strip():
        raise ValueError("Isim bos olamaz")

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO users "
                "(created_at, email, password_hash, role, name, curator_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (db.now_iso(), email,
                 _hash_password(password, secrets.token_hex(16)),
                 role, name.strip(), curator_id),
            )
            if not cur.rowcount:
                raise ValueError("Bu e-posta ile hesap zaten var")
            user_id = int(cur.lastrowid)
    finally:
        conn.close()
    user = get_user(user_id)
    assert user is not None
    return user


def login(email: str, password: str) -> str:
    """Basarili giriste sureli oturum token'i doner (SESSION_TTL_DAYS)."""
    email = email.strip().lower()
    _check_login_lock(email)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
        if row is None or not _verify_password(password, row["password_hash"]):
            _record_login_failure(email)
            raise ValueError("E-posta veya parola hatali")
        _clear_login_failures(email)
        token = secrets.token_hex(32)
        expires = (
            datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
        ).isoformat()
        with conn:
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (token, row["id"], db.now_iso(), expires),
            )
        return token
    finally:
        conn.close()


def logout(token: str) -> bool:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            return cur.rowcount > 0
    finally:
        conn.close()


def user_by_token(token: str) -> dict | None:
    if not token:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token = ?",
            (token,),
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        expires_at = data.pop("expires_at", None)
        if expires_at and datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
            logout(token)  # suresi dolan oturumu temizle
            return None
        return _public(data)
    finally:
        conn.close()


def set_curator_id(user_id: int, curator_id: int) -> None:
    """Kurator hesabini sonradan playlist'e bagla (kayitta link verilmediyse)."""
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE users SET curator_id = ? WHERE id = ? AND role = 'curator'",
                (curator_id, user_id),
            )
    finally:
        conn.close()


def get_user(user_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _public(dict(row)) if row else None
    finally:
        conn.close()


def _public(user: dict) -> dict:
    user.pop("password_hash", None)
    return user


def user_for_curator(curator_id: int) -> dict | None:
    """curators tablosundaki kayda bagli kullanici hesabi (kazanc tahakkuku)."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE curator_id = ? AND role = 'curator'",
            (curator_id,),
        ).fetchone()
        return _public(dict(row)) if row else None
    finally:
        conn.close()


# --- Kredi cuzdani --------------------------------------------------------

def _apply_credit(conn: sqlite3.Connection, user_id: int, delta: int,
                  reason: str, submission_id: int | None = None) -> None:
    conn.execute(
        "UPDATE users SET credits = credits + ? WHERE id = ?", (delta, user_id)
    )
    conn.execute(
        "INSERT INTO transactions (created_at, user_id, delta, reason, submission_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (db.now_iso(), user_id, delta, reason, submission_id),
    )


def grant_credits(user_id: int, amount: int, reason: str = "grant") -> dict:
    """Pilot donemi: odeme manuel alinir (iyzico/Papara), kredi admin'den yuklenir."""
    if amount <= 0:
        raise ValueError("Kredi miktari pozitif olmali")
    if get_user(user_id) is None:
        raise ValueError(f"Kullanici bulunamadi: {user_id}")
    conn = _connect()
    try:
        with conn:
            _apply_credit(conn, user_id, amount, reason)
    finally:
        conn.close()
    user = get_user(user_id)
    assert user is not None
    return user


def spend_credit(user_id: int, submission_id: int) -> None:
    """Gonderim basina 1 kredi. Bakiye yetersizse ValueError (atomik kontrol)."""
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE users SET credits = credits - 1 "
                "WHERE id = ? AND credits >= 1",
                (user_id,),
            )
            if not cur.rowcount:
                raise ValueError("Yetersiz kredi — paket satin almalisin")
            conn.execute(
                "INSERT INTO transactions "
                "(created_at, user_id, delta, reason, submission_id) "
                "VALUES (?, ?, -1, 'submission', ?)",
                (db.now_iso(), user_id, submission_id),
            )
    finally:
        conn.close()


def refund_credit(user_id: int, submission_id: int) -> bool:
    """SLA dolan gonderimin kredisini iade et. Cift iade DB seviyesinde
    engelli: once refund transaction'i yazilir (idx_tx_refund_once unique),
    yazilamadiysa kredi hic dokunulmaz — es zamanli cron'larda da guvenli."""
    conn = _connect()
    try:
        with conn:
            try:
                conn.execute(
                    "INSERT INTO transactions "
                    "(created_at, user_id, delta, reason, submission_id) "
                    "VALUES (?, ?, 1, 'refund', ?)",
                    (db.now_iso(), user_id, submission_id),
                )
            except sqlite3.IntegrityError:
                return False  # zaten iade edilmis
            conn.execute(
                "UPDATE users SET credits = credits + 1 WHERE id = ?", (user_id,)
            )
            return True
    finally:
        conn.close()


def transactions_for(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Kurator kazanclari ---------------------------------------------------

def is_qualified_feedback(feedback: str) -> bool:
    """Nitelikli = odenebilir: en az QUALIFIED_FEEDBACK_MIN_CHARS anlamli
    karakter. (Sonraki asama: dinleme suresi kontrolu eklenecek.)"""
    return len(feedback.strip()) >= QUALIFIED_FEEDBACK_MIN_CHARS


def accrue_earning(curator_user_id: int, submission_id: int) -> bool:
    """Nitelikli degerlendirme icin $1 tahakkuk. Ayni gonderime ikinci tahakkuk
    yazilmaz (UNIQUE) — False doner. Playlist'e ekleme SARTI YOK (editoryal
    bagimsizlik: kabul de red de ayni ucreti kazanir)."""
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO earnings "
                "(created_at, curator_user_id, submission_id, amount_usd) "
                "VALUES (?, ?, ?, ?)",
                (db.now_iso(), curator_user_id, submission_id, FEEDBACK_EARNING_USD),
            )
            return bool(cur.rowcount)
    finally:
        conn.close()


def earnings_for(curator_user_id: int) -> dict:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM earnings WHERE curator_user_id = ? ORDER BY id DESC",
            (curator_user_id,),
        ).fetchall()
        items = [dict(r) for r in rows]
        total = sum(e["amount_usd"] for e in items)
        pending = sum(e["amount_usd"] for e in items if e["status"] == "accrued")
        return {"items": items, "total_usd": total, "pending_usd": pending}
    finally:
        conn.close()
