"""Programatik SEO API katmani (api.py'ye include edilecek router).

Kapsam: PUBLIC uc noktalar SSG/ISR + Google icin sanatci/sarki/playlist
sayfa verisini ve sitemap shard'larini sunar, e-posta kapisi lead yakalar.
ADMIN uc noktalar (X-Admin-Key) kuyruga sanatci ekler ve asamali uretim
batch'ini calistirir.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel

from marketplace import accounts, leads, seo_pages

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


# --- Public: sayfa verisi (SSG/ISR data fetch) --------------------------------

@router.get("/seo/artist/{slug}")
def public_artist_page(slug: str) -> dict:
    page = seo_pages.get_artist_page(slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Sanatçı sayfası bulunamadı")
    return page


@router.get("/seo/song/{isrc}")
def public_song_page(isrc: str) -> dict:
    page = seo_pages.get_song_page(isrc)
    if page is None:
        raise HTTPException(status_code=404, detail="Şarkı sayfası bulunamadı")
    return page


@router.get("/seo/playlist/{pid}")
def public_playlist_page(pid: str) -> dict:
    page = seo_pages.get_playlist_page(pid)
    if page is None:
        raise HTTPException(status_code=404, detail="Playlist sayfası bulunamadı")
    return page


@router.get("/seo/sitemap/{page_type}")
def public_sitemap(page_type: str, offset: int = 0, limit: int = 50000) -> list[dict]:
    try:
        return seo_pages.pages_for_sitemap(page_type, offset, limit)
    except ValueError as exc:
        raise _400(exc)


# --- Public: e-posta kapisi ---------------------------------------------------

class LeadCapture(BaseModel):
    email: str
    source: str
    context: dict | None = None
    website: str = ""  # honeypot: bot doldurursa sessizce yut, kaydetme


@router.post("/leads/capture")
def capture_lead(payload: LeadCapture) -> dict:
    if payload.website.strip():
        # Bot tuzagi: gercek kullanicilar bu alani gormez/doldurmaz.
        return {"ok": True}
    try:
        leads.capture_lead(payload.email, payload.source, payload.context)
        return {"ok": True}
    except ValueError as exc:
        raise _400(exc)


# --- Admin ---------------------------------------------------------------------

class EnqueueArtist(BaseModel):
    artist_name: str
    isni: str | None = None


@router.post("/seo/enqueue-artist")
def admin_enqueue_artist(
    payload: EnqueueArtist, _: None = Depends(_require_admin_key)
) -> dict:
    try:
        return seo_pages.enqueue_artist(payload.artist_name, payload.isni)
    except ValueError as exc:
        raise _400(exc)


@router.post("/seo/build")
def admin_build(limit: int = 100, _: None = Depends(_require_admin_key)) -> dict:
    try:
        return seo_pages.build_next_batch(limit)
    except ValueError as exc:
        raise _400(exc)
