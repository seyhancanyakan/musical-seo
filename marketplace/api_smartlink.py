"""Akilli link + pre-save + affiliate API katmani (api.py'ye include edilen router).

Kapsam: sanatci akilli link olusturma/listeleme, public link sayfasi
(goruntuleme sayaci), platform tiklama sayaci, hayran e-posta toplama +
export (kredi karsiligi), affiliate ortak vitrini + tiklama yonlendirme.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from marketplace import accounts, affiliate, smartlink

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


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


class LinkCreate(BaseModel):
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)
    links: dict[str, str] = Field(
        description="orn. {'spotify': 'https://...', 'deezer': 'https://...'}"
    )
    release_date: str | None = Field(
        default=None, description="ISO tarih; gelecekteyse presave otomatik acilir"
    )


class ClickRequest(BaseModel):
    platform: str = Field(description="spotify | deezer | youtube | apple | other")


class FanRequest(BaseModel):
    email: str = Field(min_length=4)


# --- Sanatci: akilli link yonetimi -----------------------------------------

@router.post("/me/links")
def me_links_create(
    payload: LinkCreate, user: dict = Depends(_current_user)
) -> dict:
    _require_role(user, "artist")
    try:
        return smartlink.create_link(
            user, payload.artist, payload.title, payload.links,
            release_date=payload.release_date,
        )
    except ValueError as exc:
        raise _400(exc)


@router.get("/me/links")
def me_links_list(user: dict = Depends(_current_user)) -> list[dict]:
    _require_role(user, "artist")
    return smartlink.list_links(user["id"])


@router.get("/me/links/{link_id}/fans")
def me_link_fans(
    link_id: int, user: dict = Depends(_current_user)
) -> list[dict]:
    _require_role(user, "artist")
    try:
        return smartlink.fans_for(user, link_id)
    except ValueError as exc:
        raise _400(exc)


@router.post("/me/links/{link_id}/fans/export")
def me_link_fans_export(
    link_id: int, user: dict = Depends(_current_user)
) -> list[dict]:
    _require_role(user, "artist")
    try:
        return smartlink.export_fans(user, link_id)
    except ValueError as exc:
        raise _400(exc)


# --- Public akilli link sayfasi ---------------------------------------------

@router.get("/public/link/{slug}")
def public_link_get(slug: str) -> dict:
    try:
        return smartlink.get_by_slug(slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/public/link/{slug}/click")
def public_link_click(slug: str, payload: ClickRequest) -> dict:
    try:
        return smartlink.record_click(slug, payload.platform)
    except ValueError as exc:
        raise _400(exc)


@router.post("/public/link/{slug}/fan")
def public_link_fan(slug: str, payload: FanRequest) -> dict:
    try:
        added = smartlink.add_fan(slug, payload.email)
    except ValueError as exc:
        raise _400(exc)
    return {"added": added}


# --- Affiliate ortaklari ------------------------------------------------------

@router.get("/affiliates")
def affiliates_list() -> list[dict]:
    return affiliate.list_partners()


@router.post("/affiliates/{key}/click")
def affiliates_click(key: str) -> dict:
    try:
        url = affiliate.record_click(key)
    except ValueError as exc:
        raise _400(exc)
    return {"url": url}
