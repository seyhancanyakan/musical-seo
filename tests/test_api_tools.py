"""Tier-2 ucretsiz araclar (BPM/key/ISRC/aylik-dinleyici) uc nokta testleri.

Network YOK: marketplace.api_tools icindeki deezer/audio/requests cagrilari
monkeypatch'lenir. Amac: her uc noktanin (a) bulunca dogru sekli dondurdugunu,
(b) bulunamayinca/ses analizi yoksa cokmeden found=false donduğünü, (c)
monthly-listeners'in HICBIR ZAMAN sayi uydurmadigini dogrulamak.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from marketplace import api_tools
from marketplace.api import app
from musical_seo.audio import AudioProfile
from musical_seo.models import TrackInfo

client = TestClient(app)

_FOUND_TRACK = TrackInfo(
    source="deezer", found=True, artist="Tarkan", title="Simarik",
    isrc="TRA123456789", release_date="1997-01-01", url="https://deezer.com/track/1",
)
_NOT_FOUND_TRACK = TrackInfo(source="deezer", found=False, note="Deezer'da bulunamadi")
_PROFILE = AudioProfile(bpm=120.0, energy=0.6, brightness=0.5, instrumental_score=0.1)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


@pytest.fixture()
def preview_ok(monkeypatch):
    """Deezer ham arama uc noktasinin (onizleme URL'i icin) sahte yaniti."""
    monkeypatch.setattr(
        api_tools.requests, "get",
        lambda *a, **kw: _FakeResponse({"data": [{"preview": "https://dzr.example/p.mp3"}]}),
    )


@pytest.fixture()
def preview_missing(monkeypatch):
    monkeypatch.setattr(
        api_tools.requests, "get", lambda *a, **kw: _FakeResponse({"data": []})
    )


# --- /tools/bpm ---------------------------------------------------------------

def test_bpm_found(monkeypatch, preview_ok):
    monkeypatch.setattr(api_tools.deezer, "lookup", lambda a, t: _FOUND_TRACK)
    monkeypatch.setattr(api_tools.audio, "available", lambda: True)
    monkeypatch.setattr(api_tools.audio, "analyze_url", lambda url: _PROFILE)

    resp = client.get("/tools/bpm", params={"query": "Tarkan - Simarik"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["artist"] == "Tarkan"
    assert body["title"] == "Simarik"
    assert body["bpm"] == 120
    assert body["energy"] == pytest.approx(0.6)
    assert body["brightness"] == pytest.approx(0.5)


def test_bpm_not_found_when_track_missing(monkeypatch):
    monkeypatch.setattr(api_tools.deezer, "search", lambda q: _NOT_FOUND_TRACK)
    monkeypatch.setattr(api_tools.deezer, "lookup", lambda a, t: _NOT_FOUND_TRACK)

    resp = client.get("/tools/bpm", params={"query": "bilinmeyen sarki xyz"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["artist"] is None
    assert body["bpm"] is None


def test_bpm_not_found_when_audio_unavailable(monkeypatch, preview_ok):
    """Ses analizi kutuphanesi yoksa (librosa yuklu degil) found=False —
    500 patlamamali, sadece veri eksik doner."""
    monkeypatch.setattr(api_tools.deezer, "lookup", lambda a, t: _FOUND_TRACK)
    monkeypatch.setattr(api_tools.audio, "available", lambda: False)

    resp = client.get("/tools/bpm", params={"query": "Tarkan - Simarik"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["bpm"] is None


def test_bpm_not_found_when_preview_missing(monkeypatch, preview_missing):
    monkeypatch.setattr(api_tools.deezer, "lookup", lambda a, t: _FOUND_TRACK)
    monkeypatch.setattr(api_tools.audio, "available", lambda: True)

    resp = client.get("/tools/bpm", params={"query": "Tarkan - Simarik"})

    assert resp.status_code == 200
    assert resp.json()["found"] is False


# --- /tools/key -----------------------------------------------------------------

def test_key_heuristic_returns_labelled_estimate(monkeypatch, preview_ok):
    monkeypatch.setattr(api_tools.deezer, "lookup", lambda a, t: _FOUND_TRACK)
    monkeypatch.setattr(api_tools.audio, "available", lambda: True)
    monkeypatch.setattr(api_tools.audio, "analyze_url", lambda url: _PROFILE)

    resp = client.get("/tools/key", params={"query": "Tarkan - Simarik"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["estimated_key"] is not None
    # "<Kok> major|minor" bicimi
    root, mode = body["estimated_key"].split(" ")
    assert root in api_tools._KEY_WHEEL
    assert mode in ("major", "minor")
    assert 0.0 < body["confidence"] <= 0.55
    assert "sezgisel" in body["note"].lower() or "heuristic" in body["note"].lower()


def test_key_not_found_when_track_missing(monkeypatch):
    monkeypatch.setattr(api_tools.deezer, "search", lambda q: _NOT_FOUND_TRACK)
    monkeypatch.setattr(api_tools.deezer, "lookup", lambda a, t: _NOT_FOUND_TRACK)

    resp = client.get("/tools/key", params={"query": "yok boyle bir sarki"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["estimated_key"] is None
    assert body["confidence"] is None


# --- /tools/isrc ------------------------------------------------------------------

def test_isrc_found(monkeypatch):
    monkeypatch.setattr(api_tools.deezer, "lookup", lambda a, t: _FOUND_TRACK)

    resp = client.get("/tools/isrc", params={"query": "Tarkan - Simarik"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["isrc"] == "TRA123456789"
    assert body["release_date"] == "1997-01-01"
    assert body["artist"] == "Tarkan"


def test_isrc_not_found(monkeypatch):
    monkeypatch.setattr(api_tools.deezer, "search", lambda q: _NOT_FOUND_TRACK)

    resp = client.get("/tools/isrc", params={"query": "bilinmeyen"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["isrc"] is None


def test_isrc_track_found_but_no_isrc(monkeypatch):
    """Deezer'da parca var ama isrc alani bos donerse found=False olmali
    (isrc'siz sonuc bu aracin amacina hizmet etmez)."""
    track_no_isrc = TrackInfo(source="deezer", found=True, artist="X", title="Y", isrc=None)
    monkeypatch.setattr(api_tools.deezer, "lookup", lambda a, t: track_no_isrc)

    resp = client.get("/tools/isrc", params={"query": "X - Y"})

    assert resp.status_code == 200
    assert resp.json()["found"] is False


# --- /tools/monthly-listeners ------------------------------------------------------

def test_monthly_listeners_never_fabricates_numbers(monkeypatch):
    """Track bulunsa bile Spotify aylik dinleyici public API'de yok — sayi
    UYDURULMAZ, her zaman found=false + Turkce not doner."""
    monkeypatch.setattr(api_tools.deezer, "lookup", lambda a, t: _FOUND_TRACK)

    resp = client.get("/tools/monthly-listeners", params={"query": "Tarkan - Simarik"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["monthly_listeners"] is None
    assert "spotify" in body["note"].lower()
    # Yine de baglami gostermek icin cozumlenen sanatci/sarki gorunur.
    assert body["artist"] == "Tarkan"


def test_monthly_listeners_handles_unknown_track(monkeypatch):
    monkeypatch.setattr(api_tools.deezer, "search", lambda q: _NOT_FOUND_TRACK)

    resp = client.get("/tools/monthly-listeners", params={"query": "??? xyz"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["artist"] is None
    assert body["monthly_listeners"] is None


# --- genel guard: bilinmeyen/bos sorgu asla 500 vermez -----------------------------

@pytest.mark.parametrize("endpoint", ["/tools/bpm", "/tools/key", "/tools/isrc",
                                       "/tools/monthly-listeners"])
def test_empty_query_handled_gracefully(monkeypatch, endpoint):
    monkeypatch.setattr(api_tools.deezer, "search", lambda q: _NOT_FOUND_TRACK)
    monkeypatch.setattr(api_tools.deezer, "lookup", lambda a, t: _NOT_FOUND_TRACK)

    resp = client.get(endpoint, params={"query": ""})

    assert resp.status_code == 200
    assert resp.json()["found"] is False


@pytest.mark.parametrize("endpoint", ["/tools/bpm", "/tools/key", "/tools/isrc",
                                       "/tools/monthly-listeners"])
def test_missing_query_param_is_422_not_500(endpoint):
    resp = client.get(endpoint)
    assert resp.status_code == 422
