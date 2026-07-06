"""Radyo reklam spotu mini-pazari API katmani (api.py'ye include edilecek router).

Kapsam: radyo turu kurator reklam envanteri acar/duraklatir, alici public
katalogdan siparis verir, kurator siparise yanit verir (kabulde sozlesme
metni uretilir), kurator yayin dogrulamasi yapar, admin odemeleri isaretler.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from marketplace import accounts, radio_ads

router = APIRouter()


def _current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = accounts.user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Giriş gerekli")
    return user


def _require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("MARKETPLACE_ADMIN_KEY")
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Geçersiz admin anahtarı")


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --- Kurator: envanter yonetimi ---------------------------------------------

class ListingCreate(BaseModel):
    station_name: str
    slot_seconds: int
    daypart: str
    weekly_spots: int
    price_week_try: int
    description: str | None = None


@router.post("/me/radio-ads/listings")
def create_listing(
    payload: ListingCreate, user: dict = Depends(_current_user)
) -> dict:
    try:
        return radio_ads.create_listing(
            user, payload.station_name, payload.slot_seconds, payload.daypart,
            payload.weekly_spots, payload.price_week_try, payload.description,
        )
    except ValueError as exc:
        raise _400(exc)


@router.get("/me/radio-ads/listings")
def my_listings(user: dict = Depends(_current_user)) -> list[dict]:
    return radio_ads.my_listings(user)


@router.post("/me/radio-ads/listings/{listing_id}/pause")
def pause_listing(listing_id: int, user: dict = Depends(_current_user)) -> dict:
    try:
        return radio_ads.pause_listing(user, listing_id)
    except ValueError as exc:
        raise _400(exc)


@router.post("/me/radio-ads/listings/{listing_id}/activate")
def activate_listing(listing_id: int, user: dict = Depends(_current_user)) -> dict:
    try:
        return radio_ads.activate_listing(user, listing_id)
    except ValueError as exc:
        raise _400(exc)


# --- Alici: public katalog + siparis -----------------------------------------

@router.get("/public/radio-ads")
def public_catalog(
    daypart: str | None = None, max_price: int | None = None
) -> list[dict]:
    try:
        return radio_ads.public_catalog(daypart, max_price)
    except ValueError as exc:
        raise _400(exc)


class OrderCreate(BaseModel):
    buyer_name: str
    buyer_email: str
    buyer_kind: str
    weeks: int
    message: str = ""


@router.post("/public/radio-ads/{listing_id}/order")
def place_order(listing_id: int, payload: OrderCreate) -> dict:
    try:
        return radio_ads.place_order(
            listing_id, payload.buyer_name, payload.buyer_email,
            payload.buyer_kind, payload.weeks, payload.message,
        )
    except ValueError as exc:
        raise _400(exc)


# --- Kurator: gelen siparisler -----------------------------------------------

@router.get("/me/radio-ads/orders")
def my_orders(user: dict = Depends(_current_user)) -> list[dict]:
    return radio_ads.orders_for_owner(user)


class OrderRespond(BaseModel):
    action: str


@router.post("/me/radio-ads/orders/{order_id}/respond")
def respond_order(
    order_id: int, payload: OrderRespond, user: dict = Depends(_current_user)
) -> dict:
    try:
        return radio_ads.respond_order(user, order_id, payload.action)
    except ValueError as exc:
        raise _400(exc)


@router.post("/me/radio-ads/orders/{order_id}/air")
def record_air(order_id: int, user: dict = Depends(_current_user)) -> dict:
    try:
        return radio_ads.record_air(user, order_id)
    except ValueError as exc:
        raise _400(exc)


# --- Admin --------------------------------------------------------------------

@router.get("/admin/radio-ads/orders")
def admin_orders(
    status: str | None = None, _: None = Depends(_require_admin_key)
) -> list[dict]:
    return radio_ads.list_admin_orders(status)


@router.post("/admin/radio-ads/orders/{order_id}/paid")
def admin_mark_paid(
    order_id: int, _: None = Depends(_require_admin_key)
) -> dict:
    try:
        return radio_ads.mark_paid(order_id)
    except ValueError as exc:
        raise _400(exc)
