"""Marketplace SQLite deposu — curators + submissions tablolari (data/marketplace.db)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "marketplace.db"

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS curators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        deezer_playlist_id TEXT NOT NULL UNIQUE,
        playlist_title TEXT NOT NULL,
        playlist_url TEXT NOT NULL,
        fans INTEGER NOT NULL DEFAULT 0,
        track_count INTEGER NOT NULL DEFAULT 0,
        diversity REAL NOT NULL DEFAULT 0,
        quality_score REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        artist TEXT NOT NULL,
        title TEXT NOT NULL,
        track_url TEXT,
        curator_id INTEGER NOT NULL REFERENCES curators(id),
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        feedback TEXT,
        responded_at TEXT,
        deadline TEXT NOT NULL,
        placement_verified INTEGER NOT NULL DEFAULT 0,
        artist_user_id INTEGER
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_submissions_curator ON submissions (curator_id, status);",
    """
    CREATE TABLE IF NOT EXISTS purchase_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        package_key TEXT NOT NULL,
        credits INTEGER NOT NULL,
        price_try INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS public_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        token TEXT NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        artist TEXT NOT NULL,
        title TEXT NOT NULL,
        score REAL NOT NULL,
        summary_json TEXT NOT NULL DEFAULT '{}'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        message TEXT NOT NULL,
        read INTEGER NOT NULL DEFAULT 0
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS scheduled_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        artist_user_id INTEGER NOT NULL,
        artist TEXT NOT NULL,
        title TEXT NOT NULL,
        curator_id INTEGER NOT NULL,
        scheduled_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        submission_id INTEGER,
        error TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS payouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        curator_user_id INTEGER NOT NULL,
        amount_usd REAL NOT NULL,
        fee_usd REAL NOT NULL DEFAULT 0,
        instant INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'requested'
    );
    """,
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    for stmt in _SCHEMA:
        conn.execute(stmt)
    # Eski DB dosyalarina sonradan eklenen kolonlar
    cols = {r[1] for r in conn.execute("PRAGMA table_info(submissions)")}
    if "artist_user_id" not in cols:
        conn.execute("ALTER TABLE submissions ADD COLUMN artist_user_id INTEGER")
    ccols = {r[1] for r in conn.execute("PRAGMA table_info(curators)")}
    if "verify_code" not in ccols:
        conn.execute("ALTER TABLE curators ADD COLUMN verify_code TEXT")
    if "ownership_verified" not in ccols:
        conn.execute(
            "ALTER TABLE curators ADD COLUMN ownership_verified INTEGER NOT NULL DEFAULT 0"
        )
    if "curator_type" not in ccols:
        # playlist | radyo | medya | label | menajer | booker | dj | mentor | sync
        conn.execute(
            "ALTER TABLE curators ADD COLUMN curator_type TEXT NOT NULL DEFAULT 'playlist'"
        )
    # Firsat sistemi (Groover modeli): kurator yanitina istege bagli firsat
    # etiketi. primary = somut sonuc (listeye ekleme, radyo calma, yazi...),
    # secondary = dolayli deger (paylasim, tavsiye, iletisimde kalma).
    if "opportunity_level" not in cols:
        conn.execute("ALTER TABLE submissions ADD COLUMN opportunity_level TEXT")
    if "opportunity_kind" not in cols:
        conn.execute("ALTER TABLE submissions ADD COLUMN opportunity_kind TEXT")
    # Fiyatlandirma + premium akislari (bkz. pricing.py):
    # cost_credits = gonderim aninda dusulen toplam kredi (tier/garanti/rush dahil)
    # guaranteed   = SLA kacarsa 2x iade sozu verilen gonderim
    # priority     = one cikan gonderim: 48s SLA + inbox'ta ust sira
    # opened_at    = kurator detayi ilk actigi an (dinleme kapisi icin)
    if "cost_credits" not in cols:
        conn.execute(
            "ALTER TABLE submissions ADD COLUMN cost_credits INTEGER NOT NULL DEFAULT 1"
        )
    if "guaranteed" not in cols:
        conn.execute(
            "ALTER TABLE submissions ADD COLUMN guaranteed INTEGER NOT NULL DEFAULT 0"
        )
    if "priority" not in cols:
        conn.execute(
            "ALTER TABLE submissions ADD COLUMN priority INTEGER NOT NULL DEFAULT 0"
        )
    if "opened_at" not in cols:
        conn.execute("ALTER TABLE submissions ADD COLUMN opened_at TEXT")
    if "certificate_token" not in cols:
        conn.execute("ALTER TABLE submissions ADD COLUMN certificate_token TEXT")
    if "readiness_score" not in cols:
        conn.execute("ALTER TABLE submissions ADD COLUMN readiness_score REAL")
    # quality_passed: basvuru anindaki otomatik kalite esigi sonucu. Onay icin
    # TEK BASINA YETMEZ — sahiplik dogrulamasi da sart (guvenlik).
    if "quality_passed" not in ccols:
        conn.execute(
            "ALTER TABLE curators ADD COLUMN quality_passed INTEGER NOT NULL DEFAULT 0"
        )
    if "sponsored_until" not in ccols:
        conn.execute("ALTER TABLE curators ADD COLUMN sponsored_until TEXT")
    return conn


def add_curator(
    name: str, email: str, playlist_id: str, playlist_title: str, playlist_url: str,
    fans: int, track_count: int, diversity: float, quality_score: float, status: str,
    curator_type: str = "playlist", quality_passed: bool = False,
) -> int:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO curators
                    (created_at, name, email, deezer_playlist_id, playlist_title,
                     playlist_url, fans, track_count, diversity, quality_score, status,
                     curator_type, quality_passed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now_iso(), name, email, playlist_id, playlist_title, playlist_url,
                 fans, track_count, diversity, quality_score, status, curator_type,
                 int(quality_passed)),
            )
            if cur.rowcount:
                return int(cur.lastrowid)
            row = conn.execute(
                "SELECT id FROM curators WHERE deezer_playlist_id = ?", (playlist_id,)
            ).fetchone()
            return int(row["id"]) if row else 0
    finally:
        conn.close()


def get_curator(curator_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM curators WHERE id = ?", (curator_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_curator_by_playlist(playlist_id: str) -> dict | None:
    """Pitch->gonder koprusu: aday playlist onayli kurator mi?"""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM curators WHERE deezer_playlist_id = ?", (playlist_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_curators(status: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM curators", []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY quality_score DESC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def update_curator_status(curator_id: int, status: str) -> bool:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE curators SET status = ? WHERE id = ?", (status, curator_id)
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def add_submission(
    artist: str, title: str, track_url: str | None, curator_id: int,
    message: str, deadline: str, artist_user_id: int | None = None,
) -> int:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO submissions
                    (created_at, artist, title, track_url, curator_id, message,
                     deadline, artist_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now_iso(), artist, title, track_url, curator_id, message,
                 deadline, artist_user_id),
            )
            return int(cur.lastrowid)
    finally:
        conn.close()


def get_submission(submission_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_verify_code(curator_id: int, code: str) -> None:
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE curators SET verify_code = ? WHERE id = ?", (code, curator_id)
            )
    finally:
        conn.close()


def mark_ownership_verified(curator_id: int) -> None:
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE curators SET ownership_verified = 1 WHERE id = ?", (curator_id,)
            )
    finally:
        conn.close()


def list_submissions(
    curator_id: int | None = None, status: str | None = None,
    artist_user_id: int | None = None,
) -> list[dict]:
    conditions, params = [], []
    if curator_id is not None:
        conditions.append("curator_id = ?")
        params.append(curator_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if artist_user_id is not None:
        conditions.append("artist_user_id = ?")
        params.append(artist_user_id)
    sql = "SELECT * FROM submissions"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    # One cikan (priority) gonderimler kurator inbox'inda ustte gorunur.
    sql += " ORDER BY priority DESC, created_at ASC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def set_submission_response(
    submission_id: int, status: str, feedback: str,
    opportunity_level: str | None = None, opportunity_kind: str | None = None,
) -> bool:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                UPDATE submissions
                SET status = ?, feedback = ?, responded_at = ?,
                    opportunity_level = ?, opportunity_kind = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, feedback, now_iso(), opportunity_level, opportunity_kind,
                 submission_id),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def curator_stats(curator_id: int | None = None) -> dict[int, dict]:
    """Kurator basina performans metrikleri (curator_id -> stats).

    response_rate  = yanitlanan / (yanitlanan + suresi dolan)
    success_rate   = kabul / yanitlanan
    opportunity_rate = firsat etiketli yanit / yanitlanan
    Oranlar 0-100 tamsayi; hic ilgili gonderim yoksa None.
    """
    sql = """
        SELECT curator_id,
               COUNT(*) AS total,
               SUM(status IN ('accepted', 'rejected')) AS responded,
               SUM(status = 'accepted') AS accepted,
               SUM(status = 'expired') AS expired,
               SUM(opportunity_level IS NOT NULL) AS opportunities
        FROM submissions
    """
    params: list = []
    if curator_id is not None:
        sql += " WHERE curator_id = ?"
        params.append(curator_id)
    sql += " GROUP BY curator_id"
    conn = _connect()
    try:
        result: dict[int, dict] = {}
        for r in conn.execute(sql, params).fetchall():
            responded = r["responded"] or 0
            closed = responded + (r["expired"] or 0)
            result[r["curator_id"]] = {
                "total_submissions": r["total"],
                "responded": responded,
                "accepted": r["accepted"] or 0,
                "response_rate": round(responded / closed * 100) if closed else None,
                "success_rate": (
                    round((r["accepted"] or 0) / responded * 100) if responded else None
                ),
                "opportunity_rate": (
                    round((r["opportunities"] or 0) / responded * 100)
                    if responded else None
                ),
            }
        return result
    finally:
        conn.close()


def expire_overdue(now: str | None = None) -> int:
    """SLA'si dolan pending gonderimleri expired isaretler; sayisini doner."""
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE submissions SET status = 'expired' "
                "WHERE status = 'pending' AND deadline < ?",
                (now or now_iso(),),
            )
            return cur.rowcount
    finally:
        conn.close()


def set_placement_verified(submission_id: int) -> bool:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE submissions SET placement_verified = 1 WHERE id = ?",
                (submission_id,),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def mark_submission_opened(submission_id: int) -> str:
    """Kurator detayi ilk actiginda zaman damgasi (dinleme kapisi baslangici).
    Idempotent: ikinci acilis ilk damgayi ezmez."""
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE submissions SET opened_at = ? "
                "WHERE id = ? AND opened_at IS NULL",
                (now_iso(), submission_id),
            )
        row = conn.execute(
            "SELECT opened_at FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        return row["opened_at"] if row else ""
    finally:
        conn.close()


def set_sponsored_until(curator_id: int, until_iso: str | None) -> bool:
    """Sponsorlu kurator slotu: katalogda ust sira (admin/odeme sonrasi)."""
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE curators SET sponsored_until = ? WHERE id = ?",
                (until_iso, curator_id),
            )
            return cur.rowcount > 0
    finally:
        conn.close()
