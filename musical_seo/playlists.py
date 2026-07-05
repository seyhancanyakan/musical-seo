"""Playlist eslestirme — Deezer uzerinden benzer-sanatci playlist kesfi (anahtarsiz).

Akis: sanatciyi Deezer'da coz -> benzer sanatcilar (/artist/{id}/related) ->
havuzdaki isimlerle playlist aramasi -> her aday playlist'in parcalarini cek ->
havuzla kesisime gore skorla. Cikti: pitch onceligine gore sirali PlaylistMatch listesi.
Kutuphane modulu: print yok; network hatalari sessizce atlanir (aday dusurulur).
"""
from __future__ import annotations

import time
from typing import Any

import requests

from musical_seo import audio
from musical_seo.models import PlaylistMatch
from musical_seo.sources import lastfm
from musical_seo.sources import spotify as spotify_source

_API = "https://api.deezer.com"
_HEADERS = {"User-Agent": "musical-seo/0.1"}
_SLEEP = 0.15          # Deezer kota nezaketi (50 istek / 5 sn siniri var)
_FAN_CAP = 200_000     # fan katkisi tavani (dev listeler skoru domine etmesin)


def _emit(progress, stage: str, msg: str, **data: Any) -> None:
    """Ilerleme olayi yayinla (SSE/VFX icin). progress None ise sessiz;
    callback hatasi eslestirmeyi asla bozmaz."""
    if progress is None:
        return
    try:
        progress({"stage": stage, "msg": msg, "data": data or None})
    except Exception:
        pass


def _get(path: str, **params: Any) -> dict:
    try:
        resp = requests.get(f"{_API}{path}", params=params, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and not data.get("error"):
            return data
    except Exception:
        pass
    return {}


def _artist_id(artist: str) -> tuple[int | None, str]:
    data = _get("/search/artist", q=artist, limit=1)
    items = data.get("data") or []
    if not items:
        return None, artist
    return items[0].get("id"), items[0].get("name") or artist


def related_artists(artist_id: int, limit: int = 10) -> list[str]:
    data = _get(f"/artist/{artist_id}/related", limit=limit)
    names = [a.get("name", "") for a in (data.get("data") or [])]
    return [n for n in names if n][:limit]


def score_playlist(matched_count: int, fans: int, contains_track: bool) -> float:
    """SAF skor: eslesen benzer-sanatci sayisi agir basar (x10), fan sayisi
    tavanli dogrusal katki (0-10), sarki zaten listedeyse +2 (uyum kaniti)."""
    fan_component = min(max(fans, 0), _FAN_CAP) / (_FAN_CAP / 10)
    return matched_count * 10 + fan_component + (2.0 if contains_track else 0.0)


def _track_preview_and_genre(artist: str, title: str) -> tuple[str | None, str | None]:
    """Sarkinin 30 sn onizleme URL'i + albumden Deezer tur adi (fallback icin)."""
    data = _get("/search/track", q=f"{artist} {title}", limit=1)
    items = data.get("data") or []
    if not items:
        return None, None
    preview = items[0].get("preview") or None
    album_id = (items[0].get("album") or {}).get("id")
    genre = None
    if album_id:
        time.sleep(_SLEEP)
        detail = _get(f"/album/{album_id}")
        genres = (detail.get("genres") or {}).get("data") or []
        genre = genres[0].get("name") if genres else None
    return preview, genre


def _is_editorial(creator: dict) -> bool:
    """Deezer'in kendi editoryal listesi mi? Editoryal listelere pitch
    atilamaz (muhatap curator yok) — eslestirmeden tamamen elenir.
    'editor' kalibi Deezer personel hesaplarini yakalar
    (or. 'Alexandre - Pop & Hits Editor')."""
    name = (creator.get("name") or "").casefold()
    return (not creator.get("id")
            or "deezer" in name
            or "editor" in name)


def _collect_candidates(
    queries: list[str], per_query: int, max_candidates: int, progress=None
) -> dict[int, dict]:
    """Verilen aramalarla aday playlistleri topla (id bazinda tekilsiz)."""
    candidates: dict[int, dict] = {}
    for q in queries:
        _emit(progress, "search", f"Deezer'da aranıyor: “{q}”")
        time.sleep(_SLEEP)
        data = _get("/search/playlist", q=q, limit=per_query)
        for pl in data.get("data") or []:
            pid = pl.get("id")
            nb_tracks = pl.get("nb_tracks") or 0
            if not pid or pid in candidates or not 10 <= nb_tracks <= 1000:
                continue
            candidates[pid] = pl
            if len(candidates) >= max_candidates:
                return candidates
    return candidates


_AUDIO_FIT_MIN = 0.55      # ses uyumu bu esigin altindaysa aday elenir
_AUDIO_FIT_WEIGHT = 20.0   # ses uyumunun skora katkisi (0-20)
_AUDIO_SAMPLE = 3          # playlist basina analiz edilecek onizleme sayisi


def _matches_from_candidates(
    candidates: dict[int, dict],
    pool: list[str],
    canonical: str,
    title: str,
    require_pool_match: bool = True,
    target_profile: "audio.AudioProfile | None" = None,
    progress=None,
) -> list[PlaylistMatch]:
    """Aday playlistleri parca bazinda dogrula ve skorla.

    Deezer editoryal listeleri her modda elenir (pitch muhatabi yok).
    require_pool_match=False: mood/tur fallback modu — havuz kesisimi sart
    kosulmaz; target_profile verilmisse playlist'in ornek parcalari ses
    analiziyle karsilastirilir, uyum dusukse aday elenir, skor uyumdan gelir.
    """
    canonical_cf = canonical.casefold()
    title_cf = title.casefold()

    matches: list[PlaylistMatch] = []
    for pid, pl in candidates.items():
        _emit(progress, "scan", f"İnceleniyor: “{pl.get('title') or pid}” (Deezer)")
        time.sleep(_SLEEP)
        detail = _get(f"/playlist/{pid}")
        creator = detail.get("creator") or pl.get("user") or {}
        if _is_editorial(creator):
            _emit(progress, "skip",
                  f"Elendi (editoryal): “{pl.get('title') or pid}”")
            continue

        tracks = ((detail.get("tracks") or {}).get("data")) or []
        if not tracks:
            extra = _get(f"/playlist/{pid}/tracks", limit=100)
            tracks = extra.get("data") or []
        if not tracks:
            continue

        track_artists_cf = {
            (t.get("artist") or {}).get("name", "").casefold() for t in tracks
        }
        track_artists_cf.discard("")
        matched = sorted({p for p in pool if p.casefold() in track_artists_cf})
        contains = any(
            title_cf == (t.get("title") or "").casefold()
            and canonical_cf == (t.get("artist") or {}).get("name", "").casefold()
            for t in tracks
        )
        if require_pool_match and not matched and not contains:
            continue

        fans = int(detail.get("fans") or 0)
        score = score_playlist(len(matched), fans, contains)

        # Ses uyumu: fallback modunda listenin ornek parcalarini analiz et.
        if target_profile is not None and not require_pool_match:
            _emit(progress, "audio",
                  f"Ses analizi: “{pl.get('title') or pid}” örnek parçaları dinleniyor")
            previews = [t.get("preview") for t in tracks if t.get("preview")]
            pl_profile = audio.profile_from_previews(previews, sample=_AUDIO_SAMPLE)
            if pl_profile is not None:
                fit = audio.similarity(target_profile, pl_profile)
                _emit(progress, "audio_fit",
                      f"Müzikal uyum %{round(fit * 100)}: “{pl.get('title') or pid}”",
                      fit=fit)
                if fit < _AUDIO_FIT_MIN:
                    continue
                score = fit * _AUDIO_FIT_WEIGHT + score

        _emit(progress, "match", f"Eşleşme: “{pl.get('title') or pid}”",
              fans=int(detail.get("fans") or 0))
        matches.append(
            PlaylistMatch(
                source="deezer",
                playlist_id=str(pid),
                title=pl.get("title") or "",
                url=pl.get("link") or f"https://www.deezer.com/playlist/{pid}",
                fans=fans,
                track_count=int(detail.get("nb_tracks") or pl.get("nb_tracks") or 0),
                matched_artists=matched,
                contains_track=contains,
                score=round(score, 1),
                owner_name=creator.get("name"),
                owner_id=str(creator["id"]) if creator.get("id") else None,
            )
        )
    return matches


def _spotify_matches(
    queries: list[str],
    pool: list[str],
    canonical: str,
    title: str,
    per_query: int = 8,
    max_candidates: int = 20,
    require_pool_match: bool = True,
    target_profile: "audio.AudioProfile | None" = None,
    progress=None,
) -> list[PlaylistMatch]:
    """Spotify kullanici listelerinde ayni eslestirme mantigi.

    Spotify anahtari yoksa sessizce [] doner. 'spotify' sahipli (editoryal)
    listeler elenir. Yeni API uygulamalarinda preview_url cogunlukla None —
    o durumda ses uyumu atlanir, isim/mood eslesmesi ile skorlanir.
    """
    canonical_cf = canonical.casefold()
    title_cf = title.casefold()

    seen: set[str] = set()
    matches: list[PlaylistMatch] = []
    for q in queries:
        if len(seen) >= max_candidates:
            break
        _emit(progress, "search", f"Spotify'da aranıyor: “{q}”")
        for pl in spotify_source.search_playlists(q, limit=per_query):
            pid = pl["id"]
            if pid in seen or len(seen) >= max_candidates:
                continue
            seen.add(pid)

            owner_id = (pl.get("owner_id") or "").casefold()
            if not owner_id or owner_id == "spotify":
                continue  # editoryal / sahipsiz: pitch muhatabi yok
            if not 10 <= pl["track_count"] <= 1000:
                continue

            _emit(progress, "scan", f"İnceleniyor: “{pl['name']}” (Spotify)")
            tracks = spotify_source.playlist_tracks(pid)
            if not tracks:
                continue

            track_artists_cf = {
                a.casefold() for t in tracks for a in t["artists"]
            }
            matched = sorted({p for p in pool if p.casefold() in track_artists_cf})
            contains = any(
                title_cf == t["title"].casefold()
                and canonical_cf in {a.casefold() for a in t["artists"]}
                for t in tracks
            )
            if require_pool_match and not matched and not contains:
                continue

            followers = spotify_source.playlist_followers(pid)
            score = score_playlist(len(matched), followers, contains)

            if target_profile is not None and not require_pool_match:
                previews = [t["preview_url"] for t in tracks if t.get("preview_url")]
                pl_profile = audio.profile_from_previews(previews, sample=_AUDIO_SAMPLE)
                if pl_profile is not None:
                    fit = audio.similarity(target_profile, pl_profile)
                    _emit(progress, "audio_fit",
                          f"Müzikal uyum %{round(fit * 100)}: “{pl['name']}”",
                          fit=fit)
                    if fit < _AUDIO_FIT_MIN:
                        continue
                    score = fit * _AUDIO_FIT_WEIGHT + score

            _emit(progress, "match", f"Eşleşme: “{pl['name']}”", fans=followers)
            matches.append(
                PlaylistMatch(
                    source="spotify",
                    playlist_id=pid,
                    title=pl["name"],
                    url=pl["url"],
                    fans=followers,
                    track_count=pl["track_count"],
                    matched_artists=matched,
                    contains_track=contains,
                    score=round(score, 1),
                    owner_name=pl.get("owner_name"),
                    owner_id=pl.get("owner_id"),
                )
            )
    return matches


def find_playlists(
    artist: str,
    title: str,
    limit: int = 15,
    per_query: int = 8,
    max_candidates: int = 20,
    progress=None,
) -> list[PlaylistMatch]:
    """Sanatci+sarki icin pitch onceligine gore sirali playlist adaylari.

    Kademeli strateji:
    1) Deezer benzer-sanatci havuzu (buyuk sanatcilar).
    2) Havuz bos kalirsa Last.fm benzer-sanatci fallback'i.
    3) Isim bazli hic eslesme cikmazsa SES ANALIZI fallback'i: sarkinin 30 sn
       onizlemesinden profil cikar (BPM/enerji/enstrumantallik), profile uyan
       mood terimleriyle playlist ara, adaylarin ornek parcalarini ayni sekilde
       analiz edip muzikal uyuma gore skorla. Tur etiketi (or. yanlis 'Pop')
       sadece yedek arama terimi olarak kullanilir.
    Deezer editoryal listeleri her asamada elenir (pitch muhatabi yok).
    """
    _emit(progress, "resolve", f"Sanatçı çözümleniyor: {artist}")
    artist_id, canonical = _artist_id(artist)
    pool: list[str] = [canonical]
    if artist_id:
        time.sleep(_SLEEP)
        pool.extend(related_artists(artist_id, limit=10))

    # Fallback: Deezer'in related grafigi kucuk sanatcilarda bos donuyor;
    # havuz tek isimde kalirsa benzer sanatcilari Last.fm'den tamamla.
    if len(pool) <= 1:
        _emit(progress, "pool", "Deezer benzer-sanatçı grafiği boş — Last.fm'e soruluyor")
        pool.extend(lastfm.similar_artists(canonical, limit=10))
    _emit(progress, "pool", f"Benzer sanatçı havuzu hazır: {len(pool)} isim",
          names=pool[:5])

    candidates = _collect_candidates(pool[:5], per_query, max_candidates, progress)
    matches = _matches_from_candidates(
        candidates, pool, canonical, title, progress=progress
    )
    matches += _spotify_matches(
        pool[:5], pool, canonical, title, per_query, max_candidates,
        progress=progress,
    )

    if not matches:
        _emit(progress, "audio",
              "İsim eşleşmesi yok — şarkının sesi analiz ediliyor (30 sn önizleme)")
        preview, genre = _track_preview_and_genre(canonical, title)
        target_profile = audio.analyze_url(preview) if preview else None
        if target_profile is not None:
            _emit(progress, "audio_profile",
                  f"Profil: {round(target_profile.bpm)} BPM · "
                  f"enerji %{round(target_profile.energy * 100)} · "
                  f"enstrümantal %{round(target_profile.instrumental_score * 100)}",
                  bpm=round(target_profile.bpm),
                  energy=target_profile.energy,
                  brightness=target_profile.brightness,
                  instrumental=target_profile.instrumental_score)

        queries: list[str] = []
        if target_profile is not None:
            queries.extend(audio.mood_keywords(target_profile))
            _emit(progress, "mood",
                  "Mood terimleri: " + ", ".join(queries), terms=list(queries))
        if genre:
            queries.append(genre)  # yedek terim (etiket yanlis olabilir)

        if queries:
            fb_candidates = _collect_candidates(
                queries[:6], per_query, max_candidates, progress
            )
            matches = _matches_from_candidates(
                fb_candidates, pool, canonical, title,
                require_pool_match=False, target_profile=target_profile,
                progress=progress,
            )
            matches += _spotify_matches(
                queries[:6], pool, canonical, title, per_query, max_candidates,
                require_pool_match=False, target_profile=target_profile,
                progress=progress,
            )

    matches.sort(key=lambda m: m.score, reverse=True)
    _emit(progress, "rank", f"Skorlama bitti: {len(matches)} aday sıralandı")
    return matches[:limit]
