"""Sync/Lisans mini-marketplace API katmani (api.py'ye include edilen router).

Kapsam: sanatci sync ilani acar/duraklatir, alici public katalogdan lisans
talep eder, sanatci talebe yanit verir (kabulde lisans metni uretilir),
admin odemeleri isaretler.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from marketplace import accounts, syncmarket

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


# --- Sanatci: ilan yonetimi --------------------------------------------------

class ListingCreate(BaseModel):
    artist: str
    title: str
    track_url: str | None = None
    genres: str | None = None
    mood: str | None = None
    description: str | None = None
    price_youtube: int | None = None
    price_reklam: int | None = None
    price_film: int | None = None


@router.post("/me/sync/listings")
def create_listing(
    payload: ListingCreate, user: dict = Depends(_current_user)
) -> dict:
    _require_role(user, "artist")
    try:
        return syncmarket.create_listing(
            user, payload.artist, payload.title, payload.track_url,
            payload.genres, payload.mood, payload.description,
            payload.price_youtube, payload.price_reklam, payload.price_film,
        )
    except ValueError as exc:
        raise _400(exc)


@router.get("/me/sync/listings")
def my_listings(user: dict = Depends(_current_user)) -> list[dict]:
    return syncmarket.list_mine(user["id"])


@router.post("/me/sync/listings/{listing_id}/pause")
def pause_listing(listing_id: int, user: dict = Depends(_current_user)) -> dict:
    try:
        return syncmarket.pause_listing(user, listing_id)
    except ValueError as exc:
        raise _400(exc)


@router.post("/me/sync/listings/{listing_id}/activate")
def activate_listing(listing_id: int, user: dict = Depends(_current_user)) -> dict:
    try:
        return syncmarket.activate_listing(user, listing_id)
    except ValueError as exc:
        raise _400(exc)


# --- Alici: public katalog + talep --------------------------------------------

@router.get("/public/sync")
def public_catalog(
    use_kind: str | None = None, genre: str | None = None
) -> list[dict]:
    try:
        return syncmarket.list_public(use_kind, genre)
    except ValueError as exc:
        raise _400(exc)


class LicenseRequest(BaseModel):
    buyer_name: str
    buyer_email: str
    use_kind: str
    message: str | None = None


@router.post("/public/sync/{listing_id}/request")
def request_license(listing_id: int, payload: LicenseRequest) -> dict:
    try:
        return syncmarket.request_license(
            listing_id, payload.buyer_name, payload.buyer_email,
            payload.use_kind, payload.message,
        )
    except ValueError as exc:
        raise _400(exc)


# --- Sanatci: gelen talepler ---------------------------------------------------

@router.get("/me/sync/requests")
def my_requests(user: dict = Depends(_current_user)) -> list[dict]:
    _require_role(user, "artist")
    return syncmarket.requests_for_owner(user["id"])


class RequestRespond(BaseModel):
    action: str


@router.post("/me/sync/requests/{request_id}/respond")
def respond_request(
    request_id: int, payload: RequestRespond, user: dict = Depends(_current_user)
) -> dict:
    _require_role(user, "artist")
    try:
        return syncmarket.respond_request(user, request_id, payload.action)
    except ValueError as exc:
        raise _400(exc)


# --- Admin ---------------------------------------------------------------------

@router.post("/admin/sync/requests/{request_id}/paid")
def admin_mark_paid(
    request_id: int, _: None = Depends(_require_admin_key)
) -> dict:
    try:
        return syncmarket.mark_paid(request_id)
    except ValueError as exc:
        raise _400(exc)


@router.get("/admin/sync/requests")
def admin_requests(
    status: str | None = None, _: None = Depends(_require_admin_key)
) -> list[dict]:
    return syncmarket.list_admin_requests(status)
