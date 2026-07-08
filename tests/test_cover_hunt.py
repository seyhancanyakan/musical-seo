"""Cover/Derivative Avcisi testleri: ses profili mesafesi (saf fonksiyon,
harmonik tempo toleransi dahil), skorlama esik ayrimi, av entegrasyonu
(toplayicilar + ses profili monkeypatch'li), dogrulama kuyrugu (approved ->
lisans teklifi, rejected -> yok, gecersiz karar -> ValueError), rapor/aday
sorgulari, watchdog, telif itirazi belgesi. Network YOK.
"""
from __future__ import annotations

import pytest

from marketplace import accounts, cover_hunter, db


@pytest.fixture()
def hunt_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


@pytest.fixture()
def artist_user(hunt_db):
    return accounts.register("avci@test.com", "parola123", "Avci Sanatci", "artist")


# --- _audio_profile_distance (saf fonksiyon) --------------------------------

def test_distance_identical_profiles_is_zero():
    profile = {"bpm": 120.0, "energy": 0.6, "brightness": 0.5}
    assert cover_hunter._audio_profile_distance(profile, profile) == 0.0


def test_distance_very_different_profiles_is_high():
    # BPM oranı (181/60 ≈ 3.02) hiçbir harmonik ilişkiye (1x/2x/0.5x) yakın
    # değil, bu yüzden tempo toleransı devreye girmez; enerji/parlaklık da
    # uçlarda -> mesafe yüksek olmalı.
    a = {"bpm": 60.0, "energy": 0.05, "brightness": 0.05}
    b = {"bpm": 181.0, "energy": 0.95, "brightness": 0.95}
    dist = cover_hunter._audio_profile_distance(a, b)
    assert dist > 0.8


def test_distance_harmonic_tempo_tolerant():
    """Ayni enerji/parlaklikta, tempo tam iki kati/yarisi olan bir cover
    (60 <-> 120 BPM) harmonik iliski sayilir -> mesafe dusuk kalir."""
    a = {"bpm": 120.0, "energy": 0.5, "brightness": 0.4}
    b = {"bpm": 60.0, "energy": 0.5, "brightness": 0.4}
    dist = cover_hunter._audio_profile_distance(a, b)
    assert dist < 0.1


def test_distance_uses_tonality_when_present():
    same_tonality = cover_hunter._audio_profile_distance(
        {"bpm": 100.0, "energy": 0.5, "brightness": 0.5, "tonality": "C"},
        {"bpm": 100.0, "energy": 0.5, "brightness": 0.5, "tonality": "C"},
    )
    diff_tonality = cover_hunter._audio_profile_distance(
        {"bpm": 100.0, "energy": 0.5, "brightness": 0.5, "tonality": "C"},
        {"bpm": 100.0, "energy": 0.5, "brightness": 0.5, "tonality": "G"},
    )
    assert same_tonality == 0.0
    assert diff_tonality > same_tonality


# --- score_candidates --------------------------------------------------------

def test_score_candidates_splits_by_threshold():
    original = {"bpm": 120.0, "energy": 0.6, "brightness": 0.5}
    candidates = [
        {  # neredeyse ozdes ses profili -> esik ustu
            "url": "https://youtube.com/watch?v=close",
            "title": "Close Cover", "channel": "ChannelA", "source": "youtube",
            "audio_profile": {"bpm": 121.0, "energy": 0.61, "brightness": 0.51},
        },
        {  # cok farkli ses profili, metin bonusu yok -> esik alti
            "url": "https://youtube.com/watch?v=far",
            "title": "Unrelated Song", "channel": "ChannelB", "source": "youtube",
            "audio_profile": {"bpm": 200.0, "energy": 0.05, "brightness": 0.05},
        },
    ]
    scored = cover_hunter.score_candidates(original, candidates)
    by_url = {c["url"]: c for c in scored}
    assert by_url["https://youtube.com/watch?v=close"]["similarity"] >= cover_hunter.SIMILARITY_THRESHOLD
    assert by_url["https://youtube.com/watch?v=far"]["similarity"] < cover_hunter.SIMILARITY_THRESHOLD


def test_score_candidates_title_and_lyric_bonus_boosts_similarity():
    candidates = [
        {"url": "https://example.com/1", "title": "No signal", "channel": "X",
         "source": "tiktok"},
        {"url": "https://genius.com/song", "title": "Matching Title", "channel": "Y",
         "source": "lyrics", "title_match": True, "lyric_match": True},
    ]
    scored = cover_hunter.score_candidates(None, candidates)
    by_url = {c["url"]: c for c in scored}
    assert by_url["https://example.com/1"]["similarity"] == 0.0
    boosted = by_url["https://genius.com/song"]
    assert boosted["similarity"] >= 0.5
    assert "başlık/söz eşleşmesi" in boosted["match_reasons"]
    assert "söz benzerliği tespit edildi" in boosted["match_reasons"]


def test_score_candidates_does_not_persist_without_hunt_id(hunt_db):
    cover_hunter.score_candidates(
        {"bpm": 120.0, "energy": 0.6, "brightness": 0.5},
        [{"url": "https://x.test/1", "title": "T", "channel": "C",
          "source": "youtube",
          "audio_profile": {"bpm": 120.0, "energy": 0.6, "brightness": 0.5}}],
    )
    conn = cover_hunter._connect()
    try:
        count = conn.execute("SELECT COUNT(*) FROM cover_candidates").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


# --- run_cover_hunt (entegrasyon, collectors + audio profile monkeypatch'li) --

def _patch_collectors(monkeypatch, original_profile, youtube=None, lyrics=None, tiktok=None):
    monkeypatch.setattr(cover_hunter, "_original_audio_profile", lambda q: original_profile)
    monkeypatch.setattr(cover_hunter, "_collect_youtube_candidates", lambda q, max_results=50: youtube or [])
    monkeypatch.setattr(cover_hunter, "_collect_lyrics_candidates", lambda q: lyrics or [])
    monkeypatch.setattr(cover_hunter, "_collect_tiktok_candidates", lambda q: tiktok or [])


def test_run_cover_hunt_persists_high_and_medium_confidence(artist_user, monkeypatch):
    original_profile = {"bpm": 120.0, "energy": 0.6, "brightness": 0.5,
                        "instrumental_score": 0.1}
    _patch_collectors(
        monkeypatch, original_profile,
        youtube=[
            {  # neredeyse ozdes -> yuksek guven
                "url": "https://youtube.com/watch?v=high",
                "title": "Exact-ish Cover", "channel": "A", "source": "youtube",
                "audio_profile": {"bpm": 120.0, "energy": 0.6, "brightness": 0.5},
            },
            {  # esik ustu ama daha az benzer -> orta guven
                "url": "https://youtube.com/watch?v=mid",
                "title": "Looser Cover", "channel": "B", "source": "youtube",
                "audio_profile": {"bpm": 124.0, "energy": 0.5, "brightness": 0.42},
            },
            {  # esik alti -> alinmaz
                "url": "https://youtube.com/watch?v=low",
                "title": "Unrelated", "channel": "C", "source": "youtube",
                "audio_profile": {"bpm": 200.0, "energy": 0.05, "brightness": 0.05},
            },
        ],
    )
    result = cover_hunter.run_cover_hunt(artist_user["id"], "Test Sarki")
    assert result["report_token"].startswith("HUNT-")
    assert result["original_query"] == "Test Sarki"
    assert result["candidates_found"] == 2
    assert result["high_confidence"] >= 1
    assert result["estimated_unlicensed_revenue"] == "$1.200"
    urls = {c["url"] for c in result["candidates"]}
    assert "https://youtube.com/watch?v=low" not in urls


def test_run_cover_hunt_dedupes_same_url_across_sources(artist_user, monkeypatch):
    profile = {"bpm": 100.0, "energy": 0.5, "brightness": 0.4}
    dup_candidate = {
        "url": "https://youtube.com/watch?v=dup", "title": "Dup", "channel": "A",
        "source": "youtube", "audio_profile": profile,
    }
    _patch_collectors(
        monkeypatch, profile, youtube=[dup_candidate], lyrics=[dict(dup_candidate, source="lyrics")],
    )
    result = cover_hunter.run_cover_hunt(artist_user["id"], "Dup Query")
    assert result["candidates_found"] == 1


def test_run_cover_hunt_empty_query_raises(artist_user, monkeypatch):
    _patch_collectors(monkeypatch, None)
    with pytest.raises(ValueError, match="boş olamaz"):
        cover_hunter.run_cover_hunt(artist_user["id"], "   ")


def test_run_cover_hunt_survives_collector_exceptions(artist_user, monkeypatch):
    monkeypatch.setattr(cover_hunter, "_original_audio_profile", lambda q: None)

    def _boom(*args, **kwargs):
        raise RuntimeError("ag hatasi")

    monkeypatch.setattr(cover_hunter, "_collect_youtube_candidates", _boom)
    monkeypatch.setattr(cover_hunter, "_collect_lyrics_candidates", lambda q: [])
    monkeypatch.setattr(cover_hunter, "_collect_tiktok_candidates", lambda q: [])
    result = cover_hunter.run_cover_hunt(artist_user["id"], "Kirilgan Sorgu")
    assert result["candidates_found"] == 0
    assert result["candidates"] == []


# --- review_candidate + generate_license_offer + generate_claim_document ----

def _seed_hunt_with_candidate(artist_user, monkeypatch, similarity=0.9):
    profile = {"bpm": 120.0, "energy": 0.6, "brightness": 0.5}
    _patch_collectors(
        monkeypatch, profile,
        youtube=[{
            "url": "https://youtube.com/watch?v=cand", "title": "Aday Video",
            "channel": "KanalX", "source": "youtube",
            "audio_profile": profile if similarity > 0.5 else
                             {"bpm": 40.0, "energy": 0.01, "brightness": 0.01},
        }],
    )
    result = cover_hunter.run_cover_hunt(artist_user["id"], "Orijinal Sarki")
    assert result["candidates"], "test fixture beklenen adayi uretemedi"
    candidate_id = cover_hunter.candidates_for(result["hunt_id"])[0]["id"]
    return result["hunt_id"], candidate_id


def test_review_candidate_approved_returns_license_offer(artist_user, monkeypatch):
    _, candidate_id = _seed_hunt_with_candidate(artist_user, monkeypatch)
    outcome = cover_hunter.review_candidate(artist_user["id"], candidate_id, "approved")
    assert outcome["next_action"] == "license_offer"
    assert outcome["license_amount"] > 0
    stored = cover_hunter.candidates_for(0, status=None)  # sanity: fonksiyon calisir
    assert isinstance(stored, list)
    approved = cover_hunter._get_candidate(candidate_id)
    assert approved["status"] == "approved"


def test_review_candidate_rejected_has_no_license_action(artist_user, monkeypatch):
    _, candidate_id = _seed_hunt_with_candidate(artist_user, monkeypatch)
    outcome = cover_hunter.review_candidate(artist_user["id"], candidate_id, "rejected")
    assert outcome["next_action"] == "none"
    assert "license_amount" not in outcome
    rejected = cover_hunter._get_candidate(candidate_id)
    assert rejected["status"] == "rejected"


def test_review_candidate_invalid_verdict_raises(artist_user, monkeypatch):
    _, candidate_id = _seed_hunt_with_candidate(artist_user, monkeypatch)
    with pytest.raises(ValueError, match="Geçersiz karar"):
        cover_hunter.review_candidate(artist_user["id"], candidate_id, "maybe")


def test_review_candidate_unknown_id_raises(artist_user):
    with pytest.raises(ValueError, match="bulunamadı"):
        cover_hunter.review_candidate(artist_user["id"], 999999, "approved")


def test_generate_license_offer_persists_and_marks_licensed(artist_user, monkeypatch):
    _, candidate_id = _seed_hunt_with_candidate(artist_user, monkeypatch)
    cover_hunter.review_candidate(artist_user["id"], candidate_id, "approved")
    offer = cover_hunter.generate_license_offer(candidate_id)
    assert offer["amount"] > 0
    assert offer["license_type"] == "sync_cover_license"
    assert "terms" in offer and "message_template" in offer
    licensed = cover_hunter._get_candidate(candidate_id)
    assert licensed["status"] == "licensed"


def test_generate_claim_document_contains_refs(artist_user, monkeypatch):
    _, candidate_id = _seed_hunt_with_candidate(artist_user, monkeypatch)
    doc = cover_hunter.generate_claim_document(candidate_id)
    assert doc["isrc_ref"]
    assert doc["iswc_ref"]
    assert "instructions" in doc and "Content ID" in doc["instructions"] or "Copyright" in doc["instructions"]


# --- get_report + candidates_for --------------------------------------------

def test_get_report_returns_none_for_missing_token(hunt_db):
    assert cover_hunter.get_report("HUNT-DEADBEEF") is None


def test_get_report_returns_hunt_and_candidates(artist_user, monkeypatch):
    hunt_id, _candidate_id = _seed_hunt_with_candidate(artist_user, monkeypatch)
    conn = cover_hunter._connect()
    try:
        token = conn.execute(
            "SELECT report_token FROM cover_hunts WHERE id = ?", (hunt_id,)
        ).fetchone()[0]
    finally:
        conn.close()
    report = cover_hunter.get_report(token)
    assert report is not None
    assert report["id"] == hunt_id
    assert len(report["candidates"]) == 1
    assert isinstance(report["candidates"][0]["match_reasons"], list)


def test_candidates_for_filters_by_status(artist_user, monkeypatch):
    hunt_id, candidate_id = _seed_hunt_with_candidate(artist_user, monkeypatch)
    cover_hunter.review_candidate(artist_user["id"], candidate_id, "approved")
    approved_only = cover_hunter.candidates_for(hunt_id, status="approved")
    pending_only = cover_hunter.candidates_for(hunt_id, status="pending")
    assert len(approved_only) == 1
    assert pending_only == []


# --- watchdog -----------------------------------------------------------------

def test_enable_watchdog_returns_interval(artist_user):
    result = cover_hunter.enable_watchdog(artist_user["id"], "Nobetci Sarki")
    assert result == {"ok": True, "interval_hours": 168}


def test_enable_watchdog_empty_query_raises(artist_user):
    with pytest.raises(ValueError, match="boş olamaz"):
        cover_hunter.enable_watchdog(artist_user["id"], "")


# --- import sanity -----------------------------------------------------------

def test_api_module_imports_without_network():
    import marketplace.api_cover_hunt  # noqa: F401
