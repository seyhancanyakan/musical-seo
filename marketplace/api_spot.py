"""AI reklam spotu uretimi API katmani (api.py'ye include edilecek router).

Kapsam: Claude ile spot metni (anahtar yoksa sablon fallback), ElevenLabs ile
seslendirme (anahtar zorunlu), Suno jingle kuyrugu (resmi API yok -> operator
elle uretir, admin data/jingles/ altina koydugu dosyayi baglar).
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from marketplace import spot_ai

router = APIRouter()


def _require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("MARKETPLACE_ADMIN_KEY")
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Geçersiz admin anahtarı")


def _400(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --- Script uretimi ----------------------------------------------------------

class ScriptCreate(BaseModel):
    product_name: str
    details: str = ""
    seconds: int = 20
    tone: str = "enerjik"


@router.post("/public/spot/script")
def public_spot_script(payload: ScriptCreate) -> dict:
    try:
        return spot_ai.generate_script(
            payload.product_name, payload.details, payload.seconds, payload.tone
        )
    except ValueError as exc:
        raise _400(exc)


# --- Seslendirme ---------------------------------------------------------------

@router.get("/public/spot/voices")
def public_spot_voices() -> list[dict]:
    return spot_ai.list_voices()


class VoiceCreate(BaseModel):
    text: str
    voice_id: str = "default"


@router.post("/public/spot/voice")
def public_spot_voice(payload: VoiceCreate) -> dict:
    try:
        asset = spot_ai.synthesize_voice(payload.text, payload.voice_id)
    except ValueError as exc:
        raise _400(exc)
    return {"file_url": f"/spot-file/{asset['id']}", "asset": asset}


@router.get("/spot-file/{asset_id}")
def spot_file(asset_id: int) -> FileResponse:
    asset = spot_ai.get_asset(asset_id)
    if asset is None or asset["kind"] != "voice" or not asset["file_path"]:
        raise HTTPException(status_code=404, detail="Ses dosyası bulunamadı")
    path = Path(asset["file_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Ses dosyası bulunamadı")
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


# --- Jingle kuyrugu ------------------------------------------------------------

class JingleRequestCreate(BaseModel):
    brief: str
    style: str = ""


@router.post("/public/spot/jingle")
def public_spot_jingle(payload: JingleRequestCreate) -> dict:
    try:
        return spot_ai.request_jingle(payload.brief, payload.style)
    except ValueError as exc:
        raise _400(exc)


@router.get("/public/spot/jingles")
def public_spot_jingles() -> dict:
    """Hazir jingle kutuphanesi + hazir (fulfilled) talepler."""
    return {
        "library": spot_ai.jingle_library(),
        "ready_requests": spot_ai.list_jingle_requests(status="ready"),
    }


@router.get("/admin/spot/jingle-requests")
def admin_spot_jingle_requests(
    status: str | None = None, _: None = Depends(_require_admin_key)
) -> list[dict]:
    return spot_ai.list_jingle_requests(status)


class JingleFulfill(BaseModel):
    file_path: str


@router.post("/admin/spot/jingle-requests/{request_id}/fulfill")
def admin_spot_jingle_fulfill(
    request_id: int, payload: JingleFulfill, _: None = Depends(_require_admin_key)
) -> dict:
    try:
        return spot_ai.fulfill_jingle(request_id, payload.file_path)
    except ValueError as exc:
        raise _400(exc)
