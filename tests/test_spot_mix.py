"""Suno otomatik jingle + reklam mix (voiceover + bed muzik) testleri.

Network YOK: Suno/LLM cagrilari monkeypatch'lenir. mix_ad GERCEK ffmpeg
kullanir (kurulu degilse ilgili test atlanir).
"""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from marketplace import db, spot_ai


@pytest.fixture()
def spot_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    monkeypatch.setattr(spot_ai, "SPOTS_DIR", tmp_path / "spots")
    monkeypatch.setattr(spot_ai, "JINGLES_DIR", tmp_path / "jingles")
    return tmp_path


# --- Suno istem uretimi ------------------------------------------------------

def test_suggest_prompt_heuristic_no_llm(spot_db, monkeypatch):
    monkeypatch.setattr(spot_ai, "_llm_config", lambda: ("u", "m", None))
    p = spot_ai.suggest_jingle_prompt("Afyon Lokum", "acilis", "samimi")
    assert "instrumental" in p.lower()
    assert "no vocals" in p.lower()
    assert "afyon lokum" in p.lower()


def test_extract_audio_url_from_data(spot_db):
    rj = {"data": [{"audio_url": "https://x/a.mp3", "duration": 10.7}]}
    url, dur = spot_ai._extract_audio_url(rj)
    assert url == "https://x/a.mp3" and dur == 10.7


def test_extract_audio_url_recursive_fallback(spot_db):
    rj = {"weird": {"nested": ["not", "https://y/z.m4a?token=1"]}}
    url, dur = spot_ai._extract_audio_url(rj)
    assert url.endswith(".m4a?token=1") and dur is None


# --- auto_jingle + poll (Suno monkeypatch) -----------------------------------

class _Resp:
    def __init__(self, payload):
        self._p = payload
        self.content = b""

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def test_auto_jingle_creates_generating(spot_db, monkeypatch):
    monkeypatch.setattr(spot_ai, "_suno_config", lambda: ("https://api", "key"))
    monkeypatch.setattr(
        spot_ai.requests, "post",
        lambda *a, **k: _Resp({"data": {"taskId": "task_x"}}),
    )
    req = spot_ai.auto_jingle("upbeat instrumental bakery bed")
    assert req["status"] == "generating"
    assert req["task_id"] == "task_x"


def test_auto_jingle_falls_back_to_queue_without_key(spot_db, monkeypatch):
    monkeypatch.setattr(spot_ai, "_suno_config", lambda: ("https://api", None))
    req = spot_ai.auto_jingle("brief")
    assert req["status"] == "queued"       # manuel kuyruk
    assert req.get("task_id") is None


def test_poll_jingle_downloads_and_ready(spot_db, monkeypatch):
    monkeypatch.setattr(spot_ai, "_suno_config", lambda: ("https://api", "key"))
    monkeypatch.setattr(
        spot_ai.requests, "post",
        lambda *a, **k: _Resp({"data": {"taskId": "task_x"}}),
    )
    req = spot_ai.auto_jingle("bed music")

    audio_bytes = b"ID3fake-mp3-bytes"

    def fake_get(url, *a, **k):
        if "recordInfo" in url:
            return _Resp({"data": {
                "state": "success",
                "resultJson": {"data": [
                    {"audio_url": "https://cdn/x.mp3", "duration": 9.1}
                ]},
            }})
        r = _Resp({})
        r.content = audio_bytes
        return r

    monkeypatch.setattr(spot_ai.requests, "get", fake_get)
    done = spot_ai.poll_jingle(req["id"])
    assert done["status"] == "ready"
    assert done["duration"] == 9.1
    assert Path(done["file_path"]).read_bytes() == audio_bytes


def test_poll_jingle_failure(spot_db, monkeypatch):
    monkeypatch.setattr(spot_ai, "_suno_config", lambda: ("https://api", "key"))
    monkeypatch.setattr(
        spot_ai.requests, "post",
        lambda *a, **k: _Resp({"data": {"taskId": "t"}}),
    )
    req = spot_ai.auto_jingle("x")
    monkeypatch.setattr(
        spot_ai.requests, "get",
        lambda *a, **k: _Resp({"data": {"state": "failed", "failMsg": "kota doldu"}}),
    )
    done = spot_ai.poll_jingle(req["id"])
    assert done["status"] == "failed"
    assert "kota" in done["error"]


# --- mix_ad (gercek ffmpeg) --------------------------------------------------

def _write_tone_wav(path, seconds, rate=8000):
    import math
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(seconds * rate)):
            v = int(3000 * math.sin(2 * math.pi * 440 * i / rate))
            frames += int(v & 0xFFFF).to_bytes(2, "little", signed=False)
        w.writeframes(bytes(frames))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg gerekli")
def test_mix_ad_produces_voice_length_output(spot_db):
    voice_wav = spot_db / "voice.wav"
    jingle_wav = spot_db / "jingles" / "bed.wav"
    _write_tone_wav(voice_wav, 3.0)      # 3 sn voiceover
    _write_tone_wav(jingle_wav, 1.0)     # 1 sn jingle (donmeli)

    conn = spot_ai._connect()
    with conn:
        cur = conn.execute(
            "INSERT INTO spot_assets "
            "(created_at, kind, campaign_hint, text, file_path, voice_id, status) "
            "VALUES (?, 'voice', NULL, NULL, ?, NULL, 'ready')",
            (db.now_iso(), str(voice_wav)),
        )
        voice_id = int(cur.lastrowid)
    conn.close()

    result = spot_ai.mix_ad(voice_id, str(jingle_wav))
    out = Path(result["file_path"])
    assert out.is_file() and out.stat().st_size > 0
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(out)],
        capture_output=True, text=True,
    ).stdout.strip())
    assert 2.5 <= dur <= 3.6      # cikti ~ voiceover suresi (3 sn)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg gerekli")
def test_mix_ad_missing_voice_raises(spot_db):
    with pytest.raises(ValueError, match="Seslendirme bulunamadı"):
        spot_ai.mix_ad(9999, "nope.mp3")
