"""Kurator turleri + primary/secondary firsat sistemi + performans metrikleri.

Network YOK — deezer.lookup sahtelenir, DB tmp_path'e yazilir.
"""
from __future__ import annotations

import pytest

from marketplace import db, pricing, service
from musical_seo.models import TrackInfo

FEEDBACK = "Miks temiz, nakarat guclu ancak listenin tempo profiline gore giris uzun kaliyor; ikinci verse vokal katmani cok iyi calisilmis." * 2


@pytest.fixture()
def opp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    # Dinleme kapisi bu testlerin konusu degil (test_revenue'da ayrica test edilir)
    monkeypatch.setattr(pricing, "LISTEN_GATE_SECONDS", 0)
    monkeypatch.setattr(
        service.deezer, "lookup",
        lambda artist, title: TrackInfo(
            source="deezer", found=True, title=title, artist=artist,
            url="https://www.deezer.com/track/1",
        ),
    )
    curator_id = db.add_curator(
        name="Radyo Programcisi", email="radyo@test.com", playlist_id="pro_radyo_x",
        playlist_title="Radyo — X", playlist_url="", fans=0, track_count=0,
        diversity=0.0, quality_score=0.0, status="approved", curator_type="radyo",
    )
    return curator_id


# --- Saf dogrulama -------------------------------------------------------

def test_validate_opportunity_defaults_primary_on_accept():
    level, kind = service.validate_opportunity(None, None, "accepted", "radyo")
    assert (level, kind) == ("primary", "radyo_calma")


def test_validate_opportunity_none_on_reject():
    assert service.validate_opportunity(None, None, "rejected", "playlist") == (None, None)


def test_validate_opportunity_rejects_bad_level():
    with pytest.raises(ValueError):
        service.validate_opportunity("mega", "playlist_ekleme", "accepted", "playlist")


def test_validate_opportunity_rejects_mismatched_kind():
    with pytest.raises(ValueError):
        service.validate_opportunity("primary", "sosyal_paylasim", "accepted", "playlist")
    with pytest.raises(ValueError):
        service.validate_opportunity("secondary", "playlist_ekleme", "rejected", "playlist")


# --- Pro (playlist disi) basvuru ------------------------------------------

def test_apply_pro_curator_pending_without_playlist(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    curator = service.apply_curator(
        "Label A&R", "ar@label.com", "", curator_type="label"
    )
    assert curator["curator_type"] == "label"
    assert curator["status"] == "pending"          # admin onayina duser
    assert curator["deezer_playlist_id"].startswith("pro_label_")


def test_apply_pro_curator_rejects_playlist_type():
    with pytest.raises(ValueError):
        service.apply_pro_curator("X", "x@y.com", "playlist")


def test_apply_curator_rejects_unknown_type(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    with pytest.raises(ValueError):
        service.apply_curator("X", "x@y.com", "", curator_type="astrolog")


# --- Yanit + firsat kaydi --------------------------------------------------

def test_respond_records_default_primary_opportunity(opp_db):
    curator_id = opp_db
    sub = service.create_submission("Sanatci", "Sarki", curator_id)
    updated = service.respond(sub["id"], "accepted", FEEDBACK)
    assert updated["opportunity_level"] == "primary"
    assert updated["opportunity_kind"] == "radyo_calma"   # kurator turu = radyo


def test_respond_records_secondary_opportunity_on_reject(opp_db):
    curator_id = opp_db
    sub = service.create_submission("Sanatci", "Sarki 2", curator_id)
    updated = service.respond(
        sub["id"], "rejected", FEEDBACK,
        opportunity_level="secondary", opportunity_kind="tavsiye",
    )
    assert updated["opportunity_level"] == "secondary"
    assert updated["opportunity_kind"] == "tavsiye"


# --- Metrikler ---------------------------------------------------------------

def test_curator_stats_rates(opp_db):
    curator_id = opp_db
    s1 = service.create_submission("A", "S1", curator_id)
    s2 = service.create_submission("A", "S2", curator_id)
    s3 = service.create_submission("A", "S3", curator_id)

    service.respond(s1["id"], "accepted", FEEDBACK)                     # primary otomatik
    service.respond(s2["id"], "rejected", FEEDBACK)                     # firsatsiz red
    # s3 SLA disi kalsin -> expired
    conn = db._connect()
    with conn:
        conn.execute(
            "UPDATE submissions SET status = 'expired' WHERE id = ?", (s3["id"],)
        )
    conn.close()

    stats = db.curator_stats(curator_id)[curator_id]
    assert stats["total_submissions"] == 3
    assert stats["responded"] == 2
    assert stats["accepted"] == 1
    assert stats["response_rate"] == 67   # 2 / (2+1)
    assert stats["success_rate"] == 50    # 1 / 2
    assert stats["opportunity_rate"] == 50  # sadece s1 etiketli


def test_curator_stats_empty_returns_no_rates(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    assert db.curator_stats() == {}
