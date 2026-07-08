"""Optimum Yayin Tarihi Optimizatoru testleri: 4 sinyal (hazirlik/anahtar
kelime rekabeti/rakip yayinlar/gun optimizasyonu), birlesik tavsiye, tarih
matematigi, hatali tarih formati. Network YOK - hepsi monkeypatch/notr yol.
"""
from __future__ import annotations

import pytest

from marketplace import db
from musical_seo import release_timing
from musical_seo.models import AuditResult, Finding


@pytest.fixture()
def timing_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


# --- Sinyal 1: hazirlik -------------------------------------------------------

def test_signal_readiness_uses_audit_score(monkeypatch):
    result = AuditResult(
        query="Sanatci - Sarki",
        resolved_artist="Sanatci",
        resolved_title="Sarki",
        created_at="2026-01-01T00:00:00+00:00",
        score=85,
        findings=[
            Finding(severity="warn", category="metadata", message="ISRC eksik",
                    action="dogrula"),
        ],
    )
    monkeypatch.setattr(release_timing.audit, "run_audit", lambda q: result)
    signal = release_timing.signal_readiness("Sanatci - Sarki")
    assert signal["score"] == 85
    assert signal["fixable_issues"] == ["ISRC eksik"]


def test_signal_readiness_falls_back_to_neutral_on_failure(monkeypatch):
    def _raise(_query):
        raise ValueError("Sarki bulunamadi")

    monkeypatch.setattr(release_timing.audit, "run_audit", _raise)
    signal = release_timing.signal_readiness("bilinmeyen sarki")
    assert signal == {"score": 50, "findings": [], "fixable_issues": []}


# --- Sinyal 2: anahtar kelime rekabeti ----------------------------------------

def test_signal_keyword_competition_low_when_suggestions_match_own_terms(monkeypatch):
    monkeypatch.setattr(
        release_timing.autocomplete, "suggest",
        lambda q, engine="google": ["sanatci sarki sozleri", "sanatci sarki lyrics"],
    )
    signal = release_timing.signal_keyword_competition("sanatci sarki")
    assert signal["competition"] == "low"


def test_signal_keyword_competition_high_when_suggestions_are_unrelated(monkeypatch):
    monkeypatch.setattr(
        release_timing.autocomplete, "suggest",
        lambda q, engine="google": [
            "baska sanatci baska sarki", "farkli grup farkli parca",
            "alakasiz oneri bir", "alakasiz oneri iki",
        ],
    )
    signal = release_timing.signal_keyword_competition("sanatci sarki")
    assert signal["competition"] == "high"


def test_signal_keyword_competition_neutral_on_empty_or_failure(monkeypatch):
    monkeypatch.setattr(
        release_timing.autocomplete, "suggest",
        lambda q, engine="google": (_ for _ in ()).throw(Exception("ag hatasi")),
    )
    signal = release_timing.signal_keyword_competition("sanatci sarki")
    assert signal == {"competition": "medium", "score": 0.5, "alternatives": []}


# --- Sinyal 3: rakip yayinlar --------------------------------------------------

def test_signal_competitor_releases_high_risk_with_many_releases(monkeypatch):
    fake_releases = [{"title": f"T{i}", "artist-credit": [{"name": f"A{i}"}],
                       "date": "2026-03-06"} for i in range(12)]
    monkeypatch.setattr(
        release_timing, "_mb_search_releases_window",
        lambda start, end: fake_releases,
    )
    signal = release_timing.signal_competitor_releases("2026-03-06")
    assert signal["competitor_count"] == 12
    assert signal["risk"] == "high"
    assert len(signal["competitors"]) == 10  # ilk 10'a kirpilir


def test_signal_competitor_releases_low_risk_when_empty(monkeypatch):
    monkeypatch.setattr(
        release_timing, "_mb_search_releases_window", lambda start, end: []
    )
    signal = release_timing.signal_competitor_releases("2026-03-06")
    assert signal == {"competitor_count": 0, "competitors": [], "risk": "low"}


def test_signal_competitor_releases_neutral_on_network_failure(monkeypatch):
    def _raise(start, end):
        raise Exception("MusicBrainz erisilemedi")

    monkeypatch.setattr(release_timing, "_mb_search_releases_window", _raise)
    signal = release_timing.signal_competitor_releases("2026-03-06")
    assert signal == {"competitor_count": 0, "competitors": [], "risk": "low"}


# --- Sinyal 4: gun optimizasyonu (saf tarih matematigi) ------------------------

def test_signal_day_optimization_already_friday():
    # 2026-03-06 bir Cuma
    signal = release_timing.signal_day_optimization("2026-03-06")
    assert signal["recommended_day"] == "Friday"
    assert signal["score"] == 1.0
    assert signal["nearest_friday"] == "2026-03-06"


def test_signal_day_optimization_recommends_nearest_friday_forward():
    # 2026-03-04 Carsamba -> en yakin Cuma 2026-03-06 (2 gun ileri, geriye
    # gitmek 5 gun surer, ileri daha yakin)
    signal = release_timing.signal_day_optimization("2026-03-04")
    assert signal["nearest_friday"] == "2026-03-06"
    assert signal["score"] < 1.0


def test_signal_day_optimization_recommends_nearest_friday_backward():
    # 2026-03-07 Cumartesi -> en yakin Cuma 2026-03-06 (1 gun geri)
    signal = release_timing.signal_day_optimization("2026-03-07")
    assert signal["nearest_friday"] == "2026-03-06"


def test_signal_day_optimization_bad_format_raises():
    with pytest.raises(ValueError, match="Gecersiz hedef tarih"):
        release_timing.signal_day_optimization("06-03-2026")


# --- advise_release: birlesik tavsiye -----------------------------------------

def _patch_all_signals(monkeypatch, readiness_score, competition, competitor_risk):
    monkeypatch.setattr(
        release_timing, "signal_readiness",
        lambda q: {"score": readiness_score, "findings": [], "fixable_issues": []},
    )
    monkeypatch.setattr(
        release_timing, "signal_keyword_competition",
        lambda q: {"competition": competition, "score": 0.2 if competition == "low" else 0.8,
                    "alternatives": []},
    )
    monkeypatch.setattr(
        release_timing, "signal_competitor_releases",
        lambda d, window_days=7: {
            "competitor_count": 15 if competitor_risk == "high" else 0,
            "competitors": [], "risk": competitor_risk,
        },
    )


def test_advise_release_low_readiness_and_high_competitor_risk_ertele(monkeypatch):
    _patch_all_signals(monkeypatch, readiness_score=40, competition="high",
                        competitor_risk="high")
    advice = release_timing.advise_release("Sanatci - Sarki", "2026-03-06")
    assert advice["overall_verdict"] == "ertele"
    assert advice["recommended_date"] != "2026-03-06"  # cakisan haftadan kaydi


def test_advise_release_low_readiness_without_competitor_risk_hazirlan(monkeypatch):
    _patch_all_signals(monkeypatch, readiness_score=40, competition="medium",
                        competitor_risk="low")
    advice = release_timing.advise_release("Sanatci - Sarki", "2026-03-06")
    assert advice["overall_verdict"] == "hazirlan"


def test_advise_release_high_readiness_and_low_competition_hazir(monkeypatch):
    _patch_all_signals(monkeypatch, readiness_score=90, competition="low",
                        competitor_risk="low")
    advice = release_timing.advise_release("Sanatci - Sarki", "2026-03-06")
    assert advice["overall_verdict"] == "hazir"
    assert advice["report_token"].startswith("TIME-")


def test_advise_release_bad_target_date_raises(monkeypatch):
    _patch_all_signals(monkeypatch, readiness_score=90, competition="low",
                        competitor_risk="low")
    with pytest.raises(ValueError, match="Gecersiz hedef tarih"):
        release_timing.advise_release("Sanatci - Sarki", "not-a-date")


# --- Rapor persistansi ---------------------------------------------------------

def test_save_and_get_report_roundtrip(timing_db, monkeypatch):
    _patch_all_signals(monkeypatch, readiness_score=90, competition="low",
                        competitor_risk="low")
    advice = release_timing.advise_release("Sanatci - Sarki", "2026-03-06")
    saved = release_timing.save_report(1, advice)
    assert saved["report_token"] == advice["report_token"]

    fetched = release_timing.get_report(advice["report_token"])
    assert fetched is not None
    assert fetched["track_query"] == "Sanatci - Sarki"


def test_get_report_missing_token_returns_none(timing_db):
    assert release_timing.get_report("TIME-FFFFFF") is None


def test_reports_for_user_lists_own_reports_only(timing_db, monkeypatch):
    _patch_all_signals(monkeypatch, readiness_score=90, competition="low",
                        competitor_risk="low")
    advice1 = release_timing.advise_release("Sanatci - Sarki A", "2026-03-06")
    release_timing.save_report(1, advice1)
    advice2 = release_timing.advise_release("Sanatci - Sarki B", "2026-04-03")
    release_timing.save_report(2, advice2)

    reports = release_timing.reports_for_user(1)
    assert len(reports) == 1
    assert reports[0]["track_query"] == "Sanatci - Sarki A"
