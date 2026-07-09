"""Sahte Playlist Dedektoru API katmani (api.py'ye include edilecek router).

Kapsam: giris yapmis kullanici bir playlist URL'i icin adli analiz ister
(pro'ya ucretsiz, digerine FRAUD_REPORT_COST kredi), token ile raporu tekrar
gorur, gecmis raporlarini listeler.
"""
from __future__ import annotations

import json
import queue
import threading

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
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


@router.post("/fraud/analyze/stream")
def analyze_playlist_stream(
    payload: AnalyzeRequest, user: dict = Depends(_current_user)
) -> StreamingResponse:
    """Adli analizin CANLI akisi (SSE) — sayfa asama asama VFX cizer.

    EventSource kimlik dogrulama header'i tasiyamadigi icin POST + fetch/
    ReadableStream kullanilir (bkz. web/lib/api.ts analyzeFraudStream).
    Kredi (pro degilse) akis BASLAMADAN ONCE dusulur — yetersizse 400,
    hicbir is parcacigi baslamaz. Olay: data: {"stage":...,"msg":...,
    "data":{...}|null}. Asamalar: resolve, snapshot, audio, seo, signals,
    done, error. 'done' olayi /fraud/analyze ile ayni sekilli raporu tasir.
    """
    try:
        if not accounts.is_pro(user):
            accounts.charge_credits(user["id"], pricing.FRAUD_REPORT_COST, "fraud_report")
    except ValueError as exc:
        raise _400(exc)

    event_queue: queue.Queue = queue.Queue()

    def emit(event: dict) -> None:
        event_queue.put(event)

    def work() -> None:
        try:
            fraud_forensics.analyze_playlist(
                payload.playlist_url, user, progress=emit
            )
        except ValueError as exc:
            emit({"stage": "error", "msg": str(exc), "data": None})
        except Exception as exc:  # is parcaciginda yutulmasin, kullaniciya aksin
            emit({"stage": "error", "msg": f"Beklenmeyen hata: {exc}", "data": None})
        finally:
            event_queue.put(None)  # akis sonu isareti

    threading.Thread(target=work, daemon=True).start()

    def sse():
        while True:
            event = event_queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
