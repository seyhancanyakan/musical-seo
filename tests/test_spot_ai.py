"""AI spot uretimi testleri: sablon fallback (anahtar yok), Claude anahtari
varken kullanimi, kelime sayisi/sure orani, ElevenLabs anahtar zorunlulugu +
monkeypatch'li mp3 yazimi, ses listesi fallback'i, jingle kuyruk + fulfill
akisi. Network YOK — requests.post/get spot_ai modulu icinde monkeypatch'lenir.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from marketplace import db, spot_ai


@pytest.fixture()
def spot_env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")
    monkeypatch.setattr(spot_ai, "SPOTS_DIR", tmp_path / "spots")
    monkeypatch.setattr(spot_ai, "JINGLES_DIR", tmp_path / "jingles")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)


# --- generate_script: sablon fallback ---------------------------------------

def test_template_fallback_when_no_anthropic_key(spot_env):
    result = spot_ai.generate_script(
        "Kahve Dükkanı", "Taze kavrulmuş çekirdek kahve", seconds=20,
    )
    assert result["source"] == "template"
    assert "ANTHROPIC_API_KEY" in result["notes"]
    assert "{KUPON}" in result["text"]
    assert result["id"] > 0


def test_empty_product_name_raises(spot_env):
    with pytest.raises(ValueError, match="Ürün adı"):
        spot_ai.generate_script("   ", "detay", seconds=20)


def test_non_positive_seconds_raises(spot_env):
    with pytest.raises(ValueError, match="Süre"):
        spot_ai.generate_script("Ürün", "detay", seconds=0)


@pytest.mark.parametrize("seconds", [10, 20, 30, 60])
def test_word_count_matches_seconds_ratio(spot_env, seconds):
    result = spot_ai.generate_script("Ürün", "Kısa detay metni", seconds=seconds)
    target = max(8, round(seconds * spot_ai._WORDS_PER_SECOND))
    assert result["word_count"] == target
    assert result["seconds"] == seconds


# --- generate_script: Claude anahtari varken ---------------------------------

def test_generate_script_uses_claude_when_key_present(spot_env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class _FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return {
                "content": [
                    {"type": "text", "text": "Claude tarafından üretilen spot metni {KUPON}."}
                ]
            }

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResp()

    monkeypatch.setattr(spot_ai.requests, "post", fake_post)

    result = spot_ai.generate_script("Ürün", "Detay", seconds=15)
    assert result["source"] == "claude"
    assert result["notes"] == ""
    assert "Claude tarafından" in result["text"]
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["json"]["model"] == spot_ai._ANTHROPIC_MODEL


def test_generate_script_claude_error_status_raises(spot_env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class _FakeResp:
        status_code = 401
        text = "unauthorized"

        def json(self):
            return {}

    monkeypatch.setattr(spot_ai.requests, "post", lambda *a, **k: _FakeResp())

    with pytest.raises(ValueError, match="Claude API hatası"):
        spot_ai.generate_script("Ürün", "Detay", seconds=15)


# --- synthesize_voice ---------------------------------------------------------

def test_synthesize_voice_requires_key(spot_env):
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        spot_ai.synthesize_voice("Merhaba dünya")


def test_synthesize_voice_requires_nonempty_text(spot_env, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    with pytest.raises(ValueError, match="boş olamaz"):
        spot_ai.synthesize_voice("   ")


def test_synthesize_voice_writes_mp3_and_asset(spot_env, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    class _FakeResp:
        status_code = 200
        content = b"FAKE-MP3-BYTES"
        text = ""

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResp()

    monkeypatch.setattr(spot_ai.requests, "post", fake_post)

    asset = spot_ai.synthesize_voice("Merhaba, bu bir test spotu.", voice_id="voice-123")
    assert asset["kind"] == "voice"
    assert asset["voice_id"] == "voice-123"
    assert "voice-123" in captured["url"]
    assert captured["headers"]["xi-api-key"] == "test-key"

    path = Path(asset["file_path"])
    assert path.is_file()
    assert path.read_bytes() == b"FAKE-MP3-BYTES"

    fetched = spot_ai.get_asset(asset["id"])
    assert fetched is not None
    assert fetched["file_path"] == asset["file_path"]


def test_synthesize_voice_error_status_raises(spot_env, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    class _FakeResp:
        status_code = 500
        content = b""
        text = "server error"

    monkeypatch.setattr(spot_ai.requests, "post", lambda *a, **k: _FakeResp())

    with pytest.raises(ValueError, match="ElevenLabs API hatası"):
        spot_ai.synthesize_voice("Merhaba dünya")


# --- list_voices --------------------------------------------------------------

def test_list_voices_fallback_without_key(spot_env):
    voices = spot_ai.list_voices()
    assert len(voices) == 3
    assert all("voice_id" in v and "name" in v for v in voices)


def test_list_voices_uses_api_when_key_present(spot_env, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"voices": [{"voice_id": "v1", "name": "Ses Bir", "category": "premade"}]}

    monkeypatch.setattr(spot_ai.requests, "get", lambda *a, **k: _FakeResp())

    voices = spot_ai.list_voices()
    assert voices == [{"voice_id": "v1", "name": "Ses Bir", "category": "premade"}]


def test_list_voices_falls_back_on_request_error(spot_env, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    def _raise(*a, **k):
        raise spot_ai.requests.RequestException("boom")

    monkeypatch.setattr(spot_ai.requests, "get", _raise)

    voices = spot_ai.list_voices()
    assert len(voices) == 3


# --- Jingle kuyrugu -----------------------------------------------------------

def test_request_jingle_requires_brief(spot_env):
    with pytest.raises(ValueError, match="Brief"):
        spot_ai.request_jingle("   ")


def test_jingle_queue_and_fulfill_flow(spot_env):
    req = spot_ai.request_jingle("30 saniyelik enerjik kahve reklamı jingle'ı", style="pop")
    assert req["status"] == "queued"

    pending = spot_ai.list_jingle_requests(status="queued")
    assert len(pending) == 1
    assert pending[0]["id"] == req["id"]

    spot_ai.JINGLES_DIR.mkdir(parents=True, exist_ok=True)
    (spot_ai.JINGLES_DIR / "kahve-jingle.mp3").write_bytes(b"FAKE-JINGLE")

    fulfilled = spot_ai.fulfill_jingle(req["id"], "kahve-jingle.mp3")
    assert fulfilled["status"] == "ready"
    assert fulfilled["file_path"].endswith("kahve-jingle.mp3")

    ready = spot_ai.list_jingle_requests(status="ready")
    assert len(ready) == 1

    library = spot_ai.jingle_library()
    assert len(library) == 1
    assert library[0]["file_name"] == "kahve-jingle.mp3"


def test_fulfill_jingle_missing_file_raises(spot_env):
    req = spot_ai.request_jingle("brief metni", style="rock")
    with pytest.raises(ValueError, match="bulunamadı"):
        spot_ai.fulfill_jingle(req["id"], "olmayan.mp3")


def test_fulfill_jingle_unknown_request_raises(spot_env):
    with pytest.raises(ValueError, match="Jingle talebi bulunamadı"):
        spot_ai.fulfill_jingle(999, "x.mp3")


def test_fulfill_jingle_path_traversal_uses_basename_only(spot_env):
    """file_path'te dizin bileseni verilse bile sadece dosya adi (basename)
    JINGLES_DIR icinde aranir — dizin gezinmesi mumkun degil."""
    req = spot_ai.request_jingle("brief metni", style="rock")
    with pytest.raises(ValueError, match="bulunamadı"):
        spot_ai.fulfill_jingle(req["id"], "../../etc/passwd")


def test_jingle_library_empty_when_dir_missing(spot_env):
    assert spot_ai.jingle_library() == []
