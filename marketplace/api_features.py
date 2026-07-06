"""Gelir ozellikleri API katmani (api.py'ye include edilen router).

Kapsam: kredi paketleri, Artist Pro, referans, public karne/lig/kurator vitrini,
sertifika + kanit karti + etki raporu + EPK, kariyer panosu, otopilot,
yayin takvimi, kurator payout'lari, dinleme kapisi (open), self-servis
yerlesim dogrulama, yayina hazirlik raporu.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from marketplace import accounts, db, growth, premium, pricing, service
from musical_seo import audit as seo_audit
from musical_seo import db as seo_db

router = APIRouter()


def _current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = accounts.user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Giris gerekli")
    return user


def _require_role(user: dict, role: str) -> None:
    if user["role"] != role:
        raise HTTPException(status_code=403, detail=f"Bu islem {role} hesabi ister")


def _require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("MARKETPLACE_ADMIN_KEY")
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Gecersiz admin anahtari")


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --- Kredi paketleri + satin alma talebi -------------------------------------

@router.get("/packages")
def packages() -> dict:
    """Self-servis paket vitrini. Odeme pilotta manuel: talep -> admin onayi."""
    return {
        "packages": [
            {"key": k, **v} for k, v in pricing.PACKAGES.items()
        ],
        "pro": {
            "price_try": pricing.PRO_PRICE_TRY,
            "monthly_credits": pricing.PRO_MONTHLY_CREDITS,
            "sla_hours": pricing.PRO_SLA_HOURS,
        },
    }


class PackageRequest(BaseModel):
    package_key: str


@router.post("/me/packages/request")
def package_request(
    payload: PackageRequest, user: dict = Depends(_current_user)
) -> dict:
    pkg = pricing.PACKAGES.get(payload.package_key)
    if pkg is None:
        raise HTTPException(status_code=400, detail="Gecersiz paket")
    conn = accounts._connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO purchase_requests "
                "(created_at, user_id, package_key, credits, price_try) "
                "VALUES (?, ?, ?, ?, ?)",
                (db.now_iso(), user["id"], payload.package_key,
                 pkg["credits"], pkg["price_try"]),
            )
            req_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM purchase_requests WHERE id = ?", (req_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.get("/admin/purchase-requests")
def admin_purchase_requests(
    status: str = "pending", _: None = Depends(_require_admin_key)
) -> list[dict]:
    conn = accounts._connect()
    try:
        rows = conn.execute(
            "SELECT * FROM purchase_requests WHERE status = ? ORDER BY id",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/admin/purchase-requests/{request_id}/grant")
def admin_purchase_grant(
    request_id: int, _: None = Depends(_require_admin_key)
) -> dict:
    """Odeme (havale/Papara) alindi -> talebi kapat + krediyi yukle."""
    conn = accounts._connect()
    try:
        row = conn.execute(
            "SELECT * FROM purchase_requests WHERE id = ?", (request_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Talep bulunamadi")
        req = dict(row)
        if req["status"] != "pending":
            raise HTTPException(status_code=400, detail="Talep zaten sonuclanmis")
        with conn:
            conn.execute(
                "UPDATE purchase_requests SET status = 'granted' WHERE id = ?",
                (request_id,),
            )
    finally:
        conn.close()
    try:
        return accounts.grant_credits(req["user_id"], req["credits"], "purchase")
    except ValueError as exc:
        raise _400(exc)


# --- Artist Pro + sponsorluk (admin aktivasyonu; odeme manuel) -----------------

class ProActivate(BaseModel):
    user_id: int
    until_iso: str = Field(description="ISO-8601 bitis; bos gecersizlestirme")


@router.post("/admin/pro/activate")
def admin_pro_activate(
    payload: ProActivate, _: None = Depends(_require_admin_key)
) -> dict:
    try:
        return accounts.set_pro_until(payload.user_id, payload.until_iso or None)
    except ValueError as exc:
        raise _400(exc)


class SponsorSet(BaseModel):
    curator_id: int
    until_iso: str = Field(description="ISO-8601 bitis; bos = sponsorluk kaldir")


@router.post("/admin/curators/sponsor")
def admin_sponsor(
    payload: SponsorSet, _: None = Depends(_require_admin_key)
) -> dict:
    if not db.set_sponsored_until(payload.curator_id, payload.until_iso or None):
        raise HTTPException(status_code=404, detail="Curator bulunamadi")
    curator = db.get_curator(payload.curator_id)
    assert curator is not None
    curator.pop("email", None)
    return curator


# --- Referans -------------------------------------------------------------------

@router.get("/me/referral")
def my_referral(user: dict = Depends(_current_user)) -> dict:
    try:
        code = growth.referral_code_for(user["id"])
    except ValueError as exc:
        raise _400(exc)
    return {
        "code": code,
        "bonus_credits": growth.REFERRAL_BONUS_CREDITS,
        "note": "Davet ettigin sanatci ilk gonderimini yapinca ikiniz de "
                f"{growth.REFERRAL_BONUS_CREDITS} kredi kazanirsiniz.",
    }


# --- Bildirimler ------------------------------------------------------------------

@router.get("/me/notifications")
def my_notifications(
    unread_only: bool = False, user: dict = Depends(_current_user)
) -> list[dict]:
    return growth.notifications_for(user["id"], unread_only=unread_only)


@router.post("/me/notifications/read")
def my_notifications_read(user: dict = Depends(_current_user)) -> dict:
    return {"marked": growth.mark_notifications_read(user["id"])}


# --- Paylasilabilir karne + lig ------------------------------------------------------

class KarneShare(BaseModel):
    query: str = Field(min_length=3, description="'Sanatci - Sarki'")
    leaderboard_opt_in: bool | None = None


@router.post("/me/karne/share")
def karne_share(
    payload: KarneShare, user: dict = Depends(_current_user)
) -> dict:
    """Karneyi public linke cevir. Skor + alt skorlar acik, bulgular kilitli."""
    try:
        result = seo_audit.run_audit(payload.query)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    seo_db.save(result)
    data = result.to_dict()
    counts: dict[str, int] = {}
    for f in data.get("findings", []):
        sev = f.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1
    summary = {
        "finding_counts": counts,
        "subscores": data.get("subscores") or data.get("categories") or {},
    }
    token = growth.create_public_report(
        user["id"], data.get("artist") or "", data.get("title") or "",
        float(data.get("score") or 0), summary,
    )
    if payload.leaderboard_opt_in is not None:
        accounts.set_leaderboard_opt_in(user["id"], payload.leaderboard_opt_in)
    return {"token": token, "url": f"/k/{token}"}


@router.get("/public/karne/{token}")
def public_karne(token: str) -> dict:
    report = growth.get_public_report(token)
    if report is None:
        raise HTTPException(status_code=404, detail="Karne bulunamadi")
    return report


@router.get("/public/leaderboard")
def public_leaderboard(limit: int = 20) -> list[dict]:
    return growth.leaderboard(limit=min(limit, 50))


class OptIn(BaseModel):
    opt_in: bool


@router.post("/me/leaderboard-opt-in")
def leaderboard_opt_in(
    payload: OptIn, user: dict = Depends(_current_user)
) -> dict:
    accounts.set_leaderboard_opt_in(user["id"], payload.opt_in)
    return {"opt_in": payload.opt_in}


# --- Kurator vitrin profili ------------------------------------------------------------

@router.get("/public/curators/{curator_id}")
def public_curator_profile(curator_id: int) -> dict:
    profile = growth.curator_public_profile(curator_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Curator bulunamadi")
    return profile


# --- Dinleme kapisi + self-servis yerlesim dogrulama ------------------------------------

@router.post("/me/submissions/{submission_id}/open")
def submission_open(
    submission_id: int, user: dict = Depends(_current_user)
) -> dict:
    """Kurator gonderimi acti: dinleme sayaci baslar. Yanit ancak
    LISTEN_GATE_SECONDS sonra kabul edilir."""
    _require_role(user, "curator")
    sub = db.get_submission(submission_id)
    if sub is None or sub["curator_id"] != user.get("curator_id"):
        raise HTTPException(status_code=404, detail="Gonderim bulunamadi")
    try:
        opened = service.open_submission(submission_id)
    except ValueError as exc:
        raise _400(exc)
    return {
        "opened_at": opened.get("opened_at"),
        "listen_gate_seconds": pricing.LISTEN_GATE_SECONDS,
    }


@router.post("/me/submissions/{submission_id}/verify-placement")
def my_verify_placement(
    submission_id: int, user: dict = Depends(_current_user)
) -> dict:
    """Sanatci kendi kabul edilmis gonderiminin yerlesimini dogrular
    (admin beklemeden). Kontrol ucretsiz; satilan sey sertifika/kart."""
    _require_role(user, "artist")
    sub = db.get_submission(submission_id)
    if sub is None or sub.get("artist_user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Gonderim bulunamadi")
    try:
        return service.verify_placement(submission_id)
    except ValueError as exc:
        raise _400(exc)


# --- Sertifika + kanit karti + etki raporu ------------------------------------------------

@router.get("/me/submissions/{submission_id}/certificate")
def submission_certificate(
    submission_id: int, user: dict = Depends(_current_user)
) -> HTMLResponse:
    _require_role(user, "artist")
    try:
        cert = premium.issue_certificate(submission_id, user)
    except ValueError as exc:
        raise _400(exc)
    return HTMLResponse(premium.certificate_html(cert))


@router.get("/me/submissions/{submission_id}/share-card")
def submission_share_card(
    submission_id: int, user: dict = Depends(_current_user)
) -> Response:
    """Story boyutlu SVG kanit karti (sertifika sahibi icin)."""
    _require_role(user, "artist")
    try:
        cert = premium.issue_certificate(submission_id, user)
    except ValueError as exc:
        raise _400(exc)
    return Response(
        premium.share_card_svg(cert), media_type="image/svg+xml",
        headers={"Content-Disposition":
                 f'inline; filename="kanit-{cert["token"]}.svg"'},
    )


@router.get("/me/submissions/{submission_id}/impact")
def submission_impact(
    submission_id: int, premium_report: bool = False,
    user: dict = Depends(_current_user),
) -> dict:
    _require_role(user, "artist")
    try:
        return premium.impact_report(
            submission_id, user, seo_db.history, premium=premium_report
        )
    except ValueError as exc:
        raise _400(exc)


# --- EPK + kariyer panosu -----------------------------------------------------------------

@router.get("/me/epk")
def my_epk(user: dict = Depends(_current_user)) -> HTMLResponse:
    _require_role(user, "artist")
    try:
        return HTMLResponse(premium.epk_html(user))
    except ValueError as exc:
        raise _400(exc)


@router.get("/me/dashboard")
def my_dashboard(user: dict = Depends(_current_user)) -> dict:
    _require_role(user, "artist")
    growth.detect_score_drops(user["id"], seo_db.history)
    dashboard = premium.career_dashboard(user, seo_db.history)
    dashboard["notifications"] = growth.notifications_for(
        user["id"], unread_only=True
    )
    return dashboard


# --- Yayina hazirlik raporu -----------------------------------------------------------------

@router.get("/me/readiness")
def my_readiness(query: str, user: dict = Depends(_current_user)) -> dict:
    """Gonderim ONCESI metadata denetimi: kurator spam hissetmesin,
    sanatci hazir gitsin. Skor esigi gecerse 'hazir' rozeti."""
    _require_role(user, "artist")
    try:
        result = seo_audit.run_audit(query)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    seo_db.save(result)
    data = result.to_dict()
    score = float(data.get("score") or 0)
    checklist = [
        {"severity": f.get("severity"), "message": f.get("message"),
         "action": f.get("action")}
        for f in data.get("findings", [])
        if f.get("severity") in ("critical", "warn")
    ]
    return {
        "score": score,
        "ready": score >= pricing.READY_BADGE_MIN_SCORE,
        "threshold": pricing.READY_BADGE_MIN_SCORE,
        "checklist": checklist,
    }


# --- Otopilot + yayin takvimi -----------------------------------------------------------------

class AutopilotStart(BaseModel):
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)
    budget_credits: int = Field(ge=2, le=100)


@router.post("/me/autopilot")
def autopilot_start(
    payload: AutopilotStart, user: dict = Depends(_current_user)
) -> dict:
    _require_role(user, "artist")
    try:
        return premium.autopilot(
            user, payload.artist, payload.title, payload.budget_credits,
            service.create_submission,
        )
    except ValueError as exc:
        raise _400(exc)


class ScheduleCreate(BaseModel):
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)
    curator_id: int
    scheduled_at: str = Field(description="ISO-8601 (yayin gunu sabahi gibi)")


@router.post("/me/schedule")
def schedule_create(
    payload: ScheduleCreate, user: dict = Depends(_current_user)
) -> dict:
    _require_role(user, "artist")
    try:
        return premium.schedule_submission(
            user, payload.artist, payload.title, payload.curator_id,
            payload.scheduled_at,
        )
    except ValueError as exc:
        raise _400(exc)


@router.get("/me/schedule")
def schedule_list(user: dict = Depends(_current_user)) -> list[dict]:
    _require_role(user, "artist")
    return premium.list_schedules(user["id"])


# --- Kurator payout'lari -----------------------------------------------------------------------

class PayoutRequest(BaseModel):
    instant: bool = False


@router.post("/me/payouts")
def payout_request(
    payload: PayoutRequest, user: dict = Depends(_current_user)
) -> dict:
    _require_role(user, "curator")
    try:
        return premium.request_payout(user, instant=payload.instant)
    except ValueError as exc:
        raise _400(exc)


@router.get("/me/payouts")
def payout_list(user: dict = Depends(_current_user)) -> list[dict]:
    _require_role(user, "curator")
    return premium.list_payouts(user["id"])


@router.post("/admin/payouts/{payout_id}/paid")
def admin_payout_paid(
    payout_id: int, _: None = Depends(_require_admin_key)
) -> dict:
    try:
        return premium.mark_payout_paid(payout_id)
    except ValueError as exc:
        raise _400(exc)


# --- Tam bakim dongusu (cron) --------------------------------------------------------------------

@router.post("/maintenance/cycle")
def maintenance_cycle(_: None = Depends(_require_admin_key)) -> dict:
    """SLA iade + yerlesim garantisi + planli gonderim + pro tahsis."""
    return premium.maintenance_cycle(service)
