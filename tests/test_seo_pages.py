"""Programatik SEO altyapisi testleri: slugify (Turkce/noktalama), kuyruk
idempotency, build_next_batch (basarili/thin/failed — audit.run_audit
monkeypatch'lenir, AG YOK), sayfa roundtrip, sitemap shard'lari, lead
yakalama (gecerli/gecersiz/dedupe).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from marketplace import db, leads, seo_pages


@pytest.fixture()
def seo_db(tmp_path, monkeypatch):
    monkeypatch.setattr(seo_pages, "_DB_PATH", tmp_path / "seo_pages.db")


@pytest.fixture()
def leads_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


def _fake_result(artist="Test Sanatci", score=80, found_sources=2, findings=None):
    sources = [SimpleNamespace(found=True) for _ in range(found_sources)]
    sources += [SimpleNamespace(found=False) for _ in range(3 - found_sources)]
    return SimpleNamespace(
        resolved_artist=artist,
        resolved_title="Test Sarki",
        score=score,
        sources=sources,
        findings=findings or [],
        to_dict=lambda: {
            "resolved_artist": artist,
            "resolved_title": "Test Sarki",
            "score": score,
        },
    )


# --- slugify -------------------------------------------------------------

def test_slugify_turkish_chars():
    assert seo_pages.slugify("Şıla Öztürk Çağrı Ünsal Ğüven") == "sila-ozturk-cagri-unsal-guven"


def test_slugify_spaces_and_punctuation():
    assert seo_pages.slugify("  Drake & Friends!! ") == "drake-friends"


def test_slugify_empty_raises():
    with pytest.raises(ValueError):
        seo_pages.slugify("   ")


# --- enqueue_artist --------------------------------------------------------

def test_enqueue_artist_idempotent(seo_db):
    first = seo_pages.enqueue_artist("Drake")
    second = seo_pages.enqueue_artist("Drake")
    assert first["id"] == second["id"]

    conn = seo_pages._connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM build_queue WHERE ref = 'Drake'"
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 1


def test_enqueue_artist_invalid_raises(seo_db):
    with pytest.raises(ValueError):
        seo_pages.enqueue_artist("   ")


# --- build_next_batch --------------------------------------------------------

def test_build_next_batch_success(seo_db, monkeypatch):
    seo_pages.enqueue_artist("Drake")
    monkeypatch.setattr(seo_pages.audit, "run_audit", lambda q: _fake_result())

    result = seo_pages.build_next_batch()
    assert result == {"processed": 1, "built": 1, "thin": 0, "failed": 0}

    page = seo_pages.get_artist_page("test-sanatci")
    assert page is not None
    assert page["score"] == 80
    assert page["platform_count"] == 2


def test_build_next_batch_thin_skipped(seo_db, monkeypatch):
    seo_pages.enqueue_artist("Bilinmeyen Sanatci")
    monkeypatch.setattr(
        seo_pages.audit, "run_audit",
        lambda q: _fake_result(score=None, found_sources=0),
    )

    result = seo_pages.build_next_batch()
    assert result == {"processed": 1, "built": 0, "thin": 1, "failed": 0}
    assert seo_pages.get_artist_page("bilinmeyen-sanatci") is None


def test_build_next_batch_zero_platform_count_is_thin(seo_db, monkeypatch):
    seo_pages.enqueue_artist("Sifir Platform")
    monkeypatch.setattr(
        seo_pages.audit, "run_audit",
        lambda q: _fake_result(score=50, found_sources=0),
    )
    result = seo_pages.build_next_batch()
    assert result["thin"] == 1
    assert result["built"] == 0


def test_build_next_batch_audit_raises_marks_failed(seo_db, monkeypatch):
    seo_pages.enqueue_artist("Patlayan Sorgu")

    def _boom(q):
        raise RuntimeError("network down")

    monkeypatch.setattr(seo_pages.audit, "run_audit", _boom)

    result = seo_pages.build_next_batch()
    assert result == {"processed": 1, "built": 0, "thin": 0, "failed": 1}


def test_build_next_batch_findings_top3(seo_db, monkeypatch):
    seo_pages.enqueue_artist("Cok Bulgulu")
    findings = [
        SimpleNamespace(severity="critical", category="metadata", message=f"m{i}", action=None)
        for i in range(5)
    ]
    monkeypatch.setattr(
        seo_pages.audit, "run_audit",
        lambda q: _fake_result(artist="Cok Bulgulu", findings=findings),
    )
    seo_pages.build_next_batch()
    page = seo_pages.get_artist_page("cok-bulgulu")
    assert len(page["findings_json"]) == 3


# --- get_*_page roundtrip ------------------------------------------------

def test_get_artist_page_missing_returns_none(seo_db):
    assert seo_pages.get_artist_page("does-not-exist") is None


def test_get_song_page_roundtrip(seo_db):
    built = seo_pages.upsert_song_page(
        "USRC12345", "test-song", "Test Sanatci", "Test Sarki",
        score=75.0, bpm=120.0, song_key="C major", data={"foo": "bar"},
    )
    assert built["isrc"] == "USRC12345"
    fetched = seo_pages.get_song_page("USRC12345")
    assert fetched["data_json"] == {"foo": "bar"}
    assert fetched["bpm"] == 120.0


def test_upsert_song_page_thin_guard_skips(seo_db):
    result = seo_pages.upsert_song_page(
        "USRC00000", "no-score", "Sanatci", "Sarki", score=None,
    )
    assert result["skipped"] is True
    assert seo_pages.get_song_page("USRC00000") is None


def test_upsert_playlist_page_builds(seo_db):
    built = seo_pages.upsert_playlist_page(
        "pl-123", "todays-top-hits", "Todays Top Hits",
        fraud_score=12.5, verdict="guvenli", data={"tracks": 50},
    )
    assert built["verdict"] == "guvenli"
    fetched = seo_pages.get_playlist_page("pl-123")
    assert fetched["fraud_score"] == 12.5


# --- pages_for_sitemap --------------------------------------------------------

def test_pages_for_sitemap_invalid_page_type_raises(seo_db):
    with pytest.raises(ValueError):
        seo_pages.pages_for_sitemap("invalid")


def test_pages_for_sitemap_returns_shape(seo_db, monkeypatch):
    seo_pages.enqueue_artist("Drake")
    monkeypatch.setattr(seo_pages.audit, "run_audit", lambda q: _fake_result())
    seo_pages.build_next_batch()

    shard = seo_pages.pages_for_sitemap("artist")
    assert len(shard) == 1
    assert shard[0]["slug"] == "test-sanatci"
    assert "last_refreshed_at" in shard[0]


# --- leads ---------------------------------------------------------------

def test_capture_lead_valid(leads_db):
    lead = leads.capture_lead("user@example.com", "artist-page", {"slug": "drake"})
    assert lead["email"] == "user@example.com"
    assert lead["context"] == {"slug": "drake"}


def test_capture_lead_invalid_email_raises(leads_db):
    with pytest.raises(ValueError):
        leads.capture_lead("not-an-email", "artist-page")


def test_capture_lead_dedupes_same_email_and_source(leads_db):
    first = leads.capture_lead("dupe@example.com", "song-page")
    second = leads.capture_lead("dupe@example.com", "song-page")
    assert first["id"] == second["id"]
    assert leads.leads_count() == 1


def test_capture_lead_different_source_not_deduped(leads_db):
    leads.capture_lead("multi@example.com", "song-page")
    leads.capture_lead("multi@example.com", "artist-page")
    assert leads.leads_count() == 2


def test_recent_leads_orders_desc(leads_db):
    leads.capture_lead("a@example.com", "s1")
    leads.capture_lead("b@example.com", "s2")
    recent = leads.recent_leads(limit=10)
    assert len(recent) == 2
    assert recent[0]["email"] == "b@example.com"


def test_capture_lead_sends_welcome_email_on_genuinely_new_capture(
    leads_db, monkeypatch,
):
    sent_calls = []
    monkeypatch.setattr(
        leads.mailer, "send_email",
        lambda *a, **k: sent_calls.append((a, k)) or {"ok": True},
    )

    leads.capture_lead("new@example.com", "artist-page")

    assert len(sent_calls) == 1
    args, kwargs = sent_calls[0]
    assert args[0] == "new@example.com"
    assert kwargs.get("category") == "welcome"


def test_capture_lead_dedupe_hit_does_not_send_second_welcome_email(
    leads_db, monkeypatch,
):
    sent_calls = []
    monkeypatch.setattr(
        leads.mailer, "send_email",
        lambda *a, **k: sent_calls.append((a, k)) or {"ok": True},
    )

    leads.capture_lead("dupe2@example.com", "song-page")
    leads.capture_lead("dupe2@example.com", "song-page")  # 24s icinde dedupe

    assert len(sent_calls) == 1  # sadece ilk (genuinely new) capture'da mail


def test_capture_lead_email_failure_does_not_break_capture(leads_db, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("mail servisi coktu")

    monkeypatch.setattr(leads.mailer, "send_email", _boom)

    lead = leads.capture_lead("boom@example.com", "artist-page")

    assert lead["email"] == "boom@example.com"  # capture basarili kaldi
