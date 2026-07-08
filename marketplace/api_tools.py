"""Tier-2 ucretsiz araclar API katmani (api.py'ye include edilecek router).

Kapsam: BPM bulucu, sarki tonu (key) tahmincisi, ISRC sorgulayici, Spotify
aylik dinleyici izleyici — programatik SEO'nun "yapiskan, aliskanlik
yaratan" ucretsiz araclari (bkz. docs/PROGRAMATIK_SEO_WORKFLOW.md §3).

Tamamen PUBLIC — auth yok, kredi harcanmaz. Her uc nokta savunmali: kaynak
(Deezer/ses analizi) erisilemez olsa da 200 + found:false doner, asla 500
patlamaz. Sayi UYDURULMAZ — ozellikle /monthly-listeners, Spotify'in genel
API'sinde aylik dinleyici endpoint'i olmadigi icin her zaman found:false +
aciklayici not doner.
"""
from __future__ import annotations

import requests
from fastapi import APIRouter

from musical_seo import audio
from musical_seo.models import TrackInfo
from musical_seo.sources import deezer

router = APIRouter()

_TIMEOUT = 15
_DEEZER_SEARCH_URL = "https://api.deezer.com/search"

# Ton tahmini icin kaba sezgi: 12 ton bes-cember (circle of fifths) sirasinda —
# parlaklik (spectral centroid, 0-1) bu diziyi indexlemek icin kullanilir.
# GERCEK bir ton tespiti DEGILDIR (chroma/pitch-class analizi yok); sadece
# ses profilinden turetilmis eglenceli/kaba bir tahmindir — UI'da acikca
# "heuristic/sezgisel tahmin" olarak etiketlenmelidir.
_KEY_WHEEL = ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]


def _400_placeholder() -> None:  # pragma: no cover - simetri icin, kullanilmiyor
    return None


def _resolve_query(query: str) -> TrackInfo:
    """'Sanatci - Sarki' formatini once dener; yoksa serbest metin arar.
    Deezer erisilemezse veya sonuc yoksa found=False TrackInfo doner —
    hicbir zaman exception firlatmaz (bu ucnokta public + guard'li)."""
    query = (query or "").strip()
    if not query:
        return TrackInfo(source="deezer", found=False, note="Sorgu bos")
    try:
        if " - " in query:
            artist, _, title = query.partition(" - ")
            if artist.strip() and title.strip():
                return deezer.lookup(artist.strip(), title.strip())
        return deezer.search(query)
    except Exception:  # noqa: BLE001 - public arac cokmesin
        return TrackInfo(source="deezer", found=False, note="Deezer istegi basarisiz")


def _deezer_preview_url(query: str) -> str | None:
    """Deezer arama sonucunun 30 sn onizleme URL'i.

    NOT: musical_seo.sources.deezer.TrackInfo bu alani tasimiyor (paylasilan
    modul kasitli olarak degistirilmedi); bu yuzden ayni sorguyu dogrudan
    Deezer'in ham arama uc noktasindan tekrar cekiyoruz (cover_hunter.py'deki
    _track_preview_and_genre ile ayni desen)."""
    try:
        resp = requests.get(
            _DEEZER_SEARCH_URL, params={"q": query, "limit": 1}, timeout=_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    items = (data or {}).get("data") or []
    if not items:
        return None
    return items[0].get("preview") or None


def _audio_profile_for(track: TrackInfo, fallback_query: str) -> audio.AudioProfile | None:
    """Bulunan parca icin ses profili — onizleme yoksa/analiz basarisizsa None."""
    if not track.found or not audio.available():
        return None
    search_terms = f"{track.artist} {track.title}" if track.artist and track.title else fallback_query
    preview = _deezer_preview_url(search_terms)
    if not preview:
        return None
    return audio.analyze_url(preview)


@router.get("/tools/bpm")
def tool_bpm(query: str) -> dict:
    """Sarki BPM bulucu — Deezer onizlemesinden librosa ile tempo cikarir."""
    track = _resolve_query(query)
    profile = _audio_profile_for(track, query)
    return {
        "query": query,
        "found": profile is not None,
        "artist": track.artist if track.found else None,
        "title": track.title if track.found else None,
        "bpm": round(profile.bpm) if profile else None,
        "energy": profile.energy if profile else None,
        "brightness": profile.brightness if profile else None,
    }


def _estimate_key(profile: audio.AudioProfile) -> tuple[str, float]:
    """Parlaklik + enerjiden kaba bir ton/mod tahmini. SEZGISEL — gercek pitch
    class analizi degildir; guven skoru bu yuzden dusuk/orta tutulur."""
    idx = min(int(profile.brightness * len(_KEY_WHEEL)), len(_KEY_WHEEL) - 1)
    root = _KEY_WHEEL[idx]
    mode = "major" if profile.energy >= 0.5 else "minor"
    # Guven: gercek analiz olmadigi icin hicbir zaman yuksek iddia edilmez.
    confidence = round(min(0.3 + 0.25 * profile.energy, 0.55), 2)
    return f"{root} {mode}", confidence


@router.get("/tools/key")
def tool_key(query: str) -> dict:
    """Sarki tonu (key) tahmincisi — DUYURU: gercek bir ton tespiti degil,
    ses profilinden (parlaklik/enerji) turetilmis sezgisel bir tahmindir."""
    track = _resolve_query(query)
    profile = _audio_profile_for(track, query)
    estimated_key, confidence = _estimate_key(profile) if profile else (None, None)
    return {
        "query": query,
        "found": profile is not None,
        "artist": track.artist if track.found else None,
        "title": track.title if track.found else None,
        "estimated_key": estimated_key,
        "confidence": confidence,
        "note": "Sezgisel tahmin (ses parlaklik/enerji profilinden) — gercek "
        "pitch-class/chroma analizi degildir.",
    }


@router.get("/tools/isrc")
def tool_isrc(query: str) -> dict:
    """ISRC sorgulayici — Deezer katalog verisinden dogrudan."""
    track = _resolve_query(query)
    return {
        "query": query,
        "found": bool(track.found and track.isrc),
        "artist": track.artist if track.found else None,
        "title": track.title if track.found else None,
        "isrc": track.isrc if track.found else None,
        "release_date": track.release_date if track.found else None,
    }


@router.get("/tools/monthly-listeners")
def tool_monthly_listeners(query: str) -> dict:
    """Spotify aylik dinleyici sayisi — Spotify'in PUBLIC API'sinde bu metrik
    yok (Spotify for Artists'e ozel, kimlik dogrulamali erisim gerektirir).
    Sayi UYDURULMAZ: her zaman found=false + aciklayici not doner; sadece
    sorgulanan sarkinin cozumlenip cozumlenmedigi bilgi amacli eklenir."""
    track = _resolve_query(query)
    return {
        "query": query,
        "found": False,
        "artist": track.artist if track.found else None,
        "title": track.title if track.found else None,
        "monthly_listeners": None,
        "note": "Spotify aylık dinleyici sayısı public API'de yok "
        "(yalnızca Spotify for Artists — kimlik doğrulamalı erişim ister).",
    }
