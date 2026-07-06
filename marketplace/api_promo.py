"""Otomatik tanitim videosu / animasyonlu kanit karti API katmani
(api.py'ye include edilen router).

POST /me/promo          -> yeni kanit karti kaydi (kredi duser, pro ucretsiz)
GET  /me/promo          -> kullanicinin promo listesi
GET  /me/promo/{token}.svg -> animasyonlu SVG (guncel kapak/skor/rozet ile)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from marketplace import accounts, promo

router = APIRouter()


def _current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = accounts.user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Giris gerekli")
    return user


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


class PromoRequest(BaseModel):
    artist: str
    title: str
    style: str = Field(default="dark")


@router.post("/me/promo")
def create_promo(
    payload: PromoRequest, user: dict = Depends(_current_user)
) -> dict:
    try:
        return promo.create_promo(user, payload.artist, payload.title, payload.style)
    except ValueError as exc:
        raise _400(exc)


@router.get("/me/promo")
def list_promos(user: dict = Depends(_current_user)) -> dict:
    return {"items": promo.list_promos(user["id"])}


@router.get("/me/promo/{token}.svg")
def promo_svg(token: str, user: dict = Depends(_current_user)) -> Response:
    try:
        asset = promo.get_promo(token, user)
    except ValueError as exc:
        raise _400(exc)
    cover = promo.cover_url(asset["artist"], asset["title"])
    score = promo.latest_score(asset["artist"], asset["title"])
    placements = promo.verified_placement_count(user["id"])
    svg = promo.render_svg(asset, cover, score, placements)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'inline; filename="{token}.svg"'},
    )
