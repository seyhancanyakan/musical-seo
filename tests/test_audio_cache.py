"""musical_seo.audio kalici cache testleri (network YOK, librosa gerekmez)."""
from __future__ import annotations

from musical_seo import audio


def test_cache_roundtrip(tmp_path, monkeypatch):
    # Arrange: cache DB'yi gecici dizine yonlendir
    monkeypatch.setattr(audio, "_DB_PATH", tmp_path / "audio_cache.db")
    profile = audio.AudioProfile(
        bpm=117.5, energy=0.28, brightness=0.34, instrumental_score=0.3
    )
    url = "https://cdn-preview-x.dzcdn.net/stream/abc-1.mp3?hdnea=exp123"

    # Act
    audio._cache_put(url, profile)
    loaded = audio._cache_get(url)

    # Assert
    assert loaded is not None
    assert loaded.bpm == profile.bpm
    assert loaded.energy == profile.energy
    assert loaded.brightness == profile.brightness
    assert loaded.instrumental_score == profile.instrumental_score


def test_cache_key_ignores_query_string(tmp_path, monkeypatch):
    # Ayni onizlemenin farkli imzali URL'leri ayni kayda dusmeli
    monkeypatch.setattr(audio, "_DB_PATH", tmp_path / "audio_cache.db")
    profile = audio.AudioProfile(
        bpm=90.0, energy=0.5, brightness=0.4, instrumental_score=0.8
    )
    audio._cache_put("https://cdn/x.mp3?token=AAA", profile)

    assert audio._cache_get("https://cdn/x.mp3?token=BBB") is not None


def test_cache_get_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "_DB_PATH", tmp_path / "audio_cache.db")
    assert audio._cache_get("https://cdn/yok.mp3") is None
