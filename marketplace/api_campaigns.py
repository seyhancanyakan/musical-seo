"""Radyo kampanya fan-out API katmani (api.py'ye include edilecek router).

Kapsam: alici paket onerisi ister, tek formda birden fazla ilana fan-out
siparis verir (kampanya), kendi e-postasiyla durum/rapor sorgular; admin
kampanyaya bagli tum siparisleri toplu odendi isaretler.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from marketplace import campaigns

router = APIRouter()


def _require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("MARKETPLACE_ADMIN_KEY")
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Geçersiz admin anahtarı")


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --- Paket onerici -------------------------------------------------------------

class SuggestRequest(BaseModel):
    city: str | None = None
    budget_try: int | None = None
    dayparts: list[str] | None = None


@router.post("/public/campaigns/suggest")
def suggest_packages(payload: SuggestRequest) -> list[dict]:
    try:
        return campaigns.suggest_packages(
            payload.city, payload.budget_try, payload.dayparts,
        )
    except ValueError as exc:
        raise _400(exc)


# --- Kampanya olusturma (fan-out) ---------------------------------------------

class CampaignCreate(BaseModel):
    buyer_name: str
    buyer_email: str
    buyer_kind: str
    product_name: str
    spot_text: str
    cities: list[str] = []
    dayparts: list[str] = []
    weeks: int
    budget_try: int
    audio_url: str | None = None
    jingle_url: str | None = None


@router.post("/public/campaigns")
def create_campaign(payload: CampaignCreate) -> dict:
    try:
        return campaigns.create_campaign(
            payload.buyer_name, payload.buyer_email, payload.buyer_kind,
            payload.product_name, payload.spot_text, payload.cities,
            payload.dayparts, payload.weeks, payload.budget_try,
            payload.audio_url, payload.jingle_url,
        )
    except ValueError as exc:
        raise _400(exc)


# --- Alici: durum + rapor -------------------------------------------------------

@router.get("/public/campaigns/{campaign_id}")
def campaign_status(campaign_id: int, email: str) -> dict:
    try:
        campaign = campaigns.get_campaign(campaign_id, email)
        breakdown = campaigns.campaign_status(campaign_id)
    except ValueError as exc:
        raise _400(exc)
    return {"campaign": campaign, "orders": breakdown}


@router.get("/public/campaigns/{campaign_id}/report")
def campaign_report(campaign_id: int, email: str) -> dict:
    try:
        campaigns.get_campaign(campaign_id, email)  # e-posta eslesme gate'i
        return campaigns.campaign_report(campaign_id)
    except ValueError as exc:
        raise _400(exc)


# --- Admin ----------------------------------------------------------------------

@router.get("/admin/campaigns")
def admin_campaigns(
    status: str | None = None, _: None = Depends(_require_admin_key)
) -> list[dict]:
    return campaigns.list_admin_campaigns(status)


@router.post("/admin/campaigns/{campaign_id}/paid")
def admin_mark_paid(
    campaign_id: int, _: None = Depends(_require_admin_key)
) -> dict:
    try:
        return campaigns.mark_campaign_paid(campaign_id)
    except ValueError as exc:
        raise _400(exc)
