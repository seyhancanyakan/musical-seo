"""Ses parmak izi (fingerprint) yayin dogrulama motoru testleri: dogru spot
yuksek skor, yanlis spot dusuk skor, gurultulu versiyon yine de eslesir,
scan_chunk verified_plays artisi + 10 dk dedupe, ffmpeg'siz capture None.
Network YOK.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from marketplace import accounts, db, fingerprint, radio_ads

RATE = 11025

# Farkli frekans desenli iki "spot": her biri birden fazla zaman diliminde
# degisen frekans ciftleri icerir (gercek bir reklam spotunun spektral
# cesitliligini simule eder — sabit tek ton olsaydi landmark eslesmesi
# anlamsiz olurdu).
PATTERN_A = [(300, 900), (500, 1200), (700, 1600), (400, 1100)]
PATTERN_B = [(350, 1000), (620, 1450), (240, 780), (910, 2000)]


def _synthesize(pattern: list[tuple[int, int]], seg_seconds: float = 0.6) -> np.ndarray:
    segments = []
    for freqs in pattern:
        t = np.linspace(0, seg_seconds, int(RATE * seg_seconds), endpoint=False)
        seg = np.zeros_like(t)
        for f in freqs:
            seg += np.sin(2 * np.pi * f * t)
        segments.append(seg)
    signal = np.concatenate(segments)
    return signal / np.max(np.abs(signal))


def _write_wav(path: Path, signal: np.ndarray, rate: int = RATE) -> None:
    int16 = (signal * 32767 * 0.9).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(int16.tobytes())


@pytest.fixture()
def fp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    return tmp_path


def _make_order(fp_db) -> dict:
    """radyo turu kurator + aktif ilan + siparis olusturur, siparis dict'ini doner."""
    curator_id = db.add_curator(
        name="Test Radyo", email="radyo@test.com", playlist_id="pid-radyo",
        playlist_title="Test Radyo Yayini", playlist_url="https://example.com/radyo",
        fans=1000, track_count=0, diversity=0.0, quality_score=10.0,
        status="approved", curator_type="radyo",
    )
    curator_user = accounts.register(
        "radyo@test.com", "parola123", "Test Radyo", "curator", curator_id=curator_id,
    )
    listing = radio_ads.create_listing(
        curator_user, "Test FM", 30, "sabah", 10, price_week_try=1000,
    )
    return radio_ads.place_order(
        listing["id"], "Sanatci A", "sanatci@test.com", "artist", weeks=1,
    )


# --- Spektrogram/eslesme dogrulugu -------------------------------------------

def test_matching_spot_scores_high(fp_db, tmp_path):
    path_a = tmp_path / "spot_a.wav"
    _write_wav(path_a, _synthesize(PATTERN_A))

    fp_a = fingerprint.fingerprint_wav(path_a)
    fp_a_again = fingerprint.fingerprint_wav(path_a)  # ayni spotun "yayin kaydi"

    assert fp_a  # bos degil
    score = fingerprint.match_score(fp_a, fp_a_again)
    assert score > 0.9


def test_wrong_spot_scores_low(fp_db, tmp_path):
    path_a = tmp_path / "spot_a.wav"
    path_b = tmp_path / "spot_b.wav"
    _write_wav(path_a, _synthesize(PATTERN_A))
    _write_wav(path_b, _synthesize(PATTERN_B))

    fp_a = fingerprint.fingerprint_wav(path_a)
    fp_b = fingerprint.fingerprint_wav(path_b)

    score = fingerprint.match_score(fp_a, fp_b)
    assert score < 0.15


def test_noisy_version_still_matches_above_threshold(fp_db, tmp_path):
    path_a = tmp_path / "spot_a.wav"
    signal = _synthesize(PATTERN_A)
    _write_wav(path_a, signal)

    rng = np.random.default_rng(42)
    noisy = signal + rng.normal(0, 0.01, size=signal.shape)
    noisy = noisy / np.max(np.abs(noisy))
    path_noisy = tmp_path / "spot_a_noisy.wav"
    _write_wav(path_noisy, noisy)

    fp_a = fingerprint.fingerprint_wav(path_a)
    fp_noisy = fingerprint.fingerprint_wav(path_noisy)

    score = fingerprint.match_score(fp_a, fp_noisy)
    assert score >= 0.15


def test_16bit_wav_required(fp_db, tmp_path):
    path = tmp_path / "bad.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(1)  # 8-bit, desteklenmiyor
        wf.setframerate(RATE)
        wf.writeframes(bytes(1000))
    with pytest.raises(ValueError, match="16-bit"):
        fingerprint.fingerprint_wav(path)


def test_mp3_without_ffmpeg_raises(fp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(fingerprint.shutil, "which", lambda _name: None)
    with pytest.raises(ValueError, match="ffmpeg"):
        fingerprint.fingerprint_wav(tmp_path / "spot.mp3")


# --- register_spot + scan_chunk + dedupe -------------------------------------

def test_register_and_scan_increments_verified_plays_and_dedupes(fp_db, tmp_path):
    order = _make_order(fp_db)
    path_a = tmp_path / "spot_a.wav"
    signal = _synthesize(PATTERN_A)
    _write_wav(path_a, signal)

    registered = fingerprint.register_spot(order["id"], str(path_a))
    assert registered["order_id"] == order["id"]
    assert registered["hash_count"] > 0

    station_id = 7
    first = fingerprint.scan_chunk(station_id, signal, RATE)
    assert len(first) == 1
    assert first[0]["order_id"] == order["id"]
    assert first[0]["confidence"] > 0.5

    updated_order = radio_ads.get_order(order["id"])
    assert updated_order["verified_plays"] == 1

    # Ayni pencere icinde ikinci tarama tekrar saymaz.
    second = fingerprint.scan_chunk(station_id, signal, RATE)
    assert second == []
    assert radio_ads.get_order(order["id"])["verified_plays"] == 1


def test_scan_chunk_counts_again_after_dedupe_window_passes(fp_db, tmp_path):
    order = _make_order(fp_db)
    path_a = tmp_path / "spot_a.wav"
    signal = _synthesize(PATTERN_A)
    _write_wav(path_a, signal)
    fingerprint.register_spot(order["id"], str(path_a))

    station_id = 3
    fingerprint.scan_chunk(station_id, signal, RATE)

    # Dedupe penceresini simule et: mevcut tespitin detected_at'ini geriye al.
    from datetime import datetime, timedelta, timezone
    conn = fingerprint._connect()
    try:
        with conn:
            old = (
                datetime.now(timezone.utc)
                - timedelta(minutes=fingerprint.DEDUPE_MINUTES + 1)
            ).isoformat()
            conn.execute("UPDATE fp_detections SET detected_at = ?", (old,))
    finally:
        conn.close()

    second = fingerprint.scan_chunk(station_id, signal, RATE)
    assert len(second) == 1
    assert radio_ads.get_order(order["id"])["verified_plays"] == 2


def test_scan_chunk_no_match_returns_empty(fp_db, tmp_path):
    order = _make_order(fp_db)
    path_a = tmp_path / "spot_a.wav"
    _write_wav(path_a, _synthesize(PATTERN_A))
    fingerprint.register_spot(order["id"], str(path_a))

    unrelated_signal = _synthesize(PATTERN_B)
    result = fingerprint.scan_chunk(99, unrelated_signal, RATE)
    assert result == []
    assert radio_ads.get_order(order["id"])["verified_plays"] == 0


# --- Canli akis yakalama (ffmpeg) ---------------------------------------------

def test_capture_stream_chunk_without_ffmpeg_returns_none(monkeypatch):
    monkeypatch.setattr(fingerprint.shutil, "which", lambda _name: None)
    assert fingerprint.capture_stream_chunk("http://example.com/stream") is None


def test_watch_once_skips_stations_without_ffmpeg(fp_db, monkeypatch):
    monkeypatch.setattr(fingerprint.shutil, "which", lambda _name: None)
    result = fingerprint.watch_once([{"id": 1, "stream_url": "http://example.com/a"}])
    assert result == {"scanned": 0, "detections": []}
