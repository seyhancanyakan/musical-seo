"""Spotify Web API istemcisi (Client Credentials) — marketplace/fraud_forensics.py
icin GERCEK playlist verisi (takipci sayisi + parca listesi) saglar.

musical_seo/sources/spotify.py'dan FARKLI amac: o modul TEK PARCA denetimi
(audit) icin tasarlandi (resolve/lookup + curator pitch yardimcilari). Bu
modul playlist-merkezli fraud pipeline'i icin ozel, kucuk/odakli bir
sozlesme sunar: tek cagrida {name, followers, track_count, tracks} doner.

- get_token(): Client Credentials access token'i modul-seviyesinde cache'ler
  (3600 sn - 60 sn guvenlik payi). Kimlik bilgisi (.env: SPOTIFY_CLIENT_ID /
  SPOTIFY_CLIENT_SECRET) yoksa None doner.
- parse_playlist_id(url): "open.spotify.com/playlist/{id}" (sorgu string'i ve
  "intl-XX/" on eki toleransli) veya "spotify:playlist:{id}" URI'sinden
  playlist ID'sini ayiklar; eslesme yoksa None.
- get_playlist(playlist_id): playlist'i tek istekte ceker (isim, takipci
  toplami, parca toplami, parca listesi id/isim/sanatci). Editoryal
  (37i9dQZF...) listeler 404 doner -> None (kapsam disi; hedef kullanici/
  payola playlist'leri zaten 200 doner). Kota asimi/ag hatasi/bozuk JSON da
  None ile sonuclanir.
- available(): kimlik bilgisi .env'de tanimli mi (agsiz, hizli kontrol).

Guvenlik / dayaniklilik: hicbir fonksiyon exception firlatmaz — cagiran
taraf (marketplace.fraud_forensics) None donusunu "veri yok" olarak ele
alir ve notr fallback'e duser; boylece Spotify kesintisi/kota asimi fraud
analiz uc noktasini asla cokertmez.
"""
from __future__ import annotations

import os
import re
import time
from typing import Any

import requests

from musical_seo import envutil

envutil.load_env()  # SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET .env'den gelsin

_TOKEN_URL = "https://accounts.spotify.com/api/token"
_PLAYLIST_URL = "https://api.spotify.com/v1/playlists/{playlist_id}"
_TIMEOUT = 15
_TOKEN_EXPIRY_SAFETY_SECONDS = 60

# Playlist'i tek istekte cekmek icin alan listesi: isim + takipci toplami +
# parca toplami + (sample icin) parca id/isim/sanatci listesi.
_FIELDS = (
    "name,followers(total),tracks(total),owner(id),"
    "tracks.items(track(id,name,artists(name)))"
)

_PLAYLIST_ID_RE = re.compile(
    r"open\.spotify\.com/(?:intl-[a-z]{2}/)?playlist/([A-Za-z0-9]+)"
)
_PLAYLIST_URI_RE = re.compile(r"spotify:playlist:([A-Za-z0-9]+)")

_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def available() -> bool:
    """Kimlik bilgisi (.env) tanimli mi — agsiz, hizli kontrol."""
    return bool(os.environ.get("SPOTIFY_CLIENT_ID")) and bool(
        os.environ.get("SPOTIFY_CLIENT_SECRET")
    )


def get_token() -> str | None:
    """Client Credentials access token'i doner (cache'li, 3600 sn - 60 sn
    guvenlik payi). Kimlik bilgisi yoksa veya istek basarisiz olursa None
    doner; hicbir zaman exception firlatmaz."""
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    now = time.time()
    cached_token = _token_cache.get("access_token")
    if cached_token and now < _token_cache.get("expires_at", 0.0):
        return cached_token

    try:
        response = requests.post(
            _TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in", 0)
    if not access_token:
        return None

    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = now + expires_in - _TOKEN_EXPIRY_SAFETY_SECONDS
    return access_token


def parse_playlist_id(url: str) -> str | None:
    """"open.spotify.com/playlist/{id}" veya "spotify:playlist:{id}"
    icinden playlist ID'sini ayiklar. Sorgu parametreleri (?si=...) ID
    karakter sinifina girmedigi icin otomatik disarida kalir. Eslesme
    yoksa None."""
    if not url:
        return None
    match = _PLAYLIST_ID_RE.search(url)
    if match:
        return match.group(1)
    match = _PLAYLIST_URI_RE.search(url)
    if match:
        return match.group(1)
    return None


def get_playlist(playlist_id: str) -> dict[str, Any] | None:
    """Playlist'i tek istekte ceker:
    {name, followers, track_count, tracks: [{id, name, artists: [str]}]}.

    Editoryal (37i9...) playlist'ler 404 doner -> None (kapsam disi).
    Kimlik bilgisi yoksa, ag hatasi olursa, kota asilirsa veya JSON
    bozuksa da None doner — hicbir zaman exception firlatmaz."""
    if not playlist_id:
        return None
    token = get_token()
    if not token:
        return None

    try:
        response = requests.get(
            _PLAYLIST_URL.format(playlist_id=playlist_id),
            headers={"Authorization": f"Bearer {token}"},
            params={"fields": _FIELDS},
            timeout=_TIMEOUT,
        )
        if response.status_code != 200:
            return None
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    followers_raw = (data.get("followers") or {}).get("total")
    followers = followers_raw if isinstance(followers_raw, int) else None

    tracks_obj = data.get("tracks") or {}
    track_count_raw = tracks_obj.get("total")
    track_count = track_count_raw if isinstance(track_count_raw, int) else None

    tracks: list[dict[str, Any]] = []
    for item in tracks_obj.get("items") or []:
        track = (item or {}).get("track") or {}
        if not isinstance(track, dict) or not track.get("id"):
            continue
        artists = [
            a.get("name") for a in (track.get("artists") or []) if a.get("name")
        ]
        tracks.append(
            {"id": track["id"], "name": track.get("name"), "artists": artists}
        )

    return {
        "name": data.get("name"),
        "followers": followers,
        "track_count": track_count,
        "tracks": tracks,
    }
