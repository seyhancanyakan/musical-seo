"""Cover/Derivative Avcisi API katmani (api.py'ye include edilecek router).

Kapsam: tek seferlik av baslatma (kredi/pro), rapor + aday listesi goruntuleme,
aday karari (approved/rejected), lisans teklifi uretimi, surekli izleme
(watchdog) aktivasyonu.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from marketplace import accounts, cover_hunter, pricing

router = APIRouter()


def _current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = accounts.user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Giriş gerekli")
    return user


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _charge_unless_pro(user: dict, amount: int, reason: str) -> None:
    """Pro kullaniciya ucretsiz; degilse kredi dus (ValueError yetersiz
    bakiyede — cagiran _400'e cevirir)."""
    if not accounts.is_pro(user):
        accounts.charge_credits(user["id"], amount, reason)


# --- Av baslatma --------------------------------------------------------------

class HuntStart(BaseModel):
    track_query: str


@router.post("/cover-hunt/start")
def start_hunt(payload: HuntStart, user: dict = Depends(_current_user)) -> dict:
    try:
        _charge_unless_pro(user, pricing.COVER_HUNT_COST, "cover_hunt")
        return cover_hunter.run_cover_hunt(user["id"], payload.track_query)
    except ValueError as exc:
        raise _400(exc)


# --- Rapor + adaylar ------------------------------------------------------------

@router.get("/cover-hunt/report/{token}")
def get_report(token: str) -> dict:
    report = cover_hunter.get_report(token)
    if report is None:
        raise HTTPException(status_code=404, detail="Av raporu bulunamadı")
    return report


@router.get("/cover-hunt/candidates")
def list_candidates(hunt_id: int, status: str | None = None) -> list[dict]:
    return cover_hunter.candidates_for(hunt_id, status)


# --- Aday karari + lisans -----------------------------------------------------

class CandidateReview(BaseModel):
    verdict: str


@router.post("/cover-hunt/candidates/{candidate_id}/review")
def review_candidate(
    candidate_id: int, payload: CandidateReview, user: dict = Depends(_current_user)
) -> dict:
    try:
        return cover_hunter.review_candidate(user["id"], candidate_id, payload.verdict)
    except ValueError as exc:
        raise _400(exc)


@router.post("/cover-hunt/candidates/{candidate_id}/license")
def license_candidate(
    candidate_id: int, user: dict = Depends(_current_user)
) -> dict:
    try:
        return cover_hunter.generate_license_offer(candidate_id)
    except ValueError as exc:
        raise _400(exc)


# --- Watchdog (surekli izleme) ------------------------------------------------

class WatchdogEnable(BaseModel):
    track_query: str


@router.post("/cover-hunt/watchdog/enable")
def watchdog_enable(
    payload: WatchdogEnable, user: dict = Depends(_current_user)
) -> dict:
    try:
        _charge_unless_pro(user, pricing.COVER_HUNT_WATCHDOG_COST, "cover_hunt_watchdog")
        return cover_hunter.enable_watchdog(user["id"], payload.track_query)
    except ValueError as exc:
        raise _400(exc)
