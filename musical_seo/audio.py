"""Ses analizi — Deezer 30 sn onizlemelerinden yasal ses profili.

Deezer API her parca icin resmi 'preview' (30 sn MP3) verir; bu modul o
onizlemeyi indirir ve librosa ile SADECE sayisal ozellik cikarir (ses
saklanmaz): tempo (BPM), enerji (RMS), parlaklik (spectral centroid) ve
kaba bir enstrumantallik sezgisi. Amac: sarki <-> playlist muzikal uyumunu
metin metadata'sina (yanlis tur etiketi vb.) mahkum olmadan olcmek.

Kutuphane modulu: print yok; ag/cozumleme hatalarinda None doner, exception
atmaz. Sonuclar URL bazinda modul-ici cache'lenir (ayni onizleme iki kez
analiz edilmez). librosa kurulu degilse tum fonksiyonlar None/[] doner —
playlist eslestirme ses katmani olmadan calismaya devam eder.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

import requests

try:  # librosa agir bagimlilik — yoksa modul sessizce devre disi kalir
    import librosa
    import numpy as np
    _AUDIO_OK = True
except ImportError:  # pragma: no cover
    _AUDIO_OK = False

_TIMEOUT = 15
_ANALYSIS_SR = 22050        # analiz icin yeterli, hiz icin dusuk tutuldu
_ANALYSIS_DURATION = 20.0   # onizlemenin ilk 20 sn'si yeterli
_ENERGY_NORM = 0.25         # tipik yuksek-seviye master RMS'i ~0.2-0.3
_BRIGHTNESS_NORM = 4000.0   # centroid Hz normalizasyon tavani
_VOCAL_BAND = (300.0, 3400.0)  # insan sesi enerji bandi

_cache: dict[str, "AudioProfile | None"] = {}


@dataclass(frozen=True)
class AudioProfile:
    """Bir parcanin (veya playlist ortalamasinin) sayisal ses profili."""

    bpm: float
    energy: float              # 0-1 (RMS, _ENERGY_NORM'a gore)
    brightness: float          # 0-1 (spectral centroid / _BRIGHTNESS_NORM)
    instrumental_score: float  # 0-1, 1 = muhtemelen enstrumantal (SEZGISEL)


def available() -> bool:
    return _AUDIO_OK


def analyze_url(preview_url: str) -> AudioProfile | None:
    """30 sn onizleme URL'ini indir + analiz et. Hata -> None. Cache'li."""
    if not _AUDIO_OK or not preview_url:
        return None
    if preview_url in _cache:
        return _cache[preview_url]
    profile = _analyze(preview_url)
    _cache[preview_url] = profile
    return profile


def _analyze(preview_url: str) -> AudioProfile | None:
    # NOT: BytesIO uzerinden degil dosya yolundan yukluyoruz — Deezer
    # onizlemelerindeki bos ID3v2 etiketi libsndfile'in bellek-ici format
    # tespitini bozuyor ("Format not recognised"); dosya yolundan sorunsuz.
    tmp_path = None
    try:
        resp = requests.get(preview_url, timeout=_TIMEOUT)
        if resp.status_code != 200 or not resp.content:
            return None
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name
        y, sr = librosa.load(
            tmp_path,
            sr=_ANALYSIS_SR,
            mono=True,
            duration=_ANALYSIS_DURATION,
        )
    except Exception:
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    if y is None or len(y) < sr:  # 1 saniyeden kisa ise anlamsiz
        return None

    try:
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(np.atleast_1d(tempo)[0])

        rms = float(np.mean(librosa.feature.rms(y=y)))
        energy = min(rms / _ENERGY_NORM, 1.0)

        centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        brightness = min(centroid / _BRIGHTNESS_NORM, 1.0)

        instrumental = _instrumental_score(y, sr)
    except Exception:
        return None

    return AudioProfile(
        bpm=bpm,
        energy=energy,
        brightness=brightness,
        instrumental_score=instrumental,
    )


def _instrumental_score(y, sr) -> float:
    """Kaba sezgi: vokal 300-3400 Hz bandinda yogun ve zamanla dalgali enerji
    birakir. Bant orani + centroid dalgalanmasi dusukse enstrumantal say."""
    spec = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    band = (freqs >= _VOCAL_BAND[0]) & (freqs <= _VOCAL_BAND[1])
    total = float(np.sum(spec)) or 1.0
    band_ratio = float(np.sum(spec[band, :])) / total  # 0-1

    centroid_t = librosa.feature.spectral_centroid(S=spec, sr=sr)[0]
    mean_c = float(np.mean(centroid_t)) or 1.0
    centroid_var = float(np.std(centroid_t)) / mean_c  # goreli dalgalanma

    vocal_evidence = min(band_ratio * 1.4, 1.0) * min(centroid_var * 2.5, 1.0)
    return round(1.0 - min(vocal_evidence, 1.0), 3)


def profile_from_previews(preview_urls: list[str], sample: int = 3) -> AudioProfile | None:
    """Birden fazla onizlemenin ortalama profili (playlist icin). En az bir
    parca cozumlenirse ortalama doner, hicbiri cozumlenmezse None."""
    profiles = []
    for url in preview_urls[:sample]:
        p = analyze_url(url)
        if p is not None:
            profiles.append(p)
    if not profiles:
        return None
    n = len(profiles)
    return AudioProfile(
        bpm=sum(p.bpm for p in profiles) / n,
        energy=sum(p.energy for p in profiles) / n,
        brightness=sum(p.brightness for p in profiles) / n,
        instrumental_score=sum(p.instrumental_score for p in profiles) / n,
    )


def similarity(a: AudioProfile, b: AudioProfile) -> float:
    """Iki profil arasi benzerlik 0-1. BPM ve enerji agir basar."""
    bpm_dist = min(abs(a.bpm - b.bpm) / 60.0, 1.0)
    energy_dist = abs(a.energy - b.energy)
    brightness_dist = abs(a.brightness - b.brightness)
    instr_dist = abs(a.instrumental_score - b.instrumental_score)
    dist = (0.3 * bpm_dist + 0.3 * energy_dist
            + 0.2 * brightness_dist + 0.2 * instr_dist)
    return round(1.0 - dist, 3)


def mood_keywords(profile: AudioProfile) -> list[str]:
    """Profilden playlist arama terimleri uret (Deezer'da Ingilizce terimler
    kuresel sonuc verir). Yanlis tur etiketine ('Pop') alternatif sinyal."""
    calm = profile.energy < 0.4 and profile.bpm < 100
    energetic = profile.energy > 0.65 and profile.bpm > 115
    instrumental = profile.instrumental_score > 0.5

    if calm and instrumental:
        return ["peaceful piano", "calm instrumental", "ambient",
                "meditation", "relaxing piano", "sleep music"]
    if calm:
        return ["acoustic calm", "soft pop", "chill vibes", "slow songs"]
    if energetic and instrumental:
        return ["epic instrumental", "cinematic", "electronic focus", "workout"]
    if energetic:
        return ["workout", "running motivation", "dance party", "energy boost"]
    if instrumental:
        return ["instrumental focus", "study beats", "cinematic instrumental",
                "lofi instrumental"]
    return ["feel good", "good vibes", "indie mix", "acoustic pop"]
