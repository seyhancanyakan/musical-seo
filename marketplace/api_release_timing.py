"""Optimum Yayin Tarihi Optimizatoru API katmani (api.py'ye include edilecek
router).

Kapsam: sanatci sarki sorgusu + hedef yayin tarihi verir, 4 sinyalli analiz
(hazirlik/anahtar kelime rekabeti/rakip yayinlar/gun optimizasyonu) uretilir,
rapor kaydedilir; token ile tekrar okunabilir, gecmis listelenebilir.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from marketplace import accounts, pricing
from musical_seo import release_timing

router = APIRouter()


def _current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = accounts.user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Giriş gerekli")
    return user


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


class AdviseRequest(BaseModel):
    track_query: str = Field(min_length=1)
    target_date: str = Field(description="YYYY-MM-DD")


@router.post("/release-timing/advise")
def advise(
    payload: AdviseRequest, user: dict = Depends(_current_user)
) -> dict:
    """Format hatasinda ucret alinmaz (once validate); sonra pro degilse
    RELEASE_TIMING_REPORT_COST dusulur, analiz uretilip kaydedilir."""
    try:
        release_timing.validate_date_format(payload.target_date)
    except ValueError as exc:
        raise _400(exc)

    if not accounts.is_pro(user):
        try:
            accounts.charge_credits(
                user["id"], pricing.RELEASE_TIMING_REPORT_COST, "release_timing"
            )
        except ValueError as exc:
            raise _400(exc)

    try:
        advice = release_timing.advise_release(payload.track_query, payload.target_date)
    except ValueError as exc:
        raise _400(exc)
    return release_timing.save_report(user["id"], advice)


@router.get("/release-timing/report/{token}")
def get_report(token: str) -> dict:
    report = release_timing.get_report(token)
    if report is None:
        raise HTTPException(status_code=404, detail="Rapor bulunamadı")
    return report


@router.get("/release-timing/history")
def history(user: dict = Depends(_current_user)) -> list[dict]:
    return release_timing.reports_for_user(user["id"])
