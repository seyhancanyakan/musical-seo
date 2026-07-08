"""Promosyon ROI Atif Motoru testleri: changepoint tespiti (duz/yukselen/kisa
seri), olay atifi korunumu (radyo > playlist > organik agirlik), rapor
uretimi entegrasyonu (sentetik veriyle _collect_* fonksiyonlari monkeypatch
edilir), bos donem -> notr rapor (asla patlamaz), kalicilik (get_report/
reports_for_user). Network YOK.
"""
from __future__ import annotations

import pytest

from marketplace import accounts, attribution, db


@pytest.fixture()
def attribution_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


@pytest.fixture()
def artist_user(attribution_db):
    return accounts.register("sanatci@test.com", "parola123", "Test Sanatci", "artist")


# --- _detect_changepoints (PURE) ------------------------------------------------

def test_detect_changepoints_flat_series_returns_empty():
    scores = [
        {"date": f"2026-01-{d:02d}", "score": 50} for d in range(1, 16)
    ]
    assert attribution._detect_changepoints(scores) == []


def test_detect_changepoints_declining_series_returns_empty():
    scores = [
        {"date": f"2026-01-{d:02d}", "score": 80 - d} for d in range(1, 16)
    ]
    assert attribution._detect_changepoints(scores) == []


def test_detect_changepoints_short_series_returns_empty():
    assert attribution._detect_changepoints([{"date": "2026-01-01", "score": 50}]) == []
    assert attribution._detect_changepoints([]) == []


def test_detect_changepoints_rising_series_detects_changepoint():
    scores = [{"date": f"2026-01-{d:02d}", "score": 40} for d in range(1, 8)]
    scores += [{"date": f"2026-01-{d:02d}", "score": 70} for d in range(8, 16)]
    changepoints = attribution._detect_changepoints(scores)
    assert len(changepoints) >= 1
    cp = changepoints[0]
    assert cp["delta"] > 5
    assert 0 < cp["confidence"] <= 1.0
    assert cp["date"] >= "2026-01-08"


# --- _attribute_to_events (PURE, korunum) ---------------------------------------

def test_attribute_to_events_conservation_no_relevant_events():
    changepoint = {"date": "2026-01-15", "delta": 20.0, "confidence": 0.8}
    distributed = attribution._attribute_to_events(changepoint, [])
    assert len(distributed) == 1
    assert distributed[0]["channel"] == "organik"
    assert distributed[0]["attributed_delta"] == pytest.approx(20.0)


def test_attribute_to_events_conservation_with_mixed_events():
    changepoint = {"date": "2026-01-15", "delta": 20.0, "confidence": 0.8}
    events = [
        {"date": "2026-01-12", "type": "radyo", "source_id": 1},
        {"date": "2026-01-13", "type": "playlist", "source_id": 2},
        {"date": "2025-11-01", "type": "playlist", "source_id": 3},  # pencere disi
    ]
    distributed = attribution._attribute_to_events(changepoint, events)
    total = sum(item["attributed_delta"] for item in distributed)
    assert total == pytest.approx(20.0)
    channels = {item["channel"] for item in distributed}
    assert channels == {"radyo", "playlist", "organik"}
    # Pencere disindaki 3. olay dagitima dahil edilmemeli (sadece 2 olay + organik).
    assert len(distributed) == 3


def test_attribute_to_events_radyo_weighted_more_than_playlist():
    changepoint = {"date": "2026-01-15", "delta": 30.0, "confidence": 0.9}
    events = [
        {"date": "2026-01-12", "type": "radyo", "source_id": 1},
        {"date": "2026-01-13", "type": "playlist", "source_id": 2},
    ]
    distributed = attribution._attribute_to_events(changepoint, events)
    radyo = next(i for i in distributed if i["channel"] == "radyo")
    playlist = next(i for i in distributed if i["channel"] == "playlist")
    assert radyo["attributed_delta"] > playlist["attributed_delta"]
    total = sum(i["attributed_delta"] for i in distributed)
    assert total == pytest.approx(30.0)


def test_attribute_to_events_conservation_holds_for_many_events():
    changepoint = {"date": "2026-02-01", "delta": 45.5, "confidence": 0.6}
    events = [
        {"date": "2026-01-27", "type": "radyo", "source_id": i} for i in range(3)
    ] + [
        {"date": "2026-01-28", "type": "playlist", "source_id": i} for i in range(4)
    ]
    distributed = attribution._attribute_to_events(changepoint, events)
    total = sum(item["attributed_delta"] for item in distributed)
    assert total == pytest.approx(45.5)


# --- build_attribution_report (entegrasyon, sentetik _collect_*) ---------------

def _patch_collectors(monkeypatch, scores, placements, airplay):
    monkeypatch.setattr(attribution, "_collect_seo_series", lambda *a, **k: scores)
    monkeypatch.setattr(attribution, "_collect_placement_events", lambda *a, **k: placements)
    monkeypatch.setattr(attribution, "_collect_airplay_events", lambda *a, **k: airplay)


def test_build_attribution_report_with_synthetic_rising_data(artist_user, monkeypatch):
    scores = [{"date": f"2026-01-{d:02d}", "score": 40} for d in range(1, 8)]
    scores += [{"date": f"2026-01-{d:02d}", "score": 75} for d in range(8, 16)]
    placements = [{"date": "2026-01-09", "type": "playlist", "source_id": 11}]
    airplay = [{"date": "2026-01-10", "type": "radyo", "source_id": 22}]
    _patch_collectors(monkeypatch, scores, placements, airplay)

    report = attribution.build_attribution_report(
        artist_user["id"], "Test Sanatci - Test Sarki", "2026-01-01", "2026-01-15",
    )
    assert report["report_token"].startswith("ATTR-")
    assert report["total_score_delta"] > 0
    channels = {b["channel"] for b in report["breakdown"]}
    assert "radyo" in channels or "playlist" in channels
    assert report["recommendation"]


def test_build_attribution_report_empty_data_is_neutral_no_crash(artist_user, monkeypatch):
    _patch_collectors(monkeypatch, [], [], [])
    report = attribution.build_attribution_report(
        artist_user["id"], "Bilinmeyen - Sarki", "2026-01-01", "2026-01-31",
    )
    assert report["total_score_delta"] == 0
    assert len(report["breakdown"]) == 1
    assert report["breakdown"][0]["channel"] == "organik"
    assert report["breakdown"][0]["attributed_delta"] == 0


def test_build_attribution_report_real_collectors_no_data_never_crashes(artist_user):
    """Gercek _collect_* fonksiyonlari (mock yok) — hicbir snapshot/yerlesim/
    yayin olmadan cagri patlamamali, notr rapor donmeli."""
    report = attribution.build_attribution_report(
        artist_user["id"], "Hic Olmayan Sanatci - Hic Olmayan Sarki",
        "2026-01-01", "2026-01-02",
    )
    assert report["total_score_delta"] == 0
    assert report["breakdown"][0]["channel"] == "organik"


def test_build_attribution_report_persists_and_retrievable(artist_user, monkeypatch):
    scores = [{"date": f"2026-01-{d:02d}", "score": 40} for d in range(1, 8)]
    scores += [{"date": f"2026-01-{d:02d}", "score": 75} for d in range(8, 16)]
    _patch_collectors(monkeypatch, scores, [], [])

    report = attribution.build_attribution_report(
        artist_user["id"], "Test Sanatci - Test Sarki", "2026-01-01", "2026-01-15",
    )
    fetched = attribution.get_report(report["report_token"])
    assert fetched is not None
    assert fetched["track_query"] == "Test Sanatci - Test Sarki"
    assert fetched["user_id"] == artist_user["id"]
    assert isinstance(fetched["breakdown"], list)
    assert isinstance(fetched["events"], list)


def test_get_report_unknown_token_returns_none(artist_user):
    assert attribution.get_report("ATTR-NOPE00") is None


def test_reports_for_user_lists_history(artist_user, monkeypatch):
    _patch_collectors(monkeypatch, [], [], [])
    attribution.build_attribution_report(
        artist_user["id"], "A - B", "2026-01-01", "2026-01-05",
    )
    attribution.build_attribution_report(
        artist_user["id"], "C - D", "2026-01-06", "2026-01-10",
    )
    history = attribution.reports_for_user(artist_user["id"])
    assert len(history) == 2
    assert all(r["user_id"] == artist_user["id"] for r in history)
