"""Label / A&R B2B erisimi: profesyonel basvuru -> admin onayi -> sureli
token ile "yukselen sanatcilar" raporu.

Akis: sirket apply_label ile basvurur (pending) -> admin approve_label ile
onaylar (30 gunluk access_token uretilir) -> token ile /labels/report
herhangi bir oturum olmadan erisilebilir (token'in kendisi yetki).

Gizlilik: rising_report SADECE leaderboard_opt_in=1 sanatcilari icerir —
opt-out sanatcilarin verisi hicbir sekilde bu rapora sizmaz.

Is kurali ihlalleri ValueError (Turkce) — API katmani 400'e cevirir.
"""
from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from marketplace import accounts, db

TOKEN_TTL_DAYS = 30
LEAD_STATUSES = ("pending", "approved", "rejected")
DELTA_WINDOW_DAYS = 30

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS label_leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        company TEXT NOT NULL,
        contact_name TEXT NOT NULL,
        email TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        access_token TEXT,
        expires_at TEXT
    );
    """,
]


def _connect() -> sqlite3.Connection:
    # accounts._connect() -> db._connect() zinciri: users/submissions/
    # public_reports semasi da hazir olsun (rising_report bunlari okur).
    conn = accounts._connect()
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


# --- Basvuru + admin onayi --------------------------------------------------

def apply_label(company: str, contact_name: str, email: str, note: str = "") -> dict:
    """Label/A&R basvurusu. Ayni e-posta pending durumda beklerken ikinci
    basvuru reddedilir (spam/tekrar onleme)."""
    email = email.strip().lower()
    if "@" not in email or len(email) < 6:
        raise ValueError("Gecerli bir e-posta gir")
    if not company.strip():
        raise ValueError("Sirket adi bos olamaz")
    if not contact_name.strip():
        raise ValueError("Yetkili adi bos olamaz")

    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT id FROM label_leads WHERE email = ? AND status = 'pending'",
            (email,),
        ).fetchone()
        if existing is not None:
            raise ValueError("Bu e-posta ile zaten bekleyen bir basvuru var")
        with conn:
            cur = conn.execute(
                "INSERT INTO label_leads "
                "(created_at, company, contact_name, email, note) "
                "VALUES (?, ?, ?, ?, ?)",
                (db.now_iso(), company.strip(), contact_name.strip(), email,
                 note.strip()),
            )
            lead_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM label_leads WHERE id = ?", (lead_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def admin_list(status: str | None = None) -> list[dict]:
    conn = _connect()
    try:
        sql, params = "SELECT * FROM label_leads", []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY id DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _get_lead(conn: sqlite3.Connection, lead_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM label_leads WHERE id = ?", (lead_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Basvuru bulunamadi: {lead_id}")
    return dict(row)


def approve_label(lead_id: int) -> dict:
    """Basvuruyu onayla: 30 gun gecerli access_token uret."""
    conn = _connect()
    try:
        lead = _get_lead(conn, lead_id)
        token = f"LBL-{secrets.token_hex(8).upper()}"
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS)
        ).isoformat()
        with conn:
            conn.execute(
                "UPDATE label_leads "
                "SET status = 'approved', access_token = ?, expires_at = ? "
                "WHERE id = ?",
                (token, expires_at, lead_id),
            )
        return _get_lead(conn, lead_id)
    finally:
        conn.close()


def reject_label(lead_id: int) -> dict:
    conn = _connect()
    try:
        _get_lead(conn, lead_id)
        with conn:
            conn.execute(
                "UPDATE label_leads SET status = 'rejected' WHERE id = ?",
                (lead_id,),
            )
        return _get_lead(conn, lead_id)
    finally:
        conn.close()


# --- Token dogrulama + rapor -------------------------------------------------

def _validate_token(token: str) -> dict:
    token = (token or "").strip()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM label_leads WHERE access_token = ? AND status = 'approved'",
            (token,),
        ).fetchone()
        if row is None:
            raise ValueError("gecersiz veya suresi dolmus erisim")
        lead = dict(row)
        expires_at = lead.get("expires_at")
        if not expires_at or datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
            raise ValueError("gecersiz veya suresi dolmus erisim")
        return lead
    finally:
        conn.close()


def _score_history(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT created_at, score FROM public_reports "
        "WHERE user_id = ? ORDER BY created_at ASC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _submission_stats(conn: sqlite3.Connection, user_id: int) -> dict:
    row = conn.execute(
        """
        SELECT
            SUM(status = 'accepted') AS accepted,
            SUM(status = 'rejected') AS rejected,
            SUM(placement_verified = 1) AS verified
        FROM submissions WHERE artist_user_id = ?
        """,
        (user_id,),
    ).fetchone()
    accepted = row["accepted"] or 0
    rejected = row["rejected"] or 0
    verified = row["verified"] or 0
    responded = accepted + rejected
    accept_rate = round(accepted / responded * 100, 1) if responded else None
    return {
        "accepted": accepted,
        "verified_placements": verified,
        "accept_rate": accept_rate,
    }


def rising_report(token: str) -> list[dict]:
    """Yukselen sanatcilar raporu: SADECE leaderboard_opt_in=1 sanatcilar.

    Her sanatci icin: son skor, ~30 gun onceki skora gore delta, kabul
    sayisi, dogrulanmis yerlesim sayisi, kabul orani. Skor deltasina gore
    azalan sirali (en cok yukselenler basta)."""
    _validate_token(token)
    conn = _connect()
    try:
        opt_in_users = [
            dict(r) for r in conn.execute(
                "SELECT DISTINCT u.id, u.name FROM users u "
                "JOIN public_reports pr ON pr.user_id = u.id "
                "WHERE u.leaderboard_opt_in = 1"
            ).fetchall()
        ]
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=DELTA_WINDOW_DAYS)
        ).isoformat()

        report: list[dict] = []
        for user in opt_in_users:
            history = _score_history(conn, user["id"])
            if not history:
                continue
            latest_score = history[-1]["score"]
            past = [h for h in history if h["created_at"] <= cutoff]
            score_30d_ago = past[-1]["score"] if past else None
            score_delta = (
                round(latest_score - score_30d_ago, 1)
                if score_30d_ago is not None else None
            )
            stats = _submission_stats(conn, user["id"])
            report.append({
                "artist_name": user["name"],
                "latest_score": latest_score,
                "score_delta": score_delta,
                **stats,
            })

        report.sort(
            key=lambda r: r["score_delta"] if r["score_delta"] is not None
            else float("-inf"),
            reverse=True,
        )
        return report
    finally:
        conn.close()
