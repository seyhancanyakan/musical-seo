"""musical_seo.audit.normalize / evaluate icin testler (network YOK).

Sahte TrackInfo/KeywordHit listeleriyle audit.evaluate'in SAF davranisini
dogrular. Donen yapi: (findings: list[Finding], subscores: dict[str, int],
score: int).
"""
from __future__ import annotations

from musical_seo.audit import evaluate, normalize
from musical_seo.models import KeywordHit, TrackInfo


def test_normalize_strips_parenthetical_suffix_and_casefolds():
    # Arrange
    title = "Kuzu Kuzu (Official Video)"

    # Act
    result = normalize(title)

    # Assert
    assert result == "kuzu kuzu"


def test_evaluate_flags_critical_when_isrc_missing_from_spotify_and_deezer():
    # Arrange
    sources = [
        TrackInfo(
            source="spotify",
            found=True,
            title="Kuzu Kuzu",
            artist="Tarkan",
            release_date="2016-03-01",
        ),
        TrackInfo(
            source="deezer",
            found=True,
            title="Kuzu Kuzu",
            artist="Tarkan",
            release_date="2016-03-01",
        ),
        TrackInfo(source="itunes", found=False),
        TrackInfo(source="youtube", found=False, note="API anahtari yok"),
    ]

    # Act
    findings, subscores, score = evaluate(sources, [])

    # Assert
    critical_metadata = [
        f for f in findings if f.severity == "critical" and f.category == "metadata"
    ]
    assert len(critical_metadata) >= 1
    assert subscores["metadata"] <= 60
    assert isinstance(score, int)


def test_evaluate_flags_critical_presence_when_deezer_not_found():
    # Arrange
    sources = [
        TrackInfo(
            source="spotify",
            found=True,
            title="Kuzu Kuzu",
            artist="Tarkan",
            isrc="TRA391600001",
            release_date="2016-03-01",
        ),
        TrackInfo(source="deezer", found=False),
        TrackInfo(
            source="itunes",
            found=True,
            title="Kuzu Kuzu",
            artist="Tarkan",
        ),
        TrackInfo(
            source="youtube",
            found=True,
            title="Kuzu Kuzu",
            artist="Tarkan",
        ),
    ]

    # Act
    findings, subscores, score = evaluate(sources, [])

    # Assert
    critical_presence = [
        f for f in findings if f.severity == "critical" and f.category == "presence"
    ]
    assert len(critical_presence) >= 1
    assert subscores["presence"] <= 60
    assert score < 100


def test_evaluate_scores_high_when_all_sources_consistent_and_keywords_good():
    # Arrange
    sources = [
        TrackInfo(
            source="spotify",
            found=True,
            title="Kuzu Kuzu",
            artist="Tarkan",
            album="Dudu",
            isrc="TRA391600001",
            release_date="2016-03-01",
            duration_ms=200000,
            popularity=70,
            url="https://open.spotify.com/track/x",
        ),
        TrackInfo(
            source="deezer",
            found=True,
            title="Kuzu Kuzu",
            artist="Tarkan",
            isrc="TRA391600001",
            release_date="2016-03-01",
            popularity=80,
            url="https://www.deezer.com/track/x",
        ),
        TrackInfo(
            source="itunes",
            found=True,
            title="Kuzu Kuzu",
            artist="Tarkan",
            release_date="2016-03-01",
            url="https://music.apple.com/x",
        ),
        TrackInfo(
            source="youtube",
            found=True,
            title="Kuzu Kuzu",
            artist="Tarkan",
            url="https://youtube.com/watch?v=x",
            extra={"views": 1_000_000},
        ),
    ]

    artist, title = "Tarkan", "Kuzu Kuzu"
    keywords = [
        KeywordHit(
            query=artist,
            engine="google",
            suggestions=[f"{artist} sarkilari"],
            artist_present=True,
            track_present=False,
        ),
        KeywordHit(
            query=artist,
            engine="youtube",
            suggestions=[f"{artist} konser"],
            artist_present=True,
            track_present=False,
        ),
        KeywordHit(
            query=f"{artist} {title}",
            engine="google",
            suggestions=[f"{artist} {title} sozleri"],
            artist_present=True,
            track_present=True,
        ),
        KeywordHit(
            query=f"{artist} {title}",
            engine="youtube",
            suggestions=[f"{artist} {title} klip"],
            artist_present=True,
            track_present=True,
        ),
        KeywordHit(
            query=title,
            engine="google",
            suggestions=[f"{title} sozleri"],
            artist_present=False,
            track_present=True,
        ),
        KeywordHit(
            query=title,
            engine="youtube",
            suggestions=[f"{title} klip"],
            artist_present=False,
            track_present=True,
        ),
        KeywordHit(
            query=f"{title} sozleri",
            engine="google",
            suggestions=[f"{title} sozleri anlami"],
            artist_present=False,
            track_present=True,
        ),
        KeywordHit(
            query=f"{title} sozleri",
            engine="youtube",
            suggestions=[f"{title} sozleri video"],
            artist_present=False,
            track_present=True,
        ),
        KeywordHit(
            query=f"{artist} {title} lyrics",
            engine="google",
            suggestions=[f"{artist} {title} lyrics english"],
            artist_present=True,
            track_present=True,
        ),
        KeywordHit(
            query=f"{artist} {title} lyrics",
            engine="youtube",
            suggestions=[f"{artist} {title} lyrics video"],
            artist_present=True,
            track_present=True,
        ),
        KeywordHit(
            query=f"{title} sarki",
            engine="google",
            suggestions=[f"{title} sarki sozu"],
            artist_present=False,
            track_present=True,
        ),
        KeywordHit(
            query=f"{title} sarki",
            engine="youtube",
            suggestions=[f"{title} sarki video"],
            artist_present=False,
            track_present=True,
        ),
    ]

    # Act
    findings, subscores, score = evaluate(sources, keywords)

    # Assert
    critical_findings = [f for f in findings if f.severity == "critical"]
    assert critical_findings == []
    assert score >= 80
