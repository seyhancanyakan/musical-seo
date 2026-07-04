"""Curator marketplace API'si.

Calistir: uvicorn marketplace.api:app --reload --port 8100
Is kurali ihlalleri (ValueError) HTTP 400, eksik kayit 404 doner.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from marketplace import db, service
from musical_seo import audit as seo_audit
from musical_seo import db as seo_db
from musical_seo import pitch as seo_pitch
from musical_seo import playlists as seo_playlists
from musical_seo.sources import deezer as seo_deezer

app = FastAPI(
    title="musical-seo curator marketplace",
    description="Kendi curator agi: basvuru, dogrulama, gonderim, SLA, yerlesim kaniti",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3100", "http://127.0.0.1:3100"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CuratorApply(BaseModel):
    name: str = Field(min_length=2)
    email: str = Field(min_length=5)
    playlist_url: str = Field(min_length=1, description="Deezer playlist URL veya ID")


class SubmissionCreate(BaseModel):
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)
    curator_id: int


class SubmissionRespond(BaseModel):
    action: str = Field(description="accepted | rejected")
    feedback: str = ""


@app.get("/health")
def health() -> dict:
    return {"ok": True}


def _resolve(query: str) -> tuple[str, str]:
    if " - " in query:
        artist, _, title = query.partition(" - ")
        if artist.strip() and title.strip():
            return artist.strip(), title.strip()
    info = seo_deezer.search(query)
    if not info.found or not info.artist or not info.title:
        raise HTTPException(status_code=404, detail=f"Sarki bulunamadi: {query}")
    return info.artist, info.title


@app.get("/audit")
def audit_run(query: str, save: bool = True) -> dict:
    """SEO karnesi: tam denetim sonucu (frontend dashboard'u besler)."""
    try:
        result = seo_audit.run_audit(query)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if save:
        seo_db.save(result)
    return result.to_dict()


@app.get("/audit/history")
def audit_history(query: str) -> list[dict]:
    """Zaman serisi (kanit sayfasi)."""
    artist, title = _resolve(query)
    return seo_db.history(artist, title)


@app.get("/playlists")
def playlists_find(query: str, limit: int = 10) -> list[dict]:
    """Benzer-sanatci playlist eslestirme (pitch aday listesi)."""
    artist, title = _resolve(query)
    return [asdict(m) for m in seo_playlists.find_playlists(artist, title, limit=limit)]


class PitchGenerate(BaseModel):
    query: str = Field(min_length=3, description="'Sanatci - Sarki'")
    limit: int = 5


@app.post("/pitch/generate")
def pitch_generate(payload: PitchGenerate) -> list[dict]:
    """Her aday playlist icin kisisellestirilmis pitch mesaji."""
    artist, title = _resolve(payload.query)
    track = seo_deezer.lookup(artist, title)
    track_url = track.url if track.found else None
    matches = seo_playlists.find_playlists(artist, title, limit=payload.limit)
    return [
        {
            "playlist": asdict(m),
            "message": seo_pitch.build_message(artist, title, m, track_url=track_url),
        }
        for m in matches
    ]


@app.post("/curators/apply")
def curators_apply(payload: CuratorApply) -> dict:
    try:
        return service.apply_curator(payload.name, payload.email, payload.playlist_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/curators")
def curators_list(status: str | None = "approved") -> list[dict]:
    return db.list_curators(status=status or None)


@app.get("/curators/{curator_id}")
def curators_get(curator_id: int) -> dict:
    curator = db.get_curator(curator_id)
    if curator is None:
        raise HTTPException(status_code=404, detail="Curator bulunamadi")
    return curator


class CuratorStatus(BaseModel):
    status: str = Field(description="approved | rejected | pending")


@app.post("/curators/{curator_id}/status")
def curators_set_status(curator_id: int, payload: CuratorStatus) -> dict:
    """Admin: pending basvuruyu elle onayla/reddet."""
    if payload.status not in ("approved", "rejected", "pending"):
        raise HTTPException(status_code=400, detail=f"Gecersiz durum: {payload.status}")
    if not db.update_curator_status(curator_id, payload.status):
        raise HTTPException(status_code=404, detail="Curator bulunamadi")
    curator = db.get_curator(curator_id)
    assert curator is not None
    return curator


@app.post("/submissions")
def submissions_create(payload: SubmissionCreate) -> dict:
    try:
        return service.create_submission(payload.artist, payload.title, payload.curator_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/submissions")
def submissions_list(curator_id: int | None = None, status: str | None = None) -> list[dict]:
    db.expire_overdue()  # her listelemede SLA supurmesi
    return db.list_submissions(curator_id=curator_id, status=status)


@app.get("/submissions/{submission_id}")
def submissions_get(submission_id: int) -> dict:
    submission = db.get_submission(submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Gonderim bulunamadi")
    return submission


@app.post("/submissions/{submission_id}/respond")
def submissions_respond(submission_id: int, payload: SubmissionRespond) -> dict:
    try:
        return service.respond(submission_id, payload.action, payload.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/submissions/{submission_id}/verify-placement")
def submissions_verify(submission_id: int) -> dict:
    try:
        return service.verify_placement(submission_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
