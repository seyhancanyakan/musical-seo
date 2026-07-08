"""Curator marketplace API'si.

Calistir: uvicorn marketplace.api:app --reload --port 8100
Is kurali ihlalleri (ValueError) HTTP 400, eksik kayit 404 doner.
"""
from __future__ import annotations

import json
import os
import queue
import threading
from dataclasses import asdict

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from marketplace import accounts, api_features, db, growth, premium, service
from musical_seo import audit as seo_audit
from musical_seo import contacts as seo_contacts
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

# Gelir ozellikleri: paketler, pro, referans, public karne/lig/vitrin,
# sertifika/kart/etki/EPK, panel, otopilot, takvim, payout (api_features.py).
app.include_router(api_features.router)

# Gelir dalga-2: akilli link + affiliate, sync/lisans pazari, label B2B,
# radyo airplay takibi, animasyonlu tanitim karti, geri bildirim sentezi.
from marketplace import (  # noqa: E402  (router kayitlari app tanimindan sonra)
    api_airplay, api_attribution, api_campaigns, api_cover_hunt, api_feedback,
    api_fingerprint, api_fraud, api_labels, api_promo, api_radio_ads,
    api_release_timing, api_seo, api_smartlink, api_spot, api_sync, api_tracks,
)

app.include_router(api_campaigns.router)
app.include_router(api_spot.router)

app.include_router(api_tracks.router)
app.include_router(api_radio_ads.router)

app.include_router(api_smartlink.router)
app.include_router(api_sync.router)
app.include_router(api_labels.router)
app.include_router(api_airplay.router)
app.include_router(api_promo.router)
app.include_router(api_feedback.router)
app.include_router(api_fingerprint.router)

# Nis ozellikler: sahte playlist adli analizi, ROI atif, yayin zamanlamasi,
# cover avcisi (docs/NIS_OZELLIKLER_WORKFLOW.md).
app.include_router(api_fraud.router)
app.include_router(api_attribution.router)
app.include_router(api_release_timing.router)
app.include_router(api_cover_hunt.router)

# Programatik SEO: public sayfa verisi (/seo/*) + e-posta kapisi (/leads/capture)
# (docs/PROGRAMATIK_SEO_WORKFLOW.md).
app.include_router(api_seo.router)


class CuratorApply(BaseModel):
    name: str = Field(min_length=2)
    email: str = Field(min_length=5)
    playlist_url: str = Field(
        default="",
        description="Deezer/Spotify playlist URL veya ID (playlist turu icin zorunlu)",
    )
    curator_type: str = Field(
        default="playlist",
        description="playlist|radyo|medya|label|menajer|booker|dj|mentor|sync",
    )


class SubmissionCreate(BaseModel):
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)
    curator_id: int
    guaranteed: bool = Field(
        default=False, description="Garanti: SLA kacarsa 2x kredi iadesi (ek ucretli)"
    )
    priority: bool = Field(
        default=False, description="One cikan: 48s SLA + inbox'ta ust sira (+1 kredi)"
    )


class SubmissionRespond(BaseModel):
    action: str = Field(description="accepted | rejected")
    feedback: str = ""
    opportunity_level: str | None = Field(
        default=None, description="primary | secondary (bos = kabulde otomatik primary)"
    )
    opportunity_kind: str | None = Field(
        default=None, description="orn. playlist_ekleme, radyo_calma, sosyal_paylasim"
    )


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


def _enrich_contacts(pitches: list[dict], emit=None) -> list[dict]:
    """Her sonuca curator iletisimi ekle (aciklamalardan; bulunamazsa None —
    panel 'platforma davet et' akisini gosterir). Iletisimi bulunamayanlar
    ayrica marketplace.db'ye lead olarak yazilir; hermes_enrich toplu isi
    onlarin halka acik gonderim iletisimini web'den arastirip tamamlar."""
    for p in pitches:
        pl = p["playlist"]
        if emit is not None:
            emit({"stage": "contact",
                  "msg": f"İletişim aranıyor: “{pl['title']}”", "data": None})
        # Pitch->gonder koprusu: aday playlist zaten onayli kuratorse
        # panel dogrudan kredi harcatan "Gonder" butonunu gosterir.
        bridge_pid = (f"sp_{pl['playlist_id']}" if pl["source"] == "spotify"
                      else str(pl["playlist_id"]))
        known = db.get_curator_by_playlist(bridge_pid)
        p["curator_id"] = (
            known["id"] if known and known["status"] == "approved" else None
        )
        p["contact"] = seo_contacts.for_playlist(
            pl["source"], pl["playlist_id"], pl.get("owner_id")
        )
        if p["contact"] is None:
            # sp_ prefix'i hermes kuyrugunda Spotify oncelik kurali icin.
            lead_pid = (f"sp_{pl['playlist_id']}" if pl["source"] == "spotify"
                        else str(pl["playlist_id"]))
            try:
                db.add_curator(
                    name=pl.get("owner_name") or pl["title"],
                    email="",
                    playlist_id=lead_pid,
                    playlist_title=pl["title"],
                    playlist_url=pl["url"],
                    fans=int(pl.get("fans") or 0),
                    track_count=int(pl.get("track_count") or 0),
                    diversity=0.0,
                    quality_score=float(pl.get("score") or 0),
                    status="lead",
                )
            except Exception:
                pass  # lead kaydi kritik degil; pitch akisini bozmasin
    return pitches


@app.post("/pitch/generate")
def pitch_generate(payload: PitchGenerate) -> list[dict]:
    """Her aday playlist icin kisisellestirilmis pitch mesaji + iletisim."""
    artist, title = _resolve(payload.query)
    track = seo_deezer.lookup(artist, title)
    track_url = track.url if track.found else None
    matches = seo_playlists.find_playlists(artist, title, limit=payload.limit)
    return _enrich_contacts([
        {
            "playlist": asdict(m),
            "message": seo_pitch.build_message(artist, title, m, track_url=track_url),
        }
        for m in matches
    ])


@app.get("/pitch/stream")
def pitch_stream(query: str, limit: int = 5) -> StreamingResponse:
    """Pitch uretiminin CANLI akisi (SSE) — panel VFX'i bu olaylari cizer.

    Olay: data: {"stage": "...", "msg": "...", "data": {...}|null}
    Asamalar: resolve, pool, search, scan, skip, audio, audio_profile,
    audio_fit, mood, match, rank, done, error. 'done' olayi /pitch/generate
    ile ayni sekilli sonucu tasir. Eslestirme is parcaciginda kosar; olaylar
    kuyruk uzerinden aninda akar.
    """
    event_queue: queue.Queue = queue.Queue()

    def emit(event: dict) -> None:
        event_queue.put(event)

    def work() -> None:
        try:
            artist, title = _resolve(query)
            emit({"stage": "resolve", "msg": f"Şarkı çözümlendi: {artist} - {title}",
                  "data": {"artist": artist, "title": title}})
            track = seo_deezer.lookup(artist, title)
            track_url = track.url if track.found else None
            matches = seo_playlists.find_playlists(
                artist, title, limit=limit, progress=emit
            )
            pitches = _enrich_contacts(
                [
                    {
                        "playlist": asdict(m),
                        "message": seo_pitch.build_message(
                            artist, title, m, track_url=track_url
                        ),
                    }
                    for m in matches
                ],
                emit=emit,
            )
            emit({"stage": "done", "msg": f"Tamamlandı: {len(pitches)} playlist",
                  "data": {"pitches": pitches}})
        except HTTPException as exc:
            emit({"stage": "error", "msg": str(exc.detail), "data": None})
        except Exception as exc:  # is parcaciginda yutulmasin, kullaniciya aksin
            emit({"stage": "error", "msg": f"Beklenmeyen hata: {exc}", "data": None})
        finally:
            event_queue.put(None)  # akis sonu isareti

    threading.Thread(target=work, daemon=True).start()

    def sse():
        while True:
            event = event_queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- Hesap / kredi / cekirdek dongu ---------------------------------------
# Dongu: kredi al -> kurator sec -> gonder (1 kredi) -> kurator dinler +
# yazili geri bildirim -> nitelikliyse $1 kazanir -> 72 saatte cevap yoksa
# kredi otomatik iade. Playlist'e ekleme HICBIR ZAMAN satilmaz/garanti edilmez.

class AuthRegister(BaseModel):
    email: str = Field(min_length=6)
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)
    role: str = Field(pattern="^(artist|curator)$")
    playlist_url: str | None = None  # kurator: Deezer/Spotify listesi
    curator_type: str = Field(
        default="playlist",
        description="playlist|radyo|medya|label|menajer|booker|dj|mentor|sync",
    )
    referral_code: str | None = None  # davet kodu: ilk gonderimde iki tarafa bonus


class AuthLogin(BaseModel):
    email: str
    password: str


class CreditGrant(BaseModel):
    user_id: int
    amount: int = Field(gt=0)
    reason: str = "purchase"


def _current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = accounts.user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Giris gerekli")
    return user


def _require_role(user: dict, role: str) -> None:
    if user["role"] != role:
        raise HTTPException(status_code=403, detail=f"Bu islem {role} hesabi ister")


@app.post("/auth/register")
def auth_register(payload: AuthRegister) -> dict:
    try:
        curator_id = None
        if payload.role == "curator" and (
            payload.playlist_url or payload.curator_type != "playlist"
        ):
            # Playlist turu link ister; diger profesyoneller linksiz basvurur.
            curator = service.apply_curator(
                payload.name, payload.email, payload.playlist_url or "",
                curator_type=payload.curator_type,
            )
            curator_id = curator["id"]
        user = accounts.register(
            payload.email, payload.password, payload.name, payload.role,
            curator_id=curator_id, referral_code=payload.referral_code,
        )
        token = accounts.login(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"user": user, "token": token}


@app.post("/auth/login")
def auth_login(payload: AuthLogin) -> dict:
    try:
        token = accounts.login(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    user = accounts.user_by_token(token)
    return {"user": user, "token": token}


@app.get("/me")
def me(user: dict = Depends(_current_user)) -> dict:
    result = {"user": user, "transactions": accounts.transactions_for(user["id"])}
    if user["role"] == "curator":
        result["earnings"] = accounts.earnings_for(user["id"])
    return result


@app.post("/admin/credits/grant")
def admin_grant(
    payload: CreditGrant, x_admin_key: str | None = Header(default=None)
) -> dict:
    """Pilot: odeme manuel alinir (iyzico/Papara), kredi buradan yuklenir.
    MARKETPLACE_ADMIN_KEY .env'de tanimli olmali."""
    expected = os.environ.get("MARKETPLACE_ADMIN_KEY")
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Gecersiz admin anahtari")
    try:
        return accounts.grant_credits(payload.user_id, payload.amount, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/me/submissions")
def my_submission_create(
    payload: SubmissionCreate, user: dict = Depends(_current_user)
) -> dict:
    _require_role(user, "artist")
    try:
        return service.create_submission(
            payload.artist, payload.title, payload.curator_id,
            artist_user_id=user["id"],
            guaranteed=payload.guaranteed, priority=payload.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/me/inbox")
def my_inbox(user: dict = Depends(_current_user)) -> list[dict]:
    _require_role(user, "curator")
    service.expire_and_refund()  # inbox her acilista SLA suprüntüsü + iade
    if not user.get("curator_id"):
        return []
    return db.list_submissions(curator_id=user["curator_id"])


@app.post("/me/submissions/{submission_id}/respond")
def my_submission_respond(
    submission_id: int, payload: SubmissionRespond,
    user: dict = Depends(_current_user),
) -> dict:
    _require_role(user, "curator")
    submission = db.get_submission(submission_id)
    if submission is None or submission["curator_id"] != user.get("curator_id"):
        raise HTTPException(status_code=404, detail="Gonderim bulunamadi")
    try:
        return service.respond(
            submission_id, payload.action, payload.feedback,
            opportunity_level=payload.opportunity_level,
            opportunity_kind=payload.opportunity_kind,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/me/earnings")
def my_earnings(user: dict = Depends(_current_user)) -> dict:
    _require_role(user, "curator")
    return accounts.earnings_for(user["id"])


def _require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    """Server-side admin yetkisi: MARKETPLACE_ADMIN_KEY eslesmesi sart."""
    expected = os.environ.get("MARKETPLACE_ADMIN_KEY")
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Gecersiz admin anahtari")


@app.post("/maintenance/expire")
def maintenance_expire(_: None = Depends(_require_admin_key)) -> dict:
    """Cron hedefi: SLA dolan gonderimleri kapat + kredileri iade et."""
    return service.expire_and_refund()


@app.post("/curators/apply")
def curators_apply(payload: CuratorApply) -> dict:
    try:
        return service.apply_curator(
            payload.name, payload.email, payload.playlist_url,
            curator_type=payload.curator_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# Public curator DTO: e-posta / iletisim kaynagi / dogrulama kodu SIZDIRILMAZ.
_PUBLIC_CURATOR_FIELDS = (
    "id", "name", "playlist_title", "playlist_url", "fans",
    "track_count", "quality_score", "status", "ownership_verified",
    "curator_type",
)

_EMPTY_STATS = {
    "total_submissions": 0, "responded": 0, "accepted": 0,
    "response_rate": None, "success_rate": None, "opportunity_rate": None,
}


def _public_curator(curator: dict, stats: dict | None = None) -> dict:
    result = {k: curator.get(k) for k in _PUBLIC_CURATOR_FIELDS}
    result["stats"] = stats or _EMPTY_STATS
    # Reach-bazli fiyat: kademe + taban kredi maliyeti katalogda gorunur.
    result.update(service.curator_pricing(curator, stats))
    result["sponsored"] = growth.is_sponsored(curator)
    return result


@app.get("/curators")
def curators_list(status: str | None = "approved") -> list[dict]:
    all_stats = db.curator_stats()
    items = [
        _public_curator(c, all_stats.get(c["id"]))
        for c in db.list_curators(status=status or None)
    ]
    # Sponsorlu kuratorler katalogda ust sirada (arz tarafi gelir bacagi).
    items.sort(key=lambda c: (not c["sponsored"],))
    return items


@app.get("/curators/{curator_id}")
def curators_get(curator_id: int) -> dict:
    curator = db.get_curator(curator_id)
    if curator is None:
        raise HTTPException(status_code=404, detail="Curator bulunamadi")
    return _public_curator(curator, db.curator_stats(curator_id).get(curator_id))


@app.get("/admin/curators")
def admin_curators_list(
    status: str | None = None, _: None = Depends(_require_admin_key)
) -> list[dict]:
    """Admin: tam kayitlar (e-posta + iletisim kaynagi dahil)."""
    return db.list_curators(status=status or None)


class CuratorStatus(BaseModel):
    status: str = Field(description="approved | rejected | pending")


@app.post("/curators/{curator_id}/status")
def curators_set_status(
    curator_id: int, payload: CuratorStatus, _: None = Depends(_require_admin_key)
) -> dict:
    """Admin: pending basvuruyu elle onayla/reddet."""
    if payload.status not in ("approved", "rejected", "pending"):
        raise HTTPException(status_code=400, detail=f"Gecersiz durum: {payload.status}")
    if not db.update_curator_status(curator_id, payload.status):
        raise HTTPException(status_code=404, detail="Curator bulunamadi")
    curator = db.get_curator(curator_id)
    assert curator is not None
    return curator


# ESKI public /submissions yollari KALDIRILDI: kredi harcamadan gonderim,
# herkese acik listeleme ve sahipsiz yanit guvenlik acigiydi. Gonderim
# /me/submissions (auth), yanit /me/submissions/{id}/respond (auth) uzerinden.

@app.post("/submissions/{submission_id}/verify-placement")
def submissions_verify(
    submission_id: int, _: None = Depends(_require_admin_key)
) -> dict:
    try:
        return service.verify_placement(submission_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --- Oturum / sanatci gecmisi / kurator dogrulama --------------------------

@app.post("/auth/logout")
def auth_logout(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    return {"ok": accounts.logout(token)}


@app.get("/me/submissions")
def my_submissions(user: dict = Depends(_current_user)) -> list[dict]:
    """Sanatci kampanya gecmisi: durum + geri bildirim + SLA."""
    _require_role(user, "artist")
    service.expire_and_refund()  # gecmis her acilista SLA supurmesi + iade
    return db.list_submissions(artist_user_id=user["id"])


class CuratorLink(BaseModel):
    playlist_url: str = Field(min_length=10)


@app.post("/me/curator/link")
def my_curator_link(
    payload: CuratorLink, user: dict = Depends(_current_user)
) -> dict:
    """Kayitta playlist vermeyen kurator hesabina sonradan liste baglar."""
    _require_role(user, "curator")
    try:
        curator = service.apply_curator(user["name"], user["email"], payload.playlist_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    accounts.set_curator_id(user["id"], curator["id"])
    return curator


@app.get("/me/curator")
def my_curator(user: dict = Depends(_current_user)) -> dict:
    _require_role(user, "curator")
    if not user.get("curator_id"):
        raise HTTPException(status_code=404, detail="Bagli playlist yok")
    curator = db.get_curator(user["curator_id"])
    if curator is None:
        raise HTTPException(status_code=404, detail="Curator kaydi bulunamadi")
    curator.pop("email", None)
    return curator


@app.post("/me/curator/verify/start")
def my_curator_verify_start(user: dict = Depends(_current_user)) -> dict:
    """Sahiplik dogrulama kodu uret — kurator playlist ACIKLAMASINA ekler."""
    _require_role(user, "curator")
    if not user.get("curator_id"):
        raise HTTPException(status_code=404, detail="Once playlist bagla")
    try:
        code = service.start_ownership_verification(user["curator_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"code": code,
            "instructions": "Kodu playlist açıklamasına ekle, sonra Doğrula'ya bas. "
                            "Doğrulama sonrası kodu silebilirsin."}


@app.post("/me/curator/verify/check")
def my_curator_verify_check(user: dict = Depends(_current_user)) -> dict:
    _require_role(user, "curator")
    if not user.get("curator_id"):
        raise HTTPException(status_code=404, detail="Once playlist bagla")
    try:
        curator = service.check_ownership(user["curator_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    curator.pop("email", None)
    return curator


# --- Yerlesik SLA cron'u ----------------------------------------------------
# Gercek cron: uygulama ayakta oldugu surece 15 dakikada bir SLA supurmesi +
# otomatik kredi iadesi kosar. Hetzner'da ek olarak crontab onerisi:
#   */15 * * * * curl -s -X POST -H "X-Admin-Key: $KEY" http://127.0.0.1:8100/maintenance/expire

def _sla_cron() -> None:
    import time as _time
    while True:
        _time.sleep(15 * 60)
        try:
            # Tam bakim: SLA iade + yerlesim garantisi + planli gonderimler
            # + Artist Pro aylik kredi tahsisi.
            premium.maintenance_cycle(service)
        except Exception:
            pass  # cron dongusu tek hatayla olmesin


threading.Thread(target=_sla_cron, daemon=True).start()


# --- Yerlesik gunluk SEO build cron'u ----------------------------------------
# Programatik SEO sayfalarini gunde 1 kez, kademeli (SEO_DAILY_BUILD_CAP ile
# sinirli) uretir — kuyruk (build_queue) oncelik sirasina (priority DESC) gore
# islenir, boylece once seed edilen top sanatcilar yayina girer, sonra kuyruga
# eklenen digerleri gunden gune sirayla buyur. audit.run_audit ag erisimi
# gerektirebilir; build_next_batch bunu zaten yakalar (failed olarak
# isaretler), cron bu yuzden cokmez.

def _seo_build_cron() -> None:
    import time as _time
    from marketplace import seo_pages
    while True:
        _time.sleep(24 * 60 * 60)  # gunde 1 kez
        try:
            seo_pages.build_next_batch(limit=seo_pages.SEO_DAILY_BUILD_CAP)
        except Exception:
            pass  # cron tek hatayla olmesin


threading.Thread(target=_seo_build_cron, daemon=True).start()


def _alerts_cron() -> None:
    # Retention: gunluk alert taramasi (cover bulundu / sahte aktivite / ...) —
    # kullaniciyi geri getiren e-posta/bildirim tetikleyicileri (bkz. alerts.py).
    import time as _time
    from marketplace import alerts
    while True:
        _time.sleep(24 * 60 * 60)  # gunde 1 kez
        try:
            alerts.run_daily()
        except Exception:
            pass  # cron tek hatayla olmesin


threading.Thread(target=_alerts_cron, daemon=True).start()
