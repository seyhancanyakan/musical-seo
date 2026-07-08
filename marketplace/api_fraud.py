"""Sahte Playlist Dedektoru API katmani (api.py'ye include edilecek router).

Kapsam: giris yapmis kullanici bir playlist URL'i icin adli analiz ister
(pro'ya ucretsiz, digerine FRAUD_REPORT_COST kredi), token ile raporu tekrar
gorur, gecmis raporlarini listeler.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from marketplace import accounts, fraud_forensics, pricing

router = APIRouter()


def _current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = accounts.user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Giriş gerekli")
    return user


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


class AnalyzeRequest(BaseModel):
    playlist_url: str


@router.post("/fraud/analyze")
def analyze_playlist(
    payload: AnalyzeRequest, user: dict = Depends(_current_user)
) -> dict:
    try:
        if not accounts.is_pro(user):
            accounts.charge_credits(user["id"], pricing.FRAUD_REPORT_COST, "fraud_report")
        return fraud_forensics.analyze_playlist(payload.playlist_url, user)
    except ValueError as exc:
        raise _400(exc)


@router.get("/fraud/report/{token}")
def get_report(token: str) -> dict:
    # Paylasilabilir rapor: token tahmin edilemez (secrets); GET public,
    # diger nis raporlariyla (attribution/release/cover) tutarli + "Raporu
    # paylas" akisi calissin.
    report = fraud_forensics.get_report(token)
    if report is None:
        raise HTTPException(status_code=404, detail="Rapor bulunamadi")
    return report


@router.get("/fraud/history")
def history(user: dict = Depends(_current_user)) -> list[dict]:
    return fraud_forensics.reports_for_user(user["id"])
