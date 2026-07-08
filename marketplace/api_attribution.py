"""Promosyon ROI Atif Motoru API katmani (api.py'ye include edilecek router).

Kapsam: kullanici SEO skoru + playlist yerlesimi + radyo yayini uc veri
akisini birlestiren atif raporu talep eder (pro'ya ucretsiz, digerine kredi),
raporu token ile goruntuler, gecmis raporlarini listeler.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from marketplace import accounts, attribution, pricing

router = APIRouter()


def _current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = accounts.user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Giriş gerekli")
    return user


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --- Rapor talebi + gorunumu ---------------------------------------------------

class ReportRequest(BaseModel):
    track_query: str
    period_start: str
    period_end: str


@router.post("/attribution/report")
def create_report(
    payload: ReportRequest, user: dict = Depends(_current_user)
) -> dict:
    if not accounts.is_pro(user):
        try:
            accounts.charge_credits(
                user["id"], pricing.ATTRIBUTION_REPORT_COST, "attribution_report"
            )
        except ValueError as exc:
            raise _400(exc)
    return attribution.build_attribution_report(
        user["id"], payload.track_query, payload.period_start, payload.period_end,
    )


@router.get("/attribution/report/{token}")
def report_by_token(token: str) -> dict:
    report = attribution.get_report(token)
    if report is None:
        raise HTTPException(status_code=404, detail="Rapor bulunamadı")
    return report


@router.get("/attribution/history")
def report_history(user: dict = Depends(_current_user)) -> list[dict]:
    return attribution.reports_for_user(user["id"])
