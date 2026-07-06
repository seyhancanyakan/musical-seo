"""Buyume katmani: referans kredisi, paylasilabilir karne, lig, kurator vitrini,
bildirimler.

Viral dongu: sanatci karnesini/kanitini paylasir -> yeni sanatci gelir ->
referans kredisi iki tarafa da yazilir -> kredi harcama aliskanligi olusur.
Is kurali ihlalleri ValueError (Turkce); API katmani 400'e cevirir.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from marketplace import accounts, db

REFERRAL_BONUS_CREDITS = 1   # davet eden + edilen, ilk gonderimde birer kredi
LEADERBOARD_LIMIT = 20
DROP_ALERT_MIN_DELTA = 5.0   # skor bu kadar dustuyse uyari uret


# --- Referans sistemi -------------------------------------------------------

def referral_code_for(user_id: int) -> str:
    """Kullanicinin referans kodu; eski hesaplarda yoksa uretilir."""
    user = accounts.get_user(user_id)
    if user is None:
        raise ValueError(f"Kullanici bulunamadi: {user_id}")
    if user.get("referral_code"):
        return user["referral_code"]
    code = f"REF-{secrets.token_hex(3).upper()}"
    conn = accounts._connect()
    try:
        with conn:
            conn.execute(
                "UPDATE users SET referral_code = ? "
                "WHERE id = ? AND referral_code IS NULL",
                (code, user_id),
            )
        row = conn.execute(
            "SELECT referral_code FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row["referral_code"]
    finally:
        conn.close()


def apply_referral_bonus(user_id: int) -> bool:
    """Davet edilen kullanicinin ILK gonderiminde iki tarafa da bonus kredi.

    Idempotent: kullaniciya daha once 'referral_bonus' yazildiysa atlanir.
    Tek transaction: iki tarafa kredi + iki defter kaydi birlikte yazilir.
    """
    user = accounts.get_user(user_id)
    if user is None or not user.get("referred_by"):
        return False
    referrer_id = int(user["referred_by"])
    conn = accounts._connect()
    try:
        with conn:
            existing = conn.execute(
                "SELECT 1 FROM transactions "
                "WHERE user_id = ? AND reason = 'referral_bonus' LIMIT 1",
                (user_id,),
            ).fetchone()
            if existing:
                return False
            for uid in (user_id, referrer_id):
                conn.execute(
                    "UPDATE users SET credits = credits + ? WHERE id = ?",
                    (REFERRAL_BONUS_CREDITS, uid),
                )
                conn.execute(
                    "INSERT INTO transactions "
                    "(created_at, user_id, delta, reason, submission_id) "
                    "VALUES (?, ?, ?, 'referral_bonus', NULL)",
                    (db.now_iso(), uid, REFERRAL_BONUS_CREDITS),
                )
            return True
    finally:
        conn.close()


# --- Paylasilabilir karne (freemium kilit) -----------------------------------

def create_public_report(user_id: int, artist: str, title: str,
                         score: float, summary: dict) -> str:
    """Karneyi public token'li linke cevir. Ayni (user, artist, title) icin
    yeni cagri yeni snapshot uretir (skor guncellenmis olabilir)."""
    if accounts.get_user(user_id) is None:
        raise ValueError(f"Kullanici bulunamadi: {user_id}")
    token = f"KRN-{secrets.token_hex(5).upper()}"
    conn = accounts._connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO public_reports "
                "(created_at, token, user_id, artist, title, score, summary_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (db.now_iso(), token, user_id, artist, title, score,
                 json.dumps(summary, ensure_ascii=False)),
            )
    finally:
        conn.close()
    return token


def get_public_report(token: str) -> dict | None:
    """Public karne: skor + ozet ACIK, bulgu detaylari KILITLI (freemium).

    Kilidin arkasindaki detay (bulgular + aksiyon onerileri) yalnizca hesapla
    /karne uzerinden gorunur — paylasan link trafigi kayita donusur.
    """
    conn = accounts._connect()
    try:
        row = conn.execute(
            "SELECT * FROM public_reports WHERE token = ?", (token,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    data = dict(row)
    summary = json.loads(data.pop("summary_json") or "{}")
    return {
        "token": data["token"],
        "artist": data["artist"],
        "title": data["title"],
        "score": data["score"],
        "created_at": data["created_at"],
        "finding_counts": summary.get("finding_counts", {}),
        "subscores": summary.get("subscores", {}),
        "locked": True,  # bulgu detaylari + aksiyon onerileri kilitli
    }


def leaderboard(limit: int = LEADERBOARD_LIMIT) -> list[dict]:
    """Karne Ligi: opt-in kullanicilarin en iyi guncel skorlari (public).

    Her (artist, title) icin en guncel raporun skoru; sadece
    leaderboard_opt_in=1 kullanicilar listelenir (gizlilik varsayilani kapali).
    """
    conn = accounts._connect()
    try:
        rows = conn.execute(
            """
            SELECT pr.artist, pr.title, pr.score, pr.created_at, pr.token
            FROM public_reports pr
            JOIN users u ON u.id = pr.user_id
            WHERE u.leaderboard_opt_in = 1
              AND pr.id = (
                  SELECT id FROM public_reports p2
                  WHERE p2.artist = pr.artist AND p2.title = pr.title
                  ORDER BY created_at DESC LIMIT 1
              )
            ORDER BY pr.score DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Kurator vitrin profili ---------------------------------------------------

def curator_public_profile(curator_id: int) -> dict | None:
    """Public kurator profili: dogrulanmis yerlesim sayisi API kanitli —
    self-reported degil. Kurator bunu sosyal medyasinda paylasip gonderim
    ceker (arz tarafinin pazarlama silahi)."""
    curator = db.get_curator(curator_id)
    if curator is None:
        return None
    stats = db.curator_stats(curator_id).get(curator_id) or {}
    conn = accounts._connect()
    try:
        verified = conn.execute(
            "SELECT COUNT(*) AS n FROM submissions "
            "WHERE curator_id = ? AND placement_verified = 1",
            (curator_id,),
        ).fetchone()["n"]
    finally:
        conn.close()
    return {
        "id": curator["id"],
        "name": curator["name"],
        "curator_type": curator.get("curator_type") or "playlist",
        "playlist_title": curator["playlist_title"],
        "playlist_url": curator["playlist_url"],
        "fans": curator["fans"],
        "track_count": curator["track_count"],
        "quality_score": curator["quality_score"],
        "ownership_verified": curator.get("ownership_verified") or 0,
        "verified_placements": verified,
        "sponsored": is_sponsored(curator),
        "stats": stats,
    }


def is_sponsored(curator: dict, now: datetime | None = None) -> bool:
    sponsored_until = curator.get("sponsored_until")
    if not sponsored_until:
        return False
    return datetime.fromisoformat(sponsored_until) > (
        now or datetime.now(timezone.utc)
    )


# --- Bildirimler (dusus uyarisi vb.) -------------------------------------------

def add_notification(user_id: int, kind: str, message: str,
                     dedupe_same_day: bool = True) -> bool:
    """Bildirim ekle. dedupe_same_day: ayni gun ayni (kind, message) tekrar
    yazilmaz — cron her calistiginda ayni uyariyi coklamaz."""
    conn = accounts._connect()
    try:
        with conn:
            if dedupe_same_day:
                today = db.now_iso()[:10]
                existing = conn.execute(
                    "SELECT 1 FROM notifications "
                    "WHERE user_id = ? AND kind = ? AND message = ? "
                    "AND substr(created_at, 1, 10) = ? LIMIT 1",
                    (user_id, kind, message, today),
                ).fetchone()
                if existing:
                    return False
            conn.execute(
                "INSERT INTO notifications (created_at, user_id, kind, message) "
                "VALUES (?, ?, ?, ?)",
                (db.now_iso(), user_id, kind, message),
            )
            return True
    finally:
        conn.close()


def notifications_for(user_id: int, unread_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM notifications WHERE user_id = ?"
    params: list = [user_id]
    if unread_only:
        sql += " AND read = 0"
    sql += " ORDER BY id DESC LIMIT 100"
    conn = accounts._connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def mark_notifications_read(user_id: int) -> int:
    conn = accounts._connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE notifications SET read = 1 WHERE user_id = ? AND read = 0",
                (user_id,),
            )
            return cur.rowcount
    finally:
        conn.close()


def detect_score_drops(user_id: int, history_fn) -> int:
    """Kullanicinin gonderim yaptigi parcalarin son iki snapshot'ini kiyasla;
    DROP_ALERT_MIN_DELTA'dan fazla dusus varsa bildirim uret.

    history_fn: (artist, title) -> [{created_at, score, ...}] (seo_db.history;
    test edilebilirlik icin enjekte edilir). Donen deger: uretilen uyari sayisi.
    """
    tracks = {
        (s["artist"], s["title"])
        for s in db.list_submissions(artist_user_id=user_id)
    }
    alerts = 0
    for artist, title in tracks:
        try:
            rows = sorted(
                history_fn(artist, title), key=lambda r: r.get("created_at") or ""
            )
        except Exception:
            continue
        if len(rows) < 2:
            continue
        prev, last = rows[-2], rows[-1]
        prev_score, last_score = prev.get("score"), last.get("score")
        if prev_score is None or last_score is None:
            continue
        delta = float(prev_score) - float(last_score)
        if delta >= DROP_ALERT_MIN_DELTA:
            if add_notification(
                user_id, "score_drop",
                f"{artist} - {title}: SEO skoru {delta:.0f} puan dustu "
                f"({prev_score:.0f} -> {last_score:.0f}). Yeni playlist onerisi al.",
            ):
                alerts += 1
    return alerts
