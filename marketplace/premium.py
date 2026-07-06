"""Premium urunler: sertifika, kanit karti, etki raporu, EPK, kariyer panosu,
otopilot, yayin takvimi, kurator payout'lari, Artist Pro aylik tahsis.

Ortak kural: pro kullaniciya premium uretimler ucretsiz, digerlerine kredi
(pricing sabitleri). Is kurali ihlalleri ValueError (Turkce); API 400'e cevirir.
"""
from __future__ import annotations

import html
import secrets
from datetime import datetime, timedelta, timezone

from marketplace import accounts, db, pricing

PRO_GRANT_INTERVAL_DAYS = 30


# --- Yardimcilar --------------------------------------------------------------

def _own_submission(submission_id: int, user: dict) -> dict:
    sub = db.get_submission(submission_id)
    if sub is None or sub.get("artist_user_id") != user["id"]:
        raise ValueError(f"Gonderim bulunamadi: {submission_id}")
    return sub


def _charge_unless_pro(user: dict, amount: int, reason: str,
                       submission_id: int | None = None) -> bool:
    """Pro'ya ucretsiz; degilse kredi dus. Donen deger: ucret alindi mi."""
    if accounts.is_pro(user):
        return False
    accounts.charge_credits(user["id"], amount, reason, submission_id)
    return True


# --- Dogrulanmis yerlesim sertifikasi + kanit karti ----------------------------

def issue_certificate(submission_id: int, user: dict) -> dict:
    """Ilk uretimde ucret alinir ve kalici token yazilir; sonraki cagrilar
    ucretsiz ayni sertifikayi doner. Sart: yerlesim API'den DOGRULANMIS."""
    sub = _own_submission(submission_id, user)
    if not sub.get("placement_verified"):
        raise ValueError(
            "Sertifika icin once yerlesim dogrulamasi gerekli "
            "(kabul edilen gonderimde 'Yerlesimi Dogrula' calistir)"
        )
    token = sub.get("certificate_token")
    if not token:
        _charge_unless_pro(
            user, pricing.CERTIFICATE_COST, "certificate", submission_id
        )
        token = f"CERT-{secrets.token_hex(4).upper()}"
        conn = accounts._connect()
        try:
            with conn:
                conn.execute(
                    "UPDATE submissions SET certificate_token = ? "
                    "WHERE id = ? AND certificate_token IS NULL",
                    (token, submission_id),
                )
            row = conn.execute(
                "SELECT certificate_token FROM submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()
            token = row["certificate_token"]
        finally:
            conn.close()
    curator = db.get_curator(sub["curator_id"]) or {}
    return {
        "token": token,
        "submission_id": submission_id,
        "artist": sub["artist"],
        "title": sub["title"],
        "playlist_title": curator.get("playlist_title", ""),
        "playlist_url": curator.get("playlist_url", ""),
        "fans": curator.get("fans", 0),
        "verified_at": sub.get("responded_at") or sub["created_at"],
    }


def certificate_html(cert: dict) -> str:
    """Bagimsiz API dogrulamali yerlesim sertifikasi — SubmitHub'da olmayan
    kanit. Sanatci EPK/basin kitinde kullanir."""
    e = html.escape
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>Yerlesim Sertifikasi — {e(cert['artist'])}</title></head>
<body style="font-family:Georgia,serif;background:#0d1117;color:#e6edf3;
padding:48px;max-width:720px;margin:auto">
<div style="border:2px solid #d4a017;border-radius:12px;padding:40px;text-align:center">
<p style="letter-spacing:3px;color:#d4a017;font-size:13px">DOGRULANMIS YERLESIM SERTIFIKASI</p>
<h1 style="margin:16px 0 4px">{e(cert['artist'])}</h1>
<h2 style="margin:0;font-weight:normal">“{e(cert['title'])}”</h2>
<p style="margin:24px 0 8px;font-size:15px">
Bu sarkinin <strong>{e(cert['playlist_title'])}</strong> playlist'ine
({cert['fans']} takipci) eklendigi platform API'sinden bagimsiz olarak dogrulanmistir.
</p>
<p style="color:#8b949e;font-size:13px">Dogrulama: {e(str(cert['verified_at'])[:10])}
&nbsp;•&nbsp; Sertifika No: {e(cert['token'])}</p>
<p style="margin-top:24px"><a href="{e(cert['playlist_url'])}"
style="color:#d4a017">Playlist'i gor</a></p>
</div></body></html>"""


def share_card_svg(cert: dict) -> str:
    """Instagram Story boyutlu markali kanit karti (SVG). Sertifika ile gelir."""
    e = html.escape
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920"
viewBox="0 0 1080 1920">
<rect width="1080" height="1920" fill="#0d1117"/>
<rect x="60" y="560" width="960" height="800" rx="32" fill="#161b22"
stroke="#d4a017" stroke-width="4"/>
<text x="540" y="700" text-anchor="middle" fill="#d4a017" font-size="36"
font-family="Georgia" letter-spacing="8">DOGRULANMIS YERLESIM</text>
<text x="540" y="840" text-anchor="middle" fill="#e6edf3" font-size="72"
font-family="Georgia" font-weight="bold">{e(cert['artist'])}</text>
<text x="540" y="940" text-anchor="middle" fill="#e6edf3" font-size="52"
font-family="Georgia">“{e(cert['title'])}”</text>
<text x="540" y="1080" text-anchor="middle" fill="#8b949e" font-size="40"
font-family="Georgia">{e(cert['playlist_title'])}</text>
<text x="540" y="1150" text-anchor="middle" fill="#8b949e" font-size="34"
font-family="Georgia">{cert['fans']} takipci • API kanitli</text>
<text x="540" y="1290" text-anchor="middle" fill="#d4a017" font-size="30"
font-family="Georgia">{e(cert['token'])}</text>
</svg>"""


# --- Yerlesim sonrasi etki raporu ----------------------------------------------

def impact_report(submission_id: int, user: dict, history_fn,
                  premium: bool = False) -> dict:
    """Yerlesim oncesi/sonrasi metrik degisimi (snapshot zaman serisinden).

    Temel rapor ucretsiz (guven insasi); premium=True markali HTML icin
    kredi ister (pro ucretsiz). history_fn enjekte edilir (test edilebilir).
    """
    sub = _own_submission(submission_id, user)
    if sub["status"] != "accepted":
        raise ValueError("Etki raporu sadece kabul edilen gonderimler icin")
    pivot = sub.get("responded_at") or sub["created_at"]
    rows = sorted(
        history_fn(sub["artist"], sub["title"]),
        key=lambda r: r.get("created_at") or "",
    )
    before = [r for r in rows if (r.get("created_at") or "") <= pivot]
    after = [r for r in rows if (r.get("created_at") or "") > pivot]

    def _avg(items, key):
        vals = [r[key] for r in items if r.get(key) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    report = {
        "submission_id": submission_id,
        "artist": sub["artist"],
        "title": sub["title"],
        "placement_verified": bool(sub.get("placement_verified")),
        "pivot": pivot,
        "data_points": len(rows),
        "before": {"score": _avg(before, "score"),
                   "spotify_popularity": _avg(before, "spotify_popularity")},
        "after": {"score": _avg(after, "score"),
                  "spotify_popularity": _avg(after, "spotify_popularity")},
        "premium": False,
    }
    b, a = report["before"]["score"], report["after"]["score"]
    report["score_delta"] = round(a - b, 1) if (a is not None and b is not None) else None
    if premium:
        _charge_unless_pro(
            user, pricing.IMPACT_REPORT_COST, "impact_report", submission_id
        )
        report["premium"] = True
    return report


# --- EPK (elektronik basin kiti) --------------------------------------------------

def epk_data(user: dict) -> dict:
    """EPK verisi: dogrulanmis yerlesimler + sertifikalar + son karne skorlari."""
    subs = db.list_submissions(artist_user_id=user["id"])
    verified = [s for s in subs if s.get("placement_verified")]
    conn = accounts._connect()
    try:
        reports = [
            dict(r) for r in conn.execute(
                "SELECT artist, title, score, created_at FROM public_reports "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
                (user["id"],),
            ).fetchall()
        ]
    finally:
        conn.close()
    placements = []
    for s in verified:
        curator = db.get_curator(s["curator_id"]) or {}
        placements.append({
            "artist": s["artist"], "title": s["title"],
            "playlist_title": curator.get("playlist_title", ""),
            "fans": curator.get("fans", 0),
            "verified_at": s.get("responded_at") or s["created_at"],
        })
    return {"name": user["name"], "placements": placements, "reports": reports}


def epk_html(user: dict) -> str:
    """Tek tikla EPK: pro ucretsiz, digerine EPK_COST kredi."""
    _charge_unless_pro(user, pricing.EPK_COST, "epk")
    data = epk_data(user)
    e = html.escape
    rows = "".join(
        f"<li><strong>{e(p['artist'])} — {e(p['title'])}</strong>: "
        f"{e(p['playlist_title'])} ({p['fans']} takipci, "
        f"API dogrulamali, {e(str(p['verified_at'])[:10])})</li>"
        for p in data["placements"]
    ) or "<li>Henuz dogrulanmis yerlesim yok</li>"
    scores = "".join(
        f"<li>{e(r['artist'])} — {e(r['title'])}: SEO skoru {r['score']:.0f}</li>"
        for r in data["reports"]
    )
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>EPK — {e(data['name'])}</title></head>
<body style="font-family:Georgia,serif;background:#fff;color:#111;
padding:48px;max-width:760px;margin:auto">
<h1 style="border-bottom:3px solid #d4a017;padding-bottom:8px">{e(data['name'])}</h1>
<h2>Dogrulanmis Playlist Yerlesimeleri</h2>
<ul>{rows}</ul>
<h2>SEO Karne Skorlari</h2>
<ul>{scores or '<li>Henuz karne yok</li>'}</ul>
<p style="color:#888;font-size:13px">Tum yerlesimler platform API'sinden
bagimsiz dogrulanmistir — beyan degil, kanit.</p>
</body></html>"""


# --- A&R kariyer panosu -------------------------------------------------------------

def career_dashboard(user: dict, history_fn) -> dict:
    """Gonderim hunisi + parca trendleri + kohort kiyaslamasi.

    Kohort benchmark (ayni havuzdaki diger sanatcilarin ortalama skoru)
    SADECE pro'ya acilir — abonelik katmaninin sattigi sey bu.
    """
    subs = db.list_submissions(artist_user_id=user["id"])
    funnel = {"total": len(subs)}
    for status in ("pending", "accepted", "rejected", "expired"):
        funnel[status] = sum(1 for s in subs if s["status"] == status)
    funnel["verified_placements"] = sum(
        1 for s in subs if s.get("placement_verified")
    )
    spent = sum(s.get("cost_credits") or 1 for s in subs)

    tracks = []
    for artist, title in {(s["artist"], s["title"]) for s in subs}:
        try:
            rows = sorted(
                history_fn(artist, title), key=lambda r: r.get("created_at") or ""
            )
        except Exception:
            rows = []
        if rows:
            tracks.append({
                "artist": artist, "title": title,
                "latest_score": rows[-1].get("score"),
                "trend": [
                    {"created_at": r["created_at"], "score": r.get("score")}
                    for r in rows[-12:]
                ],
            })

    result = {
        "funnel": funnel,
        "credits_spent": spent,
        "tracks": sorted(
            tracks, key=lambda t: t["latest_score"] or 0, reverse=True
        ),
        "pro": accounts.is_pro(user),
        "cohort": None,
    }
    if result["pro"]:
        conn = accounts._connect()
        try:
            row = conn.execute(
                "SELECT AVG(score) AS avg_score, COUNT(DISTINCT user_id) AS artists "
                "FROM public_reports"
            ).fetchone()
        finally:
            conn.close()
        result["cohort"] = {
            "avg_score": round(row["avg_score"], 1) if row["avg_score"] else None,
            "artists": row["artists"] or 0,
        }
    return result


# --- Otopilot (yonetilen kredi harcamasi) ---------------------------------------------

def autopilot(user: dict, artist: str, title: str, budget_credits: int,
              create_fn) -> dict:
    """Krediyi beklenen-ROI sirali kuratorlere otomatik dagit.

    Siralama: response_rate * success_rate (veri yoksa notr 50/25 varsayimi),
    esitlikte kalite skoru. Ayni parcayi ayni kuratore ikinci kez gondermez.
    Servis ucreti AUTOPILOT_FEE (pro ucretsiz). create_fn enjekte edilir
    (service.create_submission; test edilebilirlik + dongusel import yok).
    """
    if budget_credits < 2:
        raise ValueError("Otopilot icin en az 2 kredi butce gerekli")
    already = {
        s["curator_id"] for s in db.list_submissions(artist_user_id=user["id"])
        if s["artist"] == artist and s["title"] == title
    }
    all_stats = db.curator_stats()

    def _roi(curator: dict) -> tuple:
        stats = all_stats.get(curator["id"]) or {}
        rr = stats.get("response_rate")
        sr = stats.get("success_rate")
        expected = (rr if rr is not None else 50) * (sr if sr is not None else 25)
        return (expected, curator.get("quality_score") or 0)

    candidates = sorted(
        (c for c in db.list_curators(status="approved") if c["id"] not in already),
        key=_roi, reverse=True,
    )
    _charge_unless_pro(user, pricing.AUTOPILOT_FEE, "autopilot")

    created, spent, errors = [], 0, []
    for curator in candidates:
        remaining_budget = budget_credits - spent
        if remaining_budget <= 0:
            break
        # Butce disiplini: kuratorun maliyetini ONCE hesapla, butceyi
        # asacaksa hic gonderme (surpriz harcama yok).
        stats = all_stats.get(curator["id"])
        est_cost = pricing.total_submission_cost(
            pricing.submission_cost(
                pricing.curator_tier(
                    curator.get("quality_score") or 0.0,
                    curator.get("fans") or 0,
                    response_rate=(stats or {}).get("response_rate"),
                    success_rate=(stats or {}).get("success_rate"),
                ),
                curator.get("curator_type") or "playlist",
                pro_artist=accounts.is_pro(user),
            )
        )
        if est_cost > remaining_budget:
            continue
        try:
            sub = create_fn(artist, title, curator["id"],
                            artist_user_id=user["id"])
        except ValueError as exc:
            errors.append({"curator_id": curator["id"], "error": str(exc)})
            continue
        spent += sub.get("cost_credits") or 1
        created.append(sub)
    return {"created": created, "spent": spent, "errors": errors}


# --- Yayin plani (zamanlanmis gonderim) ---------------------------------------------

def schedule_submission(user: dict, artist: str, title: str,
                        curator_id: int, scheduled_at: str) -> dict:
    when = datetime.fromisoformat(scheduled_at)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if when <= datetime.now(timezone.utc):
        raise ValueError("Zamanlanmis gonderim gelecekte olmali")
    if db.get_curator(curator_id) is None:
        raise ValueError(f"Curator bulunamadi: {curator_id}")
    conn = accounts._connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO scheduled_submissions "
                "(created_at, artist_user_id, artist, title, curator_id, scheduled_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (db.now_iso(), user["id"], artist, title, curator_id,
                 when.isoformat()),
            )
            row_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM scheduled_submissions WHERE id = ?", (row_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_schedules(user_id: int) -> list[dict]:
    conn = accounts._connect()
    try:
        rows = conn.execute(
            "SELECT * FROM scheduled_submissions WHERE artist_user_id = ? "
            "ORDER BY scheduled_at ASC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def run_due_schedules(create_fn) -> dict:
    """Zamani gelen planli gonderimleri calistir (cron). Kredi yetersizse
    failed + hata mesaji yazilir; sanatci panelde gorur."""
    conn = accounts._connect()
    try:
        due = [
            dict(r) for r in conn.execute(
                "SELECT * FROM scheduled_submissions "
                "WHERE status = 'pending' AND scheduled_at <= ?",
                (db.now_iso(),),
            ).fetchall()
        ]
    finally:
        conn.close()
    executed = failed = 0
    for item in due:
        try:
            sub = create_fn(item["artist"], item["title"], item["curator_id"],
                            artist_user_id=item["artist_user_id"])
            status, sub_id, error = "executed", sub["id"], None
            executed += 1
        except ValueError as exc:
            status, sub_id, error = "failed", None, str(exc)
            failed += 1
        conn = accounts._connect()
        try:
            with conn:
                conn.execute(
                    "UPDATE scheduled_submissions "
                    "SET status = ?, submission_id = ?, error = ? "
                    "WHERE id = ? AND status = 'pending'",
                    (status, sub_id, error, item["id"]),
                )
        finally:
            conn.close()
    return {"executed": executed, "failed": failed}


# --- Artist Pro aylik tahsis -----------------------------------------------------------

def grant_pro_monthly() -> int:
    """Aktif pro abonelerine 30 gunde bir PRO_MONTHLY_CREDITS yukle (cron).
    last_pro_grant cift tahsisi engeller."""
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=PRO_GRANT_INTERVAL_DAYS)).isoformat()
    conn = accounts._connect()
    try:
        rows = [
            dict(r) for r in conn.execute(
                "SELECT id FROM users WHERE pro_until > ? "
                "AND (last_pro_grant IS NULL OR last_pro_grant <= ?)",
                (now.isoformat(), cutoff),
            ).fetchall()
        ]
        granted = 0
        for row in rows:
            with conn:
                cur = conn.execute(
                    "UPDATE users SET credits = credits + ?, last_pro_grant = ? "
                    "WHERE id = ? AND (last_pro_grant IS NULL OR last_pro_grant <= ?)",
                    (pricing.PRO_MONTHLY_CREDITS, now.isoformat(), row["id"], cutoff),
                )
                if cur.rowcount:
                    conn.execute(
                        "INSERT INTO transactions "
                        "(created_at, user_id, delta, reason, submission_id) "
                        "VALUES (?, ?, ?, 'pro_monthly', NULL)",
                        (db.now_iso(), row["id"], pricing.PRO_MONTHLY_CREDITS),
                    )
                    granted += 1
        return granted
    finally:
        conn.close()


# --- Kurator payout'lari -----------------------------------------------------------------

def request_payout(user: dict, instant: bool = False) -> dict:
    """Tahakkuk etmis kazanci odemeye cevir.

    Standart: PAYOUT_MIN_USD esigi, kesinti yok. Aninda: esik yok,
    INSTANT_PAYOUT_FEE_RATE kesinti. earnings accrued -> requested;
    odeme yapilinca admin mark_payout_paid ile paid'e cevirir.
    """
    earnings = accounts.earnings_for(user["id"])
    pending = earnings["pending_usd"]
    if pending <= 0:
        raise ValueError("Odenecek tahakkuk yok")
    if not instant and pending < pricing.PAYOUT_MIN_USD:
        raise ValueError(
            f"Standart odeme esigi ${pricing.PAYOUT_MIN_USD:.0f} — "
            f"bakiyen ${pending:.2f}. Aninda odeme (%{int(pricing.INSTANT_PAYOUT_FEE_RATE*100)} "
            "kesintili) secebilirsin."
        )
    fee = pricing.instant_payout_fee(pending) if instant else 0.0
    conn = accounts._connect()
    try:
        with conn:
            conn.execute(
                "UPDATE earnings SET status = 'requested' "
                "WHERE curator_user_id = ? AND status = 'accrued'",
                (user["id"],),
            )
            cur = conn.execute(
                "INSERT INTO payouts "
                "(created_at, curator_user_id, amount_usd, fee_usd, instant) "
                "VALUES (?, ?, ?, ?, ?)",
                (db.now_iso(), user["id"], round(pending - fee, 2), fee,
                 int(instant)),
            )
            payout_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM payouts WHERE id = ?", (payout_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_payouts(user_id: int) -> list[dict]:
    conn = accounts._connect()
    try:
        rows = conn.execute(
            "SELECT * FROM payouts WHERE curator_user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_payout_paid(payout_id: int) -> dict:
    """Admin: havale yapildi -> payout + ilgili earnings 'paid'."""
    conn = accounts._connect()
    try:
        row = conn.execute(
            "SELECT * FROM payouts WHERE id = ?", (payout_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Payout bulunamadi: {payout_id}")
        payout = dict(row)
        if payout["status"] == "paid":
            return payout
        with conn:
            conn.execute(
                "UPDATE payouts SET status = 'paid' WHERE id = ?", (payout_id,)
            )
            conn.execute(
                "UPDATE earnings SET status = 'paid' "
                "WHERE curator_user_id = ? AND status = 'requested'",
                (payout["curator_user_id"],),
            )
        updated = conn.execute(
            "SELECT * FROM payouts WHERE id = ?", (payout_id,)
        ).fetchone()
        return dict(updated)
    finally:
        conn.close()


# --- Bakim dongusu (cron hedefi) -------------------------------------------------------------

def maintenance_cycle(service_module) -> dict:
    """Tek cron girisi: SLA iade + yerlesim garantisi + planli gonderimler +
    pro aylik tahsis. service_module enjekte edilir (dongusel import yok)."""
    result = service_module.expire_and_refund()
    result["placement_guarantee"] = service_module.enforce_placement_guarantee()
    result["schedules"] = run_due_schedules(service_module.create_submission)
    result["pro_grants"] = grant_pro_monthly()
    return result
