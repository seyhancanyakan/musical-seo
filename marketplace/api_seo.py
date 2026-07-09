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

from marketplace import accounts, alerts, catalog_scout, indexnow, leads, seo_pages

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


@router.post("/seo/seed-starter")
def admin_seed_starter(_: None = Depends(_require_admin_key)) -> dict:
    """Bundled top-sanatci listesini (catalog_scout.STARTER_TOP_ARTISTS) EN
    YUKSEK oncelikle kuyruga ekler — gunluk build cron'u once bunlarla
    baslasin diye. Operator bunu bir kere tetikler."""
    return catalog_scout.seed_starter()


@router.post("/seo/seed-turkish")
def admin_seed_turkish(_: None = Depends(_require_admin_key)) -> dict:
    """Turk sanatci listesini EN YUKSEK oncelikle (2000) kuyruga ekler — cron
    once Turk sanatci sayfalarini uretsin (TR pazar onceligi)."""
    return catalog_scout.seed_turkish()


@router.get("/seo/queue-stats")
def admin_queue_stats(_: None = Depends(_require_admin_key)) -> dict:
    """Kuyrugun durum bazinda ozeti (pending/done/thin/failed) — operator
    seed + gunluk cron ilerlemesini gozlemlesin diye."""
    return seo_pages.queue_stats()


# --- Admin: IndexNow + retention alerts --------------------------------------

@router.get("/seo/indexnow-key")
def admin_indexnow_key(_: None = Depends(_require_admin_key)) -> dict:
    """IndexNow anahtari + keyLocation — operator {key}.txt dosyasini site
    kokune koysun diye. Cron her build sonrasi yeni URL'leri otomatik gonderir."""
    key = indexnow.get_key()
    return {"key": key, "key_location": f"{indexnow.SITE_URL}/{key}.txt"}


@router.post("/seo/reindex")
def admin_reindex(page_type: str = "artist", limit: int = 10000,
                  _: None = Depends(_require_admin_key)) -> dict:
    """Uretilmis sayfalarin URL'lerini IndexNow'a topluca yeniden bildir."""
    try:
        rows = seo_pages.pages_for_sitemap(page_type, 0, limit)
    except ValueError as exc:
        raise _400(exc)
    slugs = [r.get("slug") for r in rows if r.get("slug")]
    prefix = {"artist": "/artist/", "song": "/song/", "playlist": "/playlist/"}.get(
        page_type, "/artist/"
    )
    return indexnow.submit_slugs(slugs, path_prefix=prefix)


@router.post("/alerts/run")
def admin_run_alerts(_: None = Depends(_require_admin_key)) -> dict:
    """Retention alert taramasini elle tetikle (cron zaten gunluk calisir)."""
    return alerts.run_daily()


# --- Admin: song/playlist kuyruk + seed (Tier 4/5 build pipeline) -------------

class EnqueueSong(BaseModel):
    query: str  # "Sanatci - Sarki" veya serbest sorgu


class EnqueuePlaylist(BaseModel):
    playlist_url: str


@router.post("/seo/enqueue-song")
def admin_enqueue_song(
    payload: EnqueueSong, _: None = Depends(_require_admin_key)
) -> dict:
    try:
        return seo_pages.enqueue_song(payload.query)
    except ValueError as exc:
        raise _400(exc)


@router.post("/seo/enqueue-playlist")
def admin_enqueue_playlist(
    payload: EnqueuePlaylist, _: None = Depends(_require_admin_key)
) -> dict:
    try:
        return seo_pages.enqueue_playlist(payload.playlist_url)
    except ValueError as exc:
        raise _400(exc)


@router.post("/seo/seed-songs")
def admin_seed_songs(per_artist: int = 3, _: None = Depends(_require_admin_key)) -> dict:
    """Starter sanatcilarin top parcalarini sarki kuyruguna ekler (Deezer)."""
    return catalog_scout.seed_songs_from_starter(per_artist=per_artist)


@router.post("/seo/seed-playlists")
def admin_seed_playlists(_: None = Depends(_require_admin_key)) -> dict:
    """Spotify aramasindan kullanici playlist'lerini kuyruga ekler (creds gerek)."""
    return catalog_scout.seed_playlists_from_search()
