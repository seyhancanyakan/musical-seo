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

import os
import secrets
import sqlite3
from pathlib import Path

import requests

from marketplace import db
from musical_seo import envutil

envutil.load_env()  # ANTHROPIC_API_KEY / ELEVENLABS_API_KEY .env'den gelsin

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SPOTS_DIR = _DATA_DIR / "spots"
JINGLES_DIR = _DATA_DIR / "jingles"

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_MODEL = "claude-sonnet-4-6"
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
    product_name: str, details: str, seconds: int, tone: str, api_key: str
) -> str:
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
        _ANTHROPIC_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": _ANTHROPIC_MODEL,
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

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    notes = ""
    if api_key:
        text = _claude_script(product_name, details, seconds, tone, api_key)
        source = "claude"
    else:
        text, _target = _template_script(product_name, details, seconds)
        source = "template"
        notes = "ANTHROPIC_API_KEY tanımlı değil (.env); şablon metin üretildi"

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
