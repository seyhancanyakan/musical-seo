"""Denetim motoru - kaynaklari toplar, kurallari isletir, skorlar.

normalize(): baslik/sanatci karsilastirmalari icin saf metin normallestirme.
evaluate(): sonuclari kurallara gore degerlendirir, kategori bazinda skorlar
uretir (metadata/presence/consistency/keywords), agirlikli genel skoru hesaplar.
run_audit(): kaynaklardan (spotify/deezer/itunes/youtube) paralel veri toplayip
anahtar kelime gorunurlugunu olcer ve evaluate() ile AuditResult uretir.
"""
from __future__ import annotations

import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from musical_seo import keywords
from musical_seo.models import AuditResult, Finding, KeywordHit, TrackInfo
from musical_seo.sources import deezer, itunes, musicbrainz, spotify, youtube

_PAREN_RE = re.compile(r"\([^)]*\)")
_BRACKET_RE = re.compile(r"\[[^\]]*\]")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_MULTI_SPACE_RE = re.compile(r"\s+")

_TITLE_NOISE_RE = re.compile(
    r"(?i)(official\s*(video|audio)|video\s*klip|lyric\s*video|\bHD\b|\b4K\b)"
)
_FEAT_RE = re.compile(r"(?i)\bfeat\.")
_FT_RE = re.compile(r"(?i)\bft\.")

_CATEGORY_WEIGHTS = {
    "metadata": 30,
    "presence": 25,
    "consistency": 20,
    "keywords": 25,
}
_SEVERITY_PENALTY = {"critical": 40, "warn": 20, "info": 5, "ok": 0}


def normalize(s: str | None) -> str:
    """Casefold + parantez/koseli parantez icini sil + noktalamayi bosluga cevir."""
    if not s:
        return ""
    text = s.casefold()
    text = _PAREN_RE.sub(" ", text)
    text = _BRACKET_RE.sub(" ", text)
    text = _PUNCT_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text).strip()
    return text


def _get_source(sources: list[TrackInfo], name: str) -> TrackInfo | None:
    for src in sources:
        if src.source == name:
            return src
    return None


def _is_mostly_upper(title: str) -> bool:
    letters = [c for c in title if c.isalpha()]
    if not letters:
        return False
    upper_count = sum(1 for c in letters if c.isupper())
    return len(title) > 4 and (upper_count / len(letters)) > 0.8


def _has_emoji(title: str) -> bool:
    return any(ord(c) > 0x1F000 for c in title)


def _feat_styles(titles: list[str]) -> set[str]:
    styles: set[str] = set()
    for t in titles:
        if _FEAT_RE.search(t):
            styles.add("feat.")
        if _FT_RE.search(t):
            styles.add("ft.")
    return styles


def _evaluate_metadata(sources: list[TrackInfo]) -> list[Finding]:
    findings: list[Finding] = []
    found_sources = [s for s in sources if s.found]

    spotify_src = _get_source(sources, "spotify")
    deezer_src = _get_source(sources, "deezer")
    spotify_found = spotify_src is not None and spotify_src.found
    deezer_found = deezer_src is not None and deezer_src.found

    if spotify_found or deezer_found:
        isrc_values = []
        if spotify_found:
            isrc_values.append(spotify_src.isrc)
        if deezer_found:
            isrc_values.append(deezer_src.isrc)
        if not any(isrc_values):
            findings.append(
                Finding(
                    severity="critical",
                    category="metadata",
                    message="ISRC kodu hicbir kaynakta gorunmuyor",
                    action="dagitici panelinden ISRC dogrula",
                )
            )

    if found_sources and not any(s.release_date for s in found_sources):
        findings.append(
            Finding(
                severity="warn",
                category="metadata",
                message="Bulunan kaynaklarin hicbirinde yayin tarihi (release_date) yok",
            )
        )

    found_titles = [s.title for s in found_sources if s.title]
    if found_titles:
        if any(_TITLE_NOISE_RE.search(t) for t in found_titles):
            findings.append(
                Finding(
                    severity="warn",
                    category="metadata",
                    message="Baslikta arama kirliligi yaratan ek ifade var",
                )
            )
        if any(_is_mostly_upper(t) for t in found_titles):
            findings.append(
                Finding(
                    severity="warn",
                    category="metadata",
                    message="Baslik tamamen buyuk harf",
                )
            )
        if any(_has_emoji(t) for t in found_titles):
            findings.append(
                Finding(
                    severity="info",
                    category="metadata",
                    message="Baslikta emoji kullanilmis",
                )
            )
        if len(_feat_styles(found_titles)) > 1:
            findings.append(
                Finding(
                    severity="info",
                    category="metadata",
                    message="'feat.' / 'ft.' yazimi kaynaklar arasinda tutarsiz",
                )
            )

    return findings


def _evaluate_presence(sources: list[TrackInfo]) -> list[Finding]:
    findings: list[Finding] = []

    deezer_src = _get_source(sources, "deezer")
    if deezer_src is not None and not deezer_src.found:
        findings.append(
            Finding(
                severity="critical",
                category="presence",
                message="Deezer'da bulunamadi",
                action="dagiticiya Deezer teslimatini sor",
            )
        )

    itunes_src = _get_source(sources, "itunes")
    if itunes_src is not None and not itunes_src.found:
        findings.append(
            Finding(
                severity="warn",
                category="presence",
                message="Apple Music/iTunes'ta bulunamadi",
            )
        )

    youtube_src = _get_source(sources, "youtube")
    if youtube_src is not None and not youtube_src.found:
        message = "YouTube'da bulunamadi"
        if youtube_src.note:
            message = f"{message} ({youtube_src.note})"
        findings.append(
            Finding(severity="info", category="presence", message=message)
        )

    return findings


def _evaluate_consistency(sources: list[TrackInfo]) -> list[Finding]:
    findings: list[Finding] = []
    found_sources = [s for s in sources if s.found]

    titled = [s for s in found_sources if s.title]
    if len({normalize(s.title) for s in titled}) > 1:
        diffs = "; ".join(f"{s.source}={s.title!r}" for s in titled)
        findings.append(
            Finding(
                severity="warn",
                category="consistency",
                message=f"Baslik yazimi kaynaklar arasinda tutarsiz: {diffs}",
            )
        )

    artisted = [s for s in found_sources if s.artist]
    if len({normalize(s.artist) for s in artisted}) > 1:
        findings.append(
            Finding(
                severity="critical",
                category="consistency",
                message="Sanatci adi kaynaklar arasinda tutarsiz",
            )
        )

    spotify_src = _get_source(sources, "spotify")
    deezer_src = _get_source(sources, "deezer")
    if (
        spotify_src is not None
        and deezer_src is not None
        and spotify_src.found
        and deezer_src.found
        and spotify_src.isrc
        and deezer_src.isrc
        and spotify_src.isrc != deezer_src.isrc
    ):
        findings.append(
            Finding(
                severity="critical",
                category="consistency",
                message="ISRC uyusmazligi",
            )
        )

    # Surum eslesmesi: MusicBrainz'in ilk-yayin tarihi otorite. Bir platformun
    # tarihi MB'den >1 yil sapiyorsa muhtemelen FARKLI SURUM (derleme/yeniden-teslim)
    # eslesmis demektir — hangi kaynagin yanlis surumu getirdigini isaret et.
    mb_src = _get_source(sources, "musicbrainz")
    mb_year = _release_year(mb_src.release_date) if mb_src and mb_src.found else None
    if mb_year is not None:
        drifted = []
        for s in found_sources:
            if s.source == "musicbrainz":
                continue
            yr = _release_year(s.release_date)
            if yr is not None and abs(yr - mb_year) > 1:
                drifted.append(f"{s.source}={yr}")
        if drifted:
            findings.append(
                Finding(
                    severity="warn",
                    category="consistency",
                    message=(
                        f"Surum uyusmazligi: MusicBrainz ilk-yayin {mb_year}, "
                        f"farkli tarih getirenler: {', '.join(drifted)} "
                        "(muhtemelen derleme/yeniden-teslim surumu eslesti)"
                    ),
                    action="Dogru orijinal surumu (MusicBrainz tarihi) referans al",
                )
            )

    return findings


def _release_year(date_str: str | None) -> int | None:
    if not date_str or len(date_str) < 4 or not date_str[:4].isdigit():
        return None
    return int(date_str[:4])


def _canonical_artist_title(sources: list[TrackInfo]) -> tuple[str | None, str | None]:
    for src in sources:
        if src.found and src.artist and src.title:
            return src.artist, src.title
    return None, None


def _evaluate_keywords(
    sources: list[TrackInfo], keyword_hits: list[KeywordHit]
) -> list[Finding]:
    findings: list[Finding] = []
    if not keyword_hits:
        return findings

    google_hits = [k for k in keyword_hits if k.engine == "google"]
    if google_hits and not any(k.artist_present for k in google_hits):
        findings.append(
            Finding(
                severity="info",
                category="keywords",
                message="Sanatci adi Google onerilerinde cikmiyor",
                action="marka aramasini buyut",
            )
        )

    artist, title = _canonical_artist_title(sources)
    if artist and title:
        combined_seed = f"{artist} {title}"
        combined_hit = next(
            (
                k
                for k in keyword_hits
                if k.engine == "google" and k.query == combined_seed
            ),
            None,
        )
        if combined_hit is not None and not combined_hit.track_present:
            findings.append(
                Finding(
                    severity="warn",
                    category="keywords",
                    message="Sarki adi birlesik aramada onerilmiyor",
                )
            )

    for hit in keyword_hits:
        if "sozleri" in hit.query.casefold() and hit.track_present:
            findings.append(
                Finding(
                    severity="ok",
                    category="keywords",
                    message="Sozleri aramasinda gorunuyor",
                )
            )

    seed_engines: dict[str, dict[str, bool]] = defaultdict(dict)
    for hit in keyword_hits:
        seed_engines[hit.query][hit.engine] = hit.artist_present
    both_engine_count = sum(
        1
        for engines in seed_engines.values()
        if engines.get("google") and engines.get("youtube")
    )
    if both_engine_count >= 2:
        findings.append(
            Finding(
                severity="ok",
                category="keywords",
                message="Sanatci adi birden fazla arama motorunda tutarli sekilde on plana cikiyor",
            )
        )

    return findings


def _category_score(findings: list[Finding], category: str) -> int:
    penalty = sum(
        _SEVERITY_PENALTY[f.severity] for f in findings if f.category == category
    )
    return max(0, 100 - penalty)


def evaluate(
    sources: list[TrackInfo], keywords: list[KeywordHit]
) -> tuple[list[Finding], dict[str, int], int]:
    findings: list[Finding] = []
    findings.extend(_evaluate_metadata(sources))
    findings.extend(_evaluate_presence(sources))
    findings.extend(_evaluate_consistency(sources))
    findings.extend(_evaluate_keywords(sources, keywords))

    subscores = {
        category: _category_score(findings, category)
        for category in _CATEGORY_WEIGHTS
    }

    weighted_sum = sum(
        subscores[category] * weight for category, weight in _CATEGORY_WEIGHTS.items()
    )
    score = round(weighted_sum / 100)

    return findings, subscores, score


def run_audit(query: str) -> AuditResult:
    canonical = spotify.resolve(query)
    canonical_source = "spotify"
    if not canonical.found:
        canonical = deezer.search(query)
        canonical_source = "deezer"
    if not canonical.found:
        canonical = itunes.search(query)
        canonical_source = "itunes"
    if not canonical.found:
        raise ValueError(f"Sarki bulunamadi: {query}")

    artist = canonical.artist or ""
    title = canonical.title or ""

    lookup_tasks = {
        "spotify": lambda: canonical
        if canonical_source == "spotify"
        else spotify.lookup(artist, title),
        "deezer": lambda: canonical
        if canonical_source == "deezer"
        else deezer.lookup(artist, title),
        "itunes": lambda: canonical
        if canonical_source == "itunes"
        else itunes.lookup(artist, title),
        "youtube": lambda: youtube.lookup(artist, title),
        "musicbrainz": lambda: musicbrainz.lookup(artist, title),
    }
    order = ("spotify", "deezer", "itunes", "youtube", "musicbrainz")

    with ThreadPoolExecutor(max_workers=len(order)) as executor:
        futures = {name: executor.submit(lookup_tasks[name]) for name in order}
        results = {name: futures[name].result() for name in order}

    sources = [results[name] for name in order]

    keyword_hits = keywords.collect(artist, title)

    findings, subscores, score = evaluate(sources, keyword_hits)

    return AuditResult(
        query=query,
        resolved_artist=artist,
        resolved_title=title,
        created_at=datetime.now(timezone.utc).isoformat(),
        sources=sources,
        keywords=keyword_hits,
        findings=findings,
        subscores=subscores,
        score=score,
    )
