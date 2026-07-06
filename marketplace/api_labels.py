"""Label / A&R B2B erisimi router'i (api.py'ye include edilen).

Kapsam: profesyonel basvuru formu, admin onay/red kuyrugu, onaylanan
sirketlerin sureli token ile eristigi "yukselen sanatcilar" raporu.
Rapor ucu auth istemez — access_token'in kendisi yetki kaniti.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from marketplace import labels

router = APIRouter()


def _require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("MARKETPLACE_ADMIN_KEY")
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Gecersiz admin anahtari")


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


class LabelApply(BaseModel):
    company: str = Field(min_length=1)
    contact_name: str = Field(min_length=1)
    email: str = Field(min_length=6)
    note: str = ""


@router.post("/public/labels/apply")
def public_labels_apply(payload: LabelApply) -> dict:
    try:
        return labels.apply_label(
            payload.company, payload.contact_name, payload.email, payload.note
        )
    except ValueError as exc:
        raise _400(exc)


@router.get("/admin/labels")
def admin_labels_list(
    status: str | None = None, x_admin_key: str | None = Header(default=None)
) -> list[dict]:
    _require_admin_key(x_admin_key)
    return labels.admin_list(status=status)


@router.post("/admin/labels/{lead_id}/approve")
def admin_labels_approve(
    lead_id: int, x_admin_key: str | None = Header(default=None)
) -> dict:
    _require_admin_key(x_admin_key)
    try:
        return labels.approve_label(lead_id)
    except ValueError as exc:
        raise _400(exc)


@router.post("/admin/labels/{lead_id}/reject")
def admin_labels_reject(
    lead_id: int, x_admin_key: str | None = Header(default=None)
) -> dict:
    _require_admin_key(x_admin_key)
    try:
        return labels.reject_label(lead_id)
    except ValueError as exc:
        raise _400(exc)


@router.get("/labels/report")
def labels_report(token: str) -> list[dict]:
    """Auth yok — sureli access_token yeter. Sadece opt-in sanatcilar gorunur."""
    try:
        return labels.rising_report(token)
    except ValueError as exc:
        raise _400(exc)
