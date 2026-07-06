"""Ses parmak izi (fingerprint) yayin dogrulama API'si (api.py'ye include
edilen router).

Kapsam: admin spot parmak izi kaydi, admin manuel/otomatik tarama tetigi
(airplay_stations tablosundaki aktif istasyonlarla — o tabloyu SADECE OKUR),
tespit loglarini gorme, public kanit sayfasi verisi.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from marketplace import airplay, fingerprint

router = APIRouter()


def _require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("MARKETPLACE_ADMIN_KEY")
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Geçersiz admin anahtarı")


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --- Admin: spot kaydi + tarama ----------------------------------------------

class SpotRegister(BaseModel):
    wav_path: str = Field(min_length=1)


@router.post("/admin/fingerprint/spots/{order_id}/register")
def admin_register_spot(
    order_id: int, payload: SpotRegister, _: None = Depends(_require_admin_key),
) -> dict:
    try:
        return fingerprint.register_spot(order_id, payload.wav_path)
    except ValueError as exc:
        raise _400(exc)


@router.post("/admin/fingerprint/scan")
def admin_scan(_: None = Depends(_require_admin_key)) -> dict:
    """airplay_stations tablosundaki aktif istasyonlari tarar (o tabloyu
    sadece okur, degistirmez). Ffmpeg yoksa ilgili istasyon sessizce atlanir."""
    stations = [
        {"id": s["id"], "stream_url": s["meta_url"]}
        for s in airplay.list_stations() if s["active"]
    ]
    return fingerprint.watch_once(stations)


@router.get("/admin/fingerprint/detections")
def admin_detections(
    order_id: int | None = None, _: None = Depends(_require_admin_key),
) -> list[dict]:
    return fingerprint.list_detections(order_id)


# --- Public: kanit sayfasi ----------------------------------------------------

@router.get("/public/campaigns-proof/{order_id}")
def public_campaign_proof(order_id: int) -> list[dict]:
    """O siparisin zaman damgali tespit loglari — kanit sayfasi verisi.
    Auth yok ama sadece tespit listesi donuyor (hassas veri yok)."""
    return fingerprint.list_detections(order_id)
