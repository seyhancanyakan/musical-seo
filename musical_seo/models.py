"""Veri modelleri — tum moduller bu sozlesmeye uyar. DEGISTIRME, sadece kullan."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TrackInfo:
    """Tek kaynaktan normalize edilmis sarki bilgisi."""

    source: str                      # "spotify" | "deezer" | "itunes" | "youtube"
    found: bool
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    isrc: str | None = None
    release_date: str | None = None  # "YYYY-MM-DD" veya "YYYY"
    duration_ms: int | None = None
    popularity: int | None = None    # kaynak olceginde ham deger (Spotify 0-100, Deezer rank)
    url: str | None = None
    note: str | None = None          # ör. "API anahtari yok"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class KeywordHit:
    """Bir autocomplete sorgusunun sonucu."""

    query: str
    engine: str                      # "google" | "youtube"
    suggestions: list[str] = field(default_factory=list)
    artist_present: bool = False     # sanatci adi onerilerin herhangi birinde geciyor mu
    track_present: bool = False      # sarki adi onerilerin herhangi birinde geciyor mu


@dataclass
class Finding:
    """Denetim bulgusu. message ve action Turkce."""

    severity: str                    # "critical" | "warn" | "info" | "ok"
    category: str                    # "metadata" | "presence" | "consistency" | "keywords"
    message: str
    action: str | None = None


@dataclass
class PlaylistMatch:
    """Benzer-sanatci analiziyle bulunan aday playlist."""

    source: str                      # "deezer"
    playlist_id: str
    title: str
    url: str
    fans: int = 0
    track_count: int = 0
    matched_artists: list[str] = field(default_factory=list)  # havuzdan eslesenler
    contains_track: bool = False     # denetlenen sarki zaten listede mi
    score: float = 0.0
    owner_name: str | None = None    # playlist sahibi (curator kesfi icin)
    owner_id: str | None = None


@dataclass
class AuditResult:
    """Tam denetim ciktisi."""

    query: str
    resolved_artist: str
    resolved_title: str
    created_at: str                  # ISO datetime (UTC)
    sources: list[TrackInfo] = field(default_factory=list)
    keywords: list[KeywordHit] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    subscores: dict[str, int] = field(default_factory=dict)  # kategori -> 0-100
    score: int = 0                   # genel 0-100

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
