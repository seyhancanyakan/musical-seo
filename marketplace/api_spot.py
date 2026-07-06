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
    # 'voice' (seslendirme) ve 'mix' (birlestirilmis nihai reklam) indirilebilir.
    if asset is None or asset["kind"] not in ("voice", "mix") or not asset["file_path"]:
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


class AutoJingleCreate(BaseModel):
    # Ya dogrudan brief, ya da senaryo alanlari (product/details/tone) verilir;
    # senaryo verildiyse Suno istemi otomatik olusturulur.
    brief: str = ""
    style: str = ""
    product_name: str = ""
    details: str = ""
    tone: str = "enerjik"
    seconds: int = 20
    instrumental: bool = True


@router.post("/public/spot/jingle/auto")
def public_spot_jingle_auto(payload: AutoJingleCreate) -> dict:
    """Suno ile senaryoya uygun jingle uretimini BASLAT. brief bossa
    urun/detay/tondan otomatik (Ingilizce) muzik istemi uretilir."""
    brief = payload.brief.strip()
    if not brief:
        if not payload.product_name.strip():
            raise HTTPException(
                status_code=400, detail="Ürün adı veya brief gerekli"
            )
        brief = spot_ai.suggest_jingle_prompt(
            payload.product_name, payload.details, payload.tone, payload.seconds
        )
    try:
        return spot_ai.auto_jingle(
            brief, payload.style, instrumental=payload.instrumental
        )
    except ValueError as exc:
        raise _400(exc)


@router.get("/public/spot/jingle/{request_id}")
def public_spot_jingle_status(request_id: int) -> dict:
    """Suno jingle durumu (poll). Hazirsa file_url ile mp3 servis edilir."""
    try:
        req = spot_ai.poll_jingle(request_id)
    except ValueError as exc:
        raise _400(exc)
    result = dict(req)
    if req.get("status") == "ready" and req.get("file_path"):
        result["file_url"] = f"/spot-jingle-file/{request_id}"
    return result


@router.get("/spot-jingle-file/{request_id}")
def spot_jingle_file(request_id: int) -> FileResponse:
    reqs = spot_ai.list_jingle_requests()
    match = next((r for r in reqs if r["id"] == request_id), None)
    if match is None or not match.get("file_path"):
        raise HTTPException(status_code=404, detail="Jingle dosyası bulunamadı")
    path = Path(match["file_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Jingle dosyası bulunamadı")
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


class MixCreate(BaseModel):
    voice_asset_id: int
    jingle_request_id: int | None = None
    jingle_file: str | None = None  # kutuphaneden secim (dosya adi)
    campaign_hint: str = ""


@router.post("/public/spot/mix")
def public_spot_mix(payload: MixCreate) -> dict:
    """Voiceover + jingle'i tek reklama birlestir (bed muzik + fade-out).
    jingle_request_id (Suno/hazir talep) VEYA jingle_file (kutuphane) verilir."""
    jingle_path: str | None = None
    if payload.jingle_request_id is not None:
        match = next(
            (r for r in spot_ai.list_jingle_requests()
             if r["id"] == payload.jingle_request_id), None
        )
        if match is None or not match.get("file_path"):
            raise HTTPException(status_code=400, detail="Jingle henüz hazır değil")
        jingle_path = match["file_path"]
    elif payload.jingle_file:
        jingle_path = payload.jingle_file
    else:
        raise HTTPException(
            status_code=400, detail="jingle_request_id veya jingle_file gerekli"
        )
    try:
        asset = spot_ai.mix_ad(
            payload.voice_asset_id, jingle_path, payload.campaign_hint
        )
    except ValueError as exc:
        raise _400(exc)
    return {"file_url": f"/spot-file/{asset['id']}", "asset": asset}


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
