"""AI destekli reklam spotu uretimi: Claude metin + ElevenLabs seslendirme +
Suno jingle kuyrugu (Suno resmi API sunmadigi icin operator elle uretir).

Tablolar (marketplace.db):
    spot_assets:     uretilen metin/ses varliklari (kind: 'script'|'voice'|'jingle').
                     'voice' kayitlarinda file_path data/spots/{hex}.mp3'e isaret eder.
    jingle_requests: brief + stil ile acilan jingle talebi. Admin data/jingles/
                     altina koydugu dosyayi fulfill_jingle ile baglar.

Akis:
    generate_script  -> ANTHROPIC_API_KEY varsa Claude, yoksa TEMPLATE fallback
                         (network'suz, testlerde deterministik).
    synthesize_voice -> ELEVENLABS_API_KEY ZORUNLU (anahtar yoksa ValueError).
    list_voices      -> anahtar yoksa 3 sabit ornek ses (UI bozulmasin).
    request_jingle / list_jingle_requests / fulfill_jingle / jingle_library
                     -> Suno'nun resmi API'si yok; operator sarkiyi disaridan
                        uretir, data/jingles/ altina koyar, fulfill ile baglar.

Is kurali ihlalleri ValueError (aksanli Turkce) — router katmani 400'e cevirir.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import sqlite3
import subprocess
from pathlib import Path

import requests

from marketplace import db
from musical_seo import envutil

envutil.load_env()  # ANTHROPIC_API_KEY / ELEVENLABS_API_KEY .env'den gelsin

# --- Suno (APIPASS) jingle uretimi -------------------------------------------
# APIPASS_API_KEY + SUNO_API_URL tanimliysa jingle GERCEKTEN uretilir
# (createTask -> recordInfo polling -> mp3 indir). Anahtar yoksa request_jingle
# manuel kuyruk davranisinda kalir (operator elle uretir).
_DEFAULT_SUNO_URL = "https://api.apipass.dev"
# Bed muzik seviyesi: voiceover'in altinda kalsin (0..1).
_BED_VOLUME = 0.22
# Reklam sonunda muzik yumusak kapanis suresi (saniye).
_FADE_OUT_SECONDS = 2.0

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SPOTS_DIR = _DATA_DIR / "spots"
JINGLES_DIR = _DATA_DIR / "jingles"

# Metin uretimi Anthropic-uyumlu bir /v1/messages endpoint'ine gider. Varsayilan
# Anthropic; .env'de LLM_API_URL / LLM_MODEL / LLM_API_KEY tanimlanirsa saglayici
# degisir (orn. z.ai GLM — ayni istek/yanit formati, ayni x-api-key header'i).
_DEFAULT_LLM_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_LLM_MODEL = "claude-sonnet-4-6"


def _llm_config() -> tuple[str, str, str | None]:
    """(url, model, api_key) — env'den okunur; testte deterministik override."""
    url = os.environ.get("LLM_API_URL", _DEFAULT_LLM_URL)
    model = os.environ.get("LLM_MODEL", _DEFAULT_LLM_MODEL)
    key = os.environ.get("LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    return url, model, key
_ELEVEN_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_ELEVEN_VOICES_URL = "https://api.elevenlabs.io/v1/voices"
_REQUEST_TIMEOUT_SECONDS = 30
_WORDS_PER_SECOND = 2.5

_FALLBACK_VOICES = [
    {"voice_id": "sample-female-tr", "name": "Örnek Kadın Ses (TR)", "category": "örnek"},
    {"voice_id": "sample-male-tr", "name": "Örnek Erkek Ses (TR)", "category": "örnek"},
    {"voice_id": "sample-energetic", "name": "Örnek Enerjik Ses", "category": "örnek"},
]

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS spot_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        kind TEXT NOT NULL,
        campaign_hint TEXT,
        text TEXT,
        file_path TEXT,
        voice_id TEXT,
        status TEXT NOT NULL DEFAULT 'ready'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS jingle_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        brief TEXT NOT NULL,
        style TEXT,
        status TEXT NOT NULL DEFAULT 'queued',
        file_path TEXT
    );
    """,
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    # Suno otomatik uretim kolonlari (eski DB'lere sonradan eklenir).
    jcols = {r[1] for r in conn.execute("PRAGMA table_info(jingle_requests)")}
    if "task_id" not in jcols:
        conn.execute("ALTER TABLE jingle_requests ADD COLUMN task_id TEXT")
    if "audio_url" not in jcols:
        conn.execute("ALTER TABLE jingle_requests ADD COLUMN audio_url TEXT")
    if "duration" not in jcols:
        conn.execute("ALTER TABLE jingle_requests ADD COLUMN duration REAL")
    if "error" not in jcols:
        conn.execute("ALTER TABLE jingle_requests ADD COLUMN error TEXT")
    return conn


# --- Script uretimi (Claude + template fallback) ----------------------------

_TEMPLATE_POOL = [
    "{product} tam aradığınız gibi.",
    "{details}",
    "Şimdi denemenin tam zamanı, bu fırsatı kaçırmayın.",
    "Stoklar tükenmeden hemen sipariş verin.",
    "{product} ile fark yaratın, hayatınızı kolaylaştırın.",
    "Kalite ve uygun fiyat bir arada, tam size göre.",
    "Herkes {product} hakkında konuşuyor, sıra sizde.",
    "Kupon kodu {KUPON} ile ekstra indirim kazanın.",
    "Bugün alın, farkı hemen yarın görün.",
    "Aradığınız çözüm artık elinizin altında, hemen harekete geçin.",
]


def _target_word_count(seconds: int) -> int:
    return max(8, round(seconds * _WORDS_PER_SECOND))


def _template_script(product_name: str, details: str, seconds: int) -> tuple[str, int]:
    """Network'suz, deterministik yer tutucu metin. word_count == hedef kelime
    sayisi (test edilebilir olsun diye tam kesilir)."""
    target = _target_word_count(seconds)
    detail_text = details.strip() or f"{product_name} sizi bekliyor"
    filled = [
        s.format(product=product_name.strip(), details=detail_text, KUPON="{KUPON}")
        for s in _TEMPLATE_POOL
    ]
    words: list[str] = []
    i = 0
    while len(words) < target:
        words.extend(filled[i % len(filled)].split())
        i += 1
    words = words[:target]
    text = " ".join(words)
    if not text.endswith((".", "!", "?")):
        text += "."
    return text, target


def _claude_script(
    product_name: str, details: str, seconds: int, tone: str, api_key: str,
    url: str | None = None, model: str | None = None,
) -> str:
    url = url or _DEFAULT_LLM_URL
    model = model or _DEFAULT_LLM_MODEL
    target = _target_word_count(seconds)
    prompt = (
        "Türkçe bir radyo reklam spotu metni yaz.\n"
        f"Ürün: {product_name}\n"
        f"Detaylar: {details}\n"
        f"Ton: {tone}\n"
        f"Süre: yaklaşık {seconds} saniye (~{target} kelime).\n"
        "Metin doğal, akıcı ve harekete geçirici olsun (net bir CTA içersin). "
        "Metnin içinde tam olarak '{KUPON}' yer tutucusunu bir kupon kodu için kullan. "
        "Sadece spot metnini döndür, başka açıklama ekleme."
    )
    resp = requests.post(
        url,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    if resp.status_code != 200:
        raise ValueError(f"Claude API hatası ({resp.status_code}): {resp.text[:200]}")
    data = resp.json()
    blocks = data.get("content") or []
    text = "".join(
        b.get("text", "") for b in blocks if b.get("type") == "text"
    ).strip()
    if not text:
        raise ValueError("Claude API boş yanıt döndü")
    return text


def generate_script(
    product_name: str, details: str = "", seconds: int = 20, tone: str = "enerjik",
) -> dict:
    if not product_name.strip():
        raise ValueError("Ürün adı boş olamaz")
    if seconds <= 0:
        raise ValueError("Süre pozitif olmalı")

    url, model, api_key = _llm_config()
    notes = ""
    if api_key:
        text = _claude_script(product_name, details, seconds, tone, api_key, url, model)
        source = "claude"
    else:
        text, _target = _template_script(product_name, details, seconds)
        source = "template"
        notes = "LLM_API_KEY/ANTHROPIC_API_KEY tanımlı değil (.env); şablon metin üretildi"

    word_count = len(text.split())
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO spot_assets "
                "(created_at, kind, campaign_hint, text, file_path, voice_id, status) "
                "VALUES (?, 'script', ?, ?, NULL, NULL, 'ready')",
                (db.now_iso(), product_name.strip(), text),
            )
            asset_id = int(cur.lastrowid)
        return {
            "id": asset_id,
            "text": text,
            "word_count": word_count,
            "seconds": seconds,
            "source": source,
            "notes": notes,
        }
    finally:
        conn.close()


def get_asset(asset_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM spot_assets WHERE id = ?", (asset_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# --- Seslendirme (ElevenLabs) ------------------------------------------------

def synthesize_voice(text: str, voice_id: str = "default") -> dict:
    if not text.strip():
        raise ValueError("Seslendirilecek metin boş olamaz")
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("Seslendirme için ELEVENLABS_API_KEY gerekli (.env)")

    resp = requests.post(
        _ELEVEN_TTS_URL.format(voice_id=voice_id),
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    if resp.status_code != 200:
        raise ValueError(
            f"ElevenLabs API hatası ({resp.status_code}): {resp.text[:200]}"
        )

    SPOTS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = SPOTS_DIR / f"{secrets.token_hex(8)}.mp3"
    file_path.write_bytes(resp.content)

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO spot_assets "
                "(created_at, kind, campaign_hint, text, file_path, voice_id, status) "
                "VALUES (?, 'voice', NULL, ?, ?, ?, 'ready')",
                (db.now_iso(), text, str(file_path), voice_id),
            )
            asset_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM spot_assets WHERE id = ?", (asset_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_voices() -> list[dict]:
    """Anahtar yoksa (veya istek basarisiz olursa) 3 sabit ornek ses — UI bozulmasin."""
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        return list(_FALLBACK_VOICES)
    try:
        resp = requests.get(
            _ELEVEN_VOICES_URL,
            headers={"xi-api-key": api_key},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        voices = resp.json().get("voices", [])
        result = [
            {
                "voice_id": v.get("voice_id"),
                "name": v.get("name"),
                "category": v.get("category"),
            }
            for v in voices
        ]
        return result or list(_FALLBACK_VOICES)
    except (requests.RequestException, ValueError):
        return list(_FALLBACK_VOICES)


# --- Jingle kuyrugu (Suno resmi API sunmuyor -> operator elle uretir) -------

def request_jingle(brief: str, style: str = "") -> dict:
    if not brief.strip():
        raise ValueError("Brief boş olamaz")

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO jingle_requests (created_at, brief, style) "
                "VALUES (?, ?, ?)",
                (db.now_iso(), brief.strip(), style.strip() or None),
            )
            request_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM jingle_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def list_jingle_requests(status: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM jingle_requests", []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def fulfill_jingle(request_id: int, file_path: str) -> dict:
    """Admin: data/jingles/ altina konan dosyayi talebe baglar, status 'ready'.
    Guvenlik: sadece dosya adi (basename) kullanilir, dizin gezinmesi engellenir."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM jingle_requests WHERE id = ?", (request_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Jingle talebi bulunamadı: {request_id}")

        file_name = Path(file_path).name
        if not file_name:
            raise ValueError("Dosya adı boş olamaz")
        candidate = JINGLES_DIR / file_name
        if not candidate.is_file():
            raise ValueError(
                f"Jingle dosyası data/jingles altında bulunamadı: {file_name}"
            )

        with conn:
            conn.execute(
                "UPDATE jingle_requests SET status = 'ready', file_path = ? "
                "WHERE id = ?",
                (str(candidate), request_id),
            )
        updated = conn.execute(
            "SELECT * FROM jingle_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return dict(updated)
    finally:
        conn.close()


def jingle_library() -> list[dict]:
    """data/jingles/*.mp3 listesi (dizin yoksa bos liste)."""
    if not JINGLES_DIR.is_dir():
        return []
    return [
        {"file_name": f.name, "path": str(f)}
        for f in sorted(JINGLES_DIR.glob("*.mp3"))
    ]


# --- Suno otomatik jingle uretimi (senaryoya uygun muzik) --------------------

def _suno_config() -> tuple[str, str | None]:
    base = os.environ.get("SUNO_API_URL", _DEFAULT_SUNO_URL).rstrip("/")
    return base, os.environ.get("APIPASS_API_KEY")


def suggest_jingle_prompt(
    product_name: str, details: str = "", tone: str = "enerjik", seconds: int = 20,
) -> str:
    """Reklam senaryosundan Suno icin (Ingilizce) muzik-stili istemi uret.

    LLM anahtari varsa metnin ruh halini muzige cevirir; yoksa tondan basit
    heuristik. Jingle voiceover'in ALTINDA calacagi icin enstrumantal ve
    vokalsiz istenir.
    """
    url, model, api_key = _llm_config()
    if api_key:
        prompt = (
            "You are a music director creating a background music bed for a "
            "Turkish radio ad. Given the product and tone, write ONE short "
            "English Suno prompt (max 20 words) describing an INSTRUMENTAL, "
            "vocal-free jingle: genre, mood, tempo, instruments. It must sit "
            "UNDER a voiceover, so keep it non-distracting.\n"
            f"Product: {product_name}\nDetails: {details}\nTone: {tone}\n"
            f"Length: about {seconds} seconds.\n"
            "Return only the prompt text, nothing else."
        )
        try:
            resp = requests.post(
                url,
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": model, "max_tokens": 120,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            parts = resp.json().get("content", [])
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            if text.strip():
                return text.strip()
        except (requests.RequestException, ValueError, KeyError):
            pass  # heuristik fallback
    tone_map = {
        "enerjik": "upbeat energetic instrumental, bright, fast tempo",
        "samimi": "warm friendly acoustic instrumental, gentle, mid tempo",
        "kurumsal": "clean modern corporate instrumental, confident, steady",
        "eglenceli": "playful cheerful instrumental, bouncy, catchy",
    }
    base = tone_map.get(tone, "upbeat instrumental, catchy, radio-friendly")
    subject = product_name.strip() or "product"
    return f"{base}, background music bed for a {subject} radio ad, no vocals"


def _extract_audio_url(result_json) -> tuple[str | None, float | None]:
    """Suno recordInfo resultJson'undan ilk ses URL'i + suresini cikar.

    resultJson bazen JSON string, bazen dict gelir; data[] icindeki ilk
    tamamlanmis parcanin audio_url'i alinir. Sema degisirse ozyinelemeli
    URL aramaya duser (dayaniklilik)."""
    if isinstance(result_json, str):
        try:
            result_json = json.loads(result_json)
        except (json.JSONDecodeError, TypeError):
            return None, None
    if isinstance(result_json, dict):
        items = result_json.get("data")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("audio_url"):
                    dur = item.get("duration")
                    return item["audio_url"], (float(dur) if dur else None)

    # Ozyinelemeli fallback: audio uzantili ilk http url.
    found: list[str] = []

    def _walk(node) -> None:
        if found:
            return
        if isinstance(node, str):
            if node.startswith("http") and node.lower().split("?")[0].endswith(
                (".mp3", ".m4a", ".wav", ".flac", ".ogg")
            ):
                found.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(result_json)
    return (found[0] if found else None), None


def auto_jingle(brief: str, style: str = "", instrumental: bool = True,
                model_version: str = "V5") -> dict:
    """Suno (APIPASS) ile jingle uretimini BASLAT. Anahtar yoksa manuel
    kuyruga duser (request_jingle davranisi). Sonuc 'generating' statuyle
    doner; frontend poll_jingle ile bekler."""
    if not brief.strip():
        raise ValueError("Brief boş olamaz")
    base, api_key = _suno_config()
    if not api_key:
        # Anahtar yoksa manuel kuyruk — operator uretir.
        return request_jingle(brief, style)

    full_prompt = brief.strip()
    if style.strip():
        full_prompt = f"{full_prompt}, {style.strip()}"
    try:
        resp = requests.post(
            f"{base}/api/v1/jobs/createTask",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": "suno/generate", "input": {
                "model_version": model_version, "prompt": full_prompt,
                "customMode": False, "instrumental": instrumental}},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        task_id = resp.json().get("data", {}).get("taskId")
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise ValueError(f"Suno jingle isteği başarısız: {exc}")
    if not task_id:
        raise ValueError("Suno görev kimliği alınamadı")

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO jingle_requests "
                "(created_at, brief, style, status, task_id) "
                "VALUES (?, ?, ?, 'generating', ?)",
                (db.now_iso(), brief.strip(), style.strip() or None, task_id),
            )
            request_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM jingle_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def poll_jingle(request_id: int) -> dict:
    """Suno gorevinin durumunu sorgula; tamamlandiysa mp3'u indir + 'ready'.

    Idempotent: zaten 'ready'/'failed' ise oldugu gibi doner. 'generating'
    ise recordInfo cagrilir; success -> indir, fail -> 'failed'+error."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM jingle_requests WHERE id = ?", (request_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Jingle talebi bulunamadı: {request_id}")
        req = dict(row)
    finally:
        conn.close()

    if req["status"] in ("ready", "failed") or not req.get("task_id"):
        return req

    base, api_key = _suno_config()
    if not api_key:
        return req
    try:
        resp = requests.get(
            f"{base}/api/v1/jobs/recordInfo",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"taskId": req["task_id"]},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise ValueError(f"Suno durum sorgusu başarısız: {exc}")

    state = (data.get("state") or "").lower()
    if state in ("generating", "waiting", "pending", "running", ""):
        return req  # hala uretiliyor
    if state != "success":
        fail = data.get("failMsg") or "Suno üretimi başarısız"
        return _update_jingle(request_id, status="failed", error=fail)

    audio_url, duration = _extract_audio_url(data.get("resultJson"))
    if not audio_url:
        return _update_jingle(
            request_id, status="failed", error="Ses URL'i bulunamadı"
        )
    # mp3'u data/jingles/ altina indir.
    JINGLES_DIR.mkdir(parents=True, exist_ok=True)
    dest = JINGLES_DIR / f"suno-{request_id}-{secrets.token_hex(3)}.mp3"
    try:
        audio = requests.get(audio_url, timeout=_REQUEST_TIMEOUT_SECONDS * 3)
        audio.raise_for_status()
        dest.write_bytes(audio.content)
    except requests.RequestException as exc:
        return _update_jingle(request_id, status="failed", error=f"İndirme hatası: {exc}")
    return _update_jingle(
        request_id, status="ready", file_path=str(dest),
        audio_url=audio_url, duration=duration,
    )


def _update_jingle(request_id: int, **fields) -> dict:
    conn = _connect()
    try:
        cols = ", ".join(f"{k} = ?" for k in fields)
        with conn:
            conn.execute(
                f"UPDATE jingle_requests SET {cols} WHERE id = ?",
                (*fields.values(), request_id),
            )
        row = conn.execute(
            "SELECT * FROM jingle_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


# --- Reklam mix'i: voiceover + bed muzik (ffmpeg) ----------------------------

def _audio_duration(path: Path) -> float:
    """ffprobe ile ses suresi (saniye). ffprobe yoksa ffmpeg log'undan cikar."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        try:
            return float(out.stdout.strip())
        except ValueError:
            pass
    raise ValueError("Ses süresi okunamadı (ffprobe gerekli)")


def mix_ad(voice_asset_id: int, jingle_path: str,
           campaign_hint: str = "") -> dict:
    """Voiceover + bed muzigi TEK reklama karistir (ffmpeg).

    - Bed muzik voiceover'in altinda (_BED_VOLUME), kisaysa dongulenir,
      voiceover suresine kirpilir, sonda _FADE_OUT_SECONDS fade-out.
    - Cikti data/spots/mix-{hex}.mp3, spot_assets'e kind='mix' yazilir.
    Radyoya gonderilecek nihai spot budur.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("Reklam birleştirme için ffmpeg gerekli (.env/sunucu)")

    voice = get_asset(voice_asset_id)
    if voice is None or voice["kind"] != "voice" or not voice["file_path"]:
        raise ValueError(f"Seslendirme bulunamadı: {voice_asset_id}")
    voice_path = Path(voice["file_path"])
    if not voice_path.is_file():
        raise ValueError("Seslendirme dosyası diskte yok")
    bed_path = Path(jingle_path)
    if not bed_path.is_file():
        # sadece dosya adi verildiyse jingles klasorunde ara
        bed_path = JINGLES_DIR / Path(jingle_path).name
    if not bed_path.is_file():
        raise ValueError(f"Jingle dosyası bulunamadı: {jingle_path}")

    voice_dur = _audio_duration(voice_path)
    fade_start = max(0.0, voice_dur - _FADE_OUT_SECONDS)
    SPOTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SPOTS_DIR / f"mix-{secrets.token_hex(4)}.mp3"

    # -stream_loop -1: bed'i sonsuz dongule; amix duration=first -> voiceover
    # boyunda keser; normalize=0 -> voiceover tam sesli kalir; bed kisik+fade.
    filter_complex = (
        f"[1:a]volume={_BED_VOLUME},"
        f"afade=t=out:st={fade_start:.3f}:d={_FADE_OUT_SECONDS}[bed];"
        f"[0:a][bed]amix=inputs=2:duration=first:normalize=0[mix]"
    )
    cmd = [
        ffmpeg, "-y", "-i", str(voice_path),
        "-stream_loop", "-1", "-i", str(bed_path),
        "-filter_complex", filter_complex, "-map", "[mix]",
        "-ac", "2", "-ar", "44100", "-b:a", "192k", str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not out_path.is_file():
        raise ValueError(f"Reklam birleştirme başarısız: {proc.stderr[-300:]}")

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO spot_assets "
                "(created_at, kind, campaign_hint, text, file_path, voice_id, status) "
                "VALUES (?, 'mix', ?, NULL, ?, NULL, 'ready')",
                (db.now_iso(), campaign_hint or None, str(out_path)),
            )
            asset_id = int(cur.lastrowid)
    finally:
        conn.close()
    return {
        "id": asset_id, "kind": "mix", "file_path": str(out_path),
        "duration": round(voice_dur, 2),
    }
