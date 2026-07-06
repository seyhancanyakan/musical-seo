"""Radyo airplay takibi API'si (api.py'ye include edilen router).

Kapsam: admin istasyon yonetimi, sanatci abonelik + kredi dusumu, tespit
edilen calinma kayitlari, manuel/otomatik yoklama (poll).
"""
from __future__ import annotations

import os
import threading

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from marketplace import accounts, airplay

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


# --- Admin: istasyon yonetimi -----------------------------------------------

class StationCreate(BaseModel):
    name: str = Field(min_length=1)
    meta_url: str = Field(min_length=1)
    kind: str = "icecast"


@router.post("/admin/airplay/stations")
def admin_add_station(
    payload: StationCreate, _: None = Depends(_require_admin_key)
) -> dict:
    try:
        return airplay.add_station(payload.name, payload.meta_url, payload.kind)
    except ValueError as exc:
        raise _400(exc)


@router.get("/admin/airplay/stations")
def admin_list_stations(_: None = Depends(_require_admin_key)) -> list[dict]:
    return airplay.list_stations()


@router.post("/admin/airplay/poll")
def admin_poll(_: None = Depends(_require_admin_key)) -> dict:
    """Manuel tetik: arka plandaki 10 dakikalik dongu beklenmeden yoklama yapar."""
    return airplay.poll_once()


# --- Sanatci: abonelik + hit'ler --------------------------------------------

class SubscribeRequest(BaseModel):
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)


@router.post("/me/airplay/subscribe")
def me_subscribe(
    payload: SubscribeRequest, user: dict = Depends(_current_user)
) -> dict:
    try:
        return airplay.subscribe(user, payload.artist, payload.title)
    except ValueError as exc:
        raise _400(exc)


@router.get("/me/airplay/subscriptions")
def me_subscriptions(user: dict = Depends(_current_user)) -> list[dict]:
    return airplay.my_subscriptions(user["id"])


@router.get("/me/airplay/hits")
def me_hits(user: dict = Depends(_current_user)) -> list[dict]:
    return airplay.my_hits(user["id"])


# --- Yerlesik yoklama cron'u -------------------------------------------------
# 10 dakikada bir aktif istasyonlari gezer. MUZIKSEO_AIRPLAY_POLL=0 ile
# kapatilabilir (test/CI ortaminda arka plan is parcacigi istenmez).

def _airplay_cron() -> None:
    import time as _time
    while True:
        _time.sleep(10 * 60)
        try:
            airplay.poll_once()
        except Exception:
            pass  # cron dongusu tek hatayla olmesin


if os.environ.get("MUZIKSEO_AIRPLAY_POLL", "1") != "0":
    threading.Thread(target=_airplay_cron, daemon=True).start()
