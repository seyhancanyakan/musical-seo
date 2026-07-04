"""Keyword analizi — autocomplete uzerinden gorunurluk olcumu."""
from __future__ import annotations

import time

from musical_seo.models import KeywordHit
from musical_seo.sources import autocomplete

_INTER_REQUEST_DELAY_SECONDS = 0.2


def build_seeds(artist: str, title: str) -> list[str]:
    candidates = [
        artist,
        f"{artist} {title}",
        title,
        f"{title} sozleri",
        f"{artist} {title} lyrics",
        f"{title} sarki",
    ]

    seeds: list[str] = []
    for candidate in candidates:
        seed = (candidate or "").strip()
        if seed and seed not in seeds:
            seeds.append(seed)
    return seeds


def collect(artist: str, title: str) -> list[KeywordHit]:
    artist_cf = (artist or "").casefold()
    title_cf = (title or "").casefold()

    hits: list[KeywordHit] = []
    for seed in build_seeds(artist, title):
        for engine in ("google", "youtube"):
            try:
                suggestions = autocomplete.suggest(seed, engine=engine)
            except Exception:
                suggestions = []

            artist_present = any(artist_cf in s.casefold() for s in suggestions)
            track_present = any(title_cf in s.casefold() for s in suggestions)

            hits.append(
                KeywordHit(
                    query=seed,
                    engine=engine,
                    suggestions=suggestions,
                    artist_present=artist_present,
                    track_present=track_present,
                )
            )
            time.sleep(_INTER_REQUEST_DELAY_SECONDS)

    return hits
