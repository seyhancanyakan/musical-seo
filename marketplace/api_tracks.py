"""Sarkilarim API'si — sanatci sarki kutuphanesi (tracks.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from marketplace import accounts, tracks

router = APIRouter()


def _current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = accounts.user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Giris gerekli")
    return user


def _require_artist(user: dict) -> None:
    if user["role"] != "artist":
        raise HTTPException(status_code=403, detail="Bu islem artist hesabi ister")


class TrackAdd(BaseModel):
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)


@router.post("/me/tracks")
def track_add(payload: TrackAdd, user: dict = Depends(_current_user)) -> dict:
    _require_artist(user)
    try:
        return tracks.add_track(user["id"], payload.artist, payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/me/tracks")
def track_list(user: dict = Depends(_current_user)) -> list[dict]:
    _require_artist(user)
    return tracks.list_tracks(user["id"])


@router.delete("/me/tracks/{track_id}")
def track_delete(track_id: int, user: dict = Depends(_current_user)) -> dict:
    _require_artist(user)
    if not tracks.delete_track(user["id"], track_id):
        raise HTTPException(status_code=404, detail="Sarki bulunamadi")
    return {"ok": True}
