"""Geri bildirim sentez raporu API katmani (api.py'ye include edilen router)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from marketplace import accounts, feedback_digest

router = APIRouter()


def _current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = accounts.user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Giris gerekli")
    return user


@router.post("/me/feedback-digest")
def create_feedback_digest(user: dict = Depends(_current_user)) -> dict:
    """Sanatcinin dolu geri bildirimlerinden yeni bir sentez raporu uretir."""
    try:
        return feedback_digest.synthesize(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/me/feedback-digest")
def get_feedback_digest(user: dict = Depends(_current_user)) -> dict:
    """Sanatcinin en son uretilmis sentez raporu; hic yoksa 404."""
    digest = feedback_digest.latest(user["id"])
    if digest is None:
        raise HTTPException(status_code=404, detail="Henuz sentez raporu yok")
    return digest
