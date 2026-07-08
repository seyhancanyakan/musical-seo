"""Cover/Derivative Avcisi — izinsiz cover/turev icerik tespiti.

Content ID (YouTube vb.) SADECE ayni ses kaydini (byte-benzeri parmak izini)
yakalar: farkli bir sanatcinin/kanalin ayni sarkiyi yeniden kaydettigi bir
cover, farkli soz duzenlemesi ya da tempo/tonalite degistirilmis bir turev
Content ID'nin gorus alanina hic girmez. Bu modul UC KATMANLI bir tespit
uygular:

    1) Ses profili katmani — musical_seo.audio ile cikarilan BPM/enerji/
       parlaklik profili, aday videolarin (varsa) profiliyle karsilastirilir
       (_audio_profile_distance). Tempo ikiye katlama/yarilama (harmonik
       iliski) toleransli ele alinir.
    2) Soz/baslik katmani — YouTube/lyrics kaynaklarindan gelen adaylarda
       baslik ya da soz eslesmesi bonus similarity katar (ses profili
       eksik/belirsiz oldugunda bile sinyal saglar).
    3) Dogrulama kuyrugu — esik ustu adaylar 'pending' olarak kaydedilir;
       sanatci review_candidate ile approved/rejected karari verir, onaylanan
       adaya lisans teklifi (generate_license_offer) ya da Content ID/telif
       itiraz basvuru metni (generate_claim_document) uretilir.

Tablolar (marketplace.db):
    cover_hunts:      acilan her av (sorgu + orijinal ses profili + rapor
                       token'i). status: open | watchdog.
    cover_candidates: esik ustu adaylar (source: youtube|lyrics|tiktok).
                       status: pending -> approved/rejected -> licensed/claimed.
    cover_licenses:   onaylanan adaylar icin uretilen lisans teklifi kaydi.

Kaynak toplayicilari (_collect_*) ag erisimi gerektirir; API anahtari yoksa
ya da istek basarisiz olursa SESSIZCE [] doner — av hicbir zaman tek bir
kaynak eksikligiyle cokmez. Ses analizi musical_seo.audio uzerinden gelir;
librosa kurulu degilse _original_audio_profile None doner (ses katmani
devre disi, soz/baslik katmani calismaya devam eder).

Is kurali ihlalleri ValueError (aksanli Turkce) — router katmani 400'e cevirir.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3

import requests

from marketplace import db, pricing
from musical_seo import audio

_TIMEOUT = 15
_DEEZER_SEARCH_URL = "https://api.deezer.com/search"
_YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_GENIUS_SEARCH_URL = "https://api.genius.com/search"

# Ses profili mesafesi bu esigin ALTINDAYSA "benzer" sayilir (0=ozdes).
AUDIO_DISTANCE_SIMILAR_MAX = 0.35
# similarity (1 - agirlikli mesafe + bonuslar) bu esigin USTUNDEYSE aday
# cover_candidates'a kaydedilir.
SIMILARITY_THRESHOLD = 0.65
HIGH_CONFIDENCE_THRESHOLD = 0.8

# BPM toleransi: tempo bu yuzdeden az farkliysa (harmonik/normal) ayni sayilir.
_BPM_TOLERANCE_PCT = 0.05
# Bu yuzde farktan sonra mesafe 1.0'a ulasir (asiri farkli tempo).
_BPM_MAX_DIFF_PCT = 0.5

# Kaba gelir tahmini: her yuksek/orta guvenli aday basina ortalama tahmini
# lisanssiz reklam geliri (gosterim amacli, gercek veri yok).
_REVENUE_PER_CANDIDATE_USD = 600

# Lisans tekliflerinde taban bedel (TRY); benzerlik arttikca yukselir.
_BASE_LICENSE_AMOUNT_TRY = 2500

WATCHDOG_INTERVAL_HOURS = 168  # haftalik surekli izleme

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS cover_hunts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        original_query TEXT NOT NULL,
        original_audio_profile TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        report_token TEXT NOT NULL UNIQUE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS cover_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        hunt_id INTEGER NOT NULL REFERENCES cover_hunts(id),
        source TEXT,
        url TEXT NOT NULL,
        title TEXT,
        channel TEXT,
        similarity_score REAL NOT NULL DEFAULT 0,
        match_reasons TEXT,
        status TEXT NOT NULL DEFAULT 'pending'
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_cover_candidates_hunt "
    "ON cover_candidates (hunt_id);",
    """
    CREATE TABLE IF NOT EXISTS cover_licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        candidate_id INTEGER NOT NULL REFERENCES cover_candidates(id),
        license_type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'offered'
    );
    """,
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


# --- Ses profili mesafesi (saf fonksiyon, network yok) ----------------------

def _bpm_distance(bpm_a: float | None, bpm_b: float | None) -> float:
    """BPM mesafesi 0..1. Tempo ikiye katlama/yarilama (harmonik iliski)
    toleransli: 120 BPM'lik bir cover 60 BPM olarak kaydedilmisse de
    ayni ritmik referans sayilir."""
    if not bpm_a or not bpm_b:
        return 0.5  # veri yok -> notr mesafe
    candidates = (bpm_b, bpm_b * 2, bpm_b / 2)
    best_diff_pct = min(abs(bpm_a - c) / bpm_a for c in candidates)
    if best_diff_pct <= _BPM_TOLERANCE_PCT:
        return 0.0
    span = _BPM_MAX_DIFF_PCT - _BPM_TOLERANCE_PCT
    return min((best_diff_pct - _BPM_TOLERANCE_PCT) / span, 1.0)


def _audio_profile_distance(profile_a: dict, profile_b: dict) -> float:
    """Iki ses profili arasi agirlikli mesafe 0..1 (0 = ozdes).

    BPM (%5 toleransli + harmonik), enerji, parlaklik agirlikli ortalama;
    her iki profilde de 'tonality' varsa ek agirlik olarak katilir. Saf
    fonksiyon: network/DB yok, dogrudan unit test edilir.
    """
    bpm_dist = _bpm_distance(profile_a.get("bpm"), profile_b.get("bpm"))
    energy_dist = abs((profile_a.get("energy") or 0.0) - (profile_b.get("energy") or 0.0))
    brightness_dist = abs(
        (profile_a.get("brightness") or 0.0) - (profile_b.get("brightness") or 0.0)
    )
    weights = [(0.45, bpm_dist), (0.3, energy_dist), (0.25, brightness_dist)]
    if profile_a.get("tonality") is not None and profile_b.get("tonality") is not None:
        tonality_dist = 0.0 if profile_a["tonality"] == profile_b["tonality"] else 1.0
        weights = [
            (0.35, bpm_dist), (0.25, energy_dist),
            (0.2, brightness_dist), (0.2, tonality_dist),
        ]
    total_weight = sum(w for w, _ in weights)
    dist = sum(w * d for w, d in weights) / total_weight
    return round(min(max(dist, 0.0), 1.0), 4)


# --- Orijinal ses profili (Deezer onizleme + musical_seo.audio) ------------

def _original_audio_profile(track_query: str) -> dict | None:
    """track_query icin Deezer'da 30 sn onizleme bulur + ses profili cikarir.

    librosa kurulu degilse, Deezer'da sonuc yoksa ya da herhangi bir adim
    basarisiz olursa None doner — av bu yuzden hicbir zaman cokmemeli.
    """
    if not audio.available() or not track_query:
        return None
    try:
        resp = requests.get(
            _DEEZER_SEARCH_URL, params={"q": track_query, "limit": 1}, timeout=_TIMEOUT
        )
        resp.raise_for_status()
        results = (resp.json() or {}).get("data") or []
        if not results:
            return None
        preview_url = results[0].get("preview")
        if not preview_url:
            return None
        profile = audio.analyze_url(preview_url)
        if profile is None:
            return None
        return {
            "bpm": profile.bpm,
            "energy": profile.energy,
            "brightness": profile.brightness,
            "instrumental_score": profile.instrumental_score,
        }
    except Exception:
        return None


# --- Aday toplayicilari (ag erisimi; her biri guarded) ----------------------

def _collect_youtube_candidates(track_query: str, max_results: int = 50) -> list[dict]:
    """YouTube Data API v3 arama. YOUTUBE_API_KEY yoksa ya da istek basarisiz
    olursa [] doner."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key or not track_query:
        return []
    try:
        resp = requests.get(
            _YOUTUBE_SEARCH_URL,
            params={
                "part": "snippet", "q": track_query, "type": "video",
                "maxResults": min(max_results, 50), "key": api_key,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        items = (resp.json() or {}).get("items") or []
    except Exception:
        return []

    candidates = []
    for item in items:
        video_id = (item.get("id") or {}).get("videoId")
        snippet = item.get("snippet") or {}
        if not video_id:
            continue
        candidates.append({
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": snippet.get("title") or "",
            "channel": snippet.get("channelTitle") or "",
            "source": "youtube",
        })
    return candidates


def _collect_lyrics_candidates(track_query: str) -> list[dict]:
    """Soz/baslik tabanli aday tarama (Genius benzeri kaynak). Bu kaynaktan
    gelen adaylar zaten baslik/soz eslesmesi tasidigi icin title_match=True
    ile isaretlenir. GENIUS_API_KEY yoksa ya da istek basarisiz olursa []
    doner."""
    api_key = os.environ.get("GENIUS_API_KEY")
    if not api_key or not track_query:
        return []
    try:
        resp = requests.get(
            _GENIUS_SEARCH_URL, params={"q": track_query},
            headers={"Authorization": f"Bearer {api_key}"}, timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        hits = ((resp.json() or {}).get("response") or {}).get("hits") or []
    except Exception:
        return []

    candidates = []
    for hit in hits:
        result = hit.get("result") or {}
        url = result.get("url")
        if not url:
            continue
        candidates.append({
            "url": url,
            "title": result.get("full_title") or result.get("title") or "",
            "channel": (result.get("primary_artist") or {}).get("name") or "",
            "source": "lyrics",
            "title_match": True,
        })
    return candidates


def _collect_tiktok_candidates(track_query: str) -> list[dict]:
    """TikTok genel arama icin resmi/kamuya acik bir API sunmuyor — bu asama
    her zaman [] doner (sonraki adimda partner API/scraping eklenebilir)."""
    return []


# --- Skorlama + persist -----------------------------------------------------

def score_candidates(
    original_profile: dict | None, candidates: list[dict],
    hunt_id: int | None = None,
) -> list[dict]:
    """Adaylari orijinal profile karsi skorlar.

    similarity = 1 - ses profili mesafesi (ikisi de mevcutsa) + soz/baslik
    bonuslari (title_match/lyric_match bayraklari). hunt_id verilirse
    SIMILARITY_THRESHOLD ustundeki adaylar cover_candidates'a 'pending'
    olarak kaydedilir (run_cover_hunt bu sekilde cagirir; standalone
    kullanimda hunt_id=None ile sadece skorlama yapilir, DB'ye yazilmaz).
    """
    scored: list[dict] = []
    for cand in candidates:
        reasons: list[str] = []
        similarity = 0.0
        cand_profile = cand.get("audio_profile")
        if original_profile and cand_profile:
            distance = _audio_profile_distance(original_profile, cand_profile)
            similarity = 1.0 - distance
            if distance < AUDIO_DISTANCE_SIMILAR_MAX:
                reasons.append("ses profili çok yakın (BPM/enerji/parlaklık)")
        if cand.get("title_match"):
            similarity = min(1.0, similarity + 0.15)
            reasons.append("başlık/söz eşleşmesi")
        if cand.get("lyric_match"):
            similarity = min(1.0, similarity + 0.2)
            reasons.append("söz benzerliği tespit edildi")
        if not cand_profile and not original_profile and reasons:
            # Ses sinyali hic yok — sadece metin bonuslari var; makul bir
            # taban belirle ki bariz baslik/soz eslesmesi kaybolmasin.
            similarity = max(similarity, 0.5)
        similarity = round(max(0.0, min(1.0, similarity)), 4)

        scored.append({
            "url": cand.get("url"),
            "title": cand.get("title"),
            "channel": cand.get("channel") or cand.get("source") or "",
            "source": cand.get("source") or "",
            "similarity": similarity,
            "match_reasons": reasons,
        })

    scored.sort(key=lambda c: c["similarity"], reverse=True)

    if hunt_id is not None:
        conn = _connect()
        try:
            with conn:
                for item in scored:
                    if item["similarity"] < SIMILARITY_THRESHOLD:
                        continue
                    conn.execute(
                        """
                        INSERT INTO cover_candidates
                            (created_at, hunt_id, source, url, title, channel,
                             similarity_score, match_reasons, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                        """,
                        (db.now_iso(), hunt_id, item["source"], item["url"],
                         item["title"], item["channel"], item["similarity"],
                         json.dumps(item["match_reasons"], ensure_ascii=False)),
                    )
        finally:
            conn.close()

    return scored


def _format_usd(amount: int) -> str:
    """Kaba tahmin gosterimi: bin ayraci nokta ('$1.200')."""
    return f"${amount:,}".replace(",", ".")


def _estimate_unlicensed_revenue(candidate_count: int) -> str:
    return _format_usd(candidate_count * _REVENUE_PER_CANDIDATE_USD)


# --- Av (hunt) ---------------------------------------------------------------

def run_cover_hunt(user_id: int, track_query: str) -> dict:
    """Tek seferlik av: orijinal ses profili + 3 kaynaktan aday toplama +
    skorlama + esik ustu adaylarin kalici kaydi. Hicbir kaynak/analiz adimi
    (audio kutuphanesi eksik, ag hatasi vb.) avin tamamini durdurmaz."""
    if not track_query or not track_query.strip():
        raise ValueError("Şarkı/sanatçı sorgusu boş olamaz")
    track_query = track_query.strip()

    original_profile = _original_audio_profile(track_query)

    raw_candidates: list[dict] = []
    for collector in (
        _collect_youtube_candidates, _collect_lyrics_candidates,
        _collect_tiktok_candidates,
    ):
        try:
            raw_candidates.extend(collector(track_query))
        except Exception:
            continue  # tek kaynagin hatasi avi durdurmasin

    seen_urls: set[str] = set()
    deduped: list[dict] = []
    for cand in raw_candidates:
        url = cand.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(cand)

    report_token = f"HUNT-{secrets.token_hex(3).upper()}"
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO cover_hunts
                    (created_at, user_id, original_query, original_audio_profile,
                     status, report_token)
                VALUES (?, ?, ?, ?, 'open', ?)
                """,
                (db.now_iso(), user_id, track_query,
                 json.dumps(original_profile) if original_profile else None,
                 report_token),
            )
            hunt_id = int(cur.lastrowid)
    finally:
        conn.close()

    scored = score_candidates(original_profile, deduped, hunt_id=hunt_id)
    persisted = [c for c in scored if c["similarity"] >= SIMILARITY_THRESHOLD]
    high_confidence = sum(
        1 for c in persisted if c["similarity"] >= HIGH_CONFIDENCE_THRESHOLD
    )
    medium_confidence = len(persisted) - high_confidence

    return {
        "hunt_id": hunt_id,
        "report_token": report_token,
        "original_query": track_query,
        "candidates_found": len(persisted),
        "high_confidence": high_confidence,
        "medium_confidence": medium_confidence,
        "estimated_unlicensed_revenue": _estimate_unlicensed_revenue(len(persisted)),
        "candidates": persisted,
    }


def _parse_match_reasons(raw: dict) -> dict:
    if raw.get("match_reasons"):
        try:
            raw["match_reasons"] = json.loads(raw["match_reasons"])
        except (TypeError, ValueError):
            pass
    return raw


def get_report(token: str) -> dict | None:
    """report_token ile av + tum adaylari doner. Bulunamazsa None (404 API
    katmaninda)."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM cover_hunts WHERE report_token = ?", (token,)
        ).fetchone()
        if row is None:
            return None
        hunt = dict(row)
        candidates = [
            _parse_match_reasons(dict(r)) for r in conn.execute(
                "SELECT * FROM cover_candidates WHERE hunt_id = ? "
                "ORDER BY similarity_score DESC",
                (hunt["id"],),
            ).fetchall()
        ]
    finally:
        conn.close()

    if hunt.get("original_audio_profile"):
        try:
            hunt["original_audio_profile"] = json.loads(hunt["original_audio_profile"])
        except (TypeError, ValueError):
            pass
    hunt["candidates"] = candidates
    return hunt


def candidates_for(hunt_id: int, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM cover_candidates WHERE hunt_id = ?"
    params: list = [hunt_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY similarity_score DESC"
    conn = _connect()
    try:
        rows = [_parse_match_reasons(dict(r)) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
    return rows


# --- Dogrulama kuyrugu (review) + lisans/telif itirazi ----------------------

def _get_candidate(candidate_id: int) -> dict:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM cover_candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"Aday bulunamadı: {candidate_id}")
    return dict(row)


def _license_amount_for(candidate: dict) -> int:
    """Benzerlik ne kadar yuksekse lisans bedeli o kadar yuksek — daha net
    kanit daha guclu pazarlik pozisyonu demek (gosterim amacli taban bedel)."""
    similarity = candidate.get("similarity_score") or 0.0
    return round(_BASE_LICENSE_AMOUNT_TRY * (0.5 + similarity))


def review_candidate(user_id: int, candidate_id: int, verdict: str) -> dict:
    """Sanatci (av sahibi) adaya karar verir: approved/rejected.

    Onaylananda bir sonraki adim lisans teklifidir (generate_license_offer
    dedicated endpoint'i ile uretilir); burada sadece onizleme tutari doner.
    """
    if verdict not in ("approved", "rejected"):
        raise ValueError(f"Geçersiz karar: {verdict}")

    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT cc.*, ch.user_id AS hunt_user_id
            FROM cover_candidates cc
            JOIN cover_hunts ch ON ch.id = cc.hunt_id
            WHERE cc.id = ?
            """,
            (candidate_id,),
        ).fetchone()
        if row is None or row["hunt_user_id"] != user_id:
            raise ValueError(f"Aday bulunamadı: {candidate_id}")
        candidate = dict(row)
        with conn:
            conn.execute(
                "UPDATE cover_candidates SET status = ? WHERE id = ?",
                (verdict, candidate_id),
            )
    finally:
        conn.close()

    result = {
        "candidate_id": candidate_id, "verdict": verdict,
        "next_action": "license_offer" if verdict == "approved" else "none",
    }
    if verdict == "approved":
        result["license_amount"] = _license_amount_for(candidate)
    return result


def generate_license_offer(candidate_id: int) -> dict:
    """Onaylanmis aday icin lisans teklifi uretir + kaydeder + adayi
    'licensed' isaretler. Basit tutar hesabi (syncmarket ilan bazli fiyatlama
    kullandigi icin genel bir fiyatlandirma yardimcisi sunmuyor)."""
    candidate = _get_candidate(candidate_id)
    amount = _license_amount_for(candidate)
    commission = round(amount * pricing.COVER_LICENSE_COMMISSION)
    offer = {
        "candidate_id": candidate_id,
        "license_type": "sync_cover_license",
        "amount": amount,
        "commission": commission,
        "terms": (
            f"Bu içerik lisanslandığında orijinal eser sahibine {amount} TRY "
            f"(MüzikSEO komisyonu: {commission} TRY) ödenir. Lisans geçmişe "
            "dönük kullanımı ve ileriye dönük 1 yıllık kullanım hakkını kapsar."
        ),
        "message_template": (
            f"Merhaba, \"{candidate.get('title') or ''}\" adlı içeriğinizde "
            "kullanılan müziğin telif sahibi adına yazıyoruz. İçeriği "
            f"kaldırmak yerine {amount} TRY karşılığında resmi kullanım "
            "lisansı sunuyoruz. Content ID uyuşmazlığından kaçınmak için "
            "7 gün içinde yanıt bekliyoruz."
        ),
    }
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO cover_licenses
                    (created_at, candidate_id, license_type, amount, status)
                VALUES (?, ?, ?, ?, 'offered')
                """,
                (db.now_iso(), candidate_id, offer["license_type"], amount),
            )
            conn.execute(
                "UPDATE cover_candidates SET status = 'licensed' WHERE id = ?",
                (candidate_id,),
            )
    finally:
        conn.close()
    return offer


def generate_claim_document(candidate_id: int) -> dict:
    """Content ID / telif itirazi basvurusu icin talimat metni + referans
    numaralari (ISRC/ISWC gercek kayit sistemine baglanana kadar goruntuludur)."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT cc.*, ch.original_query, ch.report_token
            FROM cover_candidates cc
            JOIN cover_hunts ch ON ch.id = cc.hunt_id
            WHERE cc.id = ?
            """,
            (candidate_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"Aday bulunamadı: {candidate_id}")
    candidate = dict(row)

    isrc_ref = f"ISRC-REF-{candidate_id:06d}"
    iswc_ref = f"ISWC-REF-{candidate_id:06d}"
    instructions = (
        "1) Platformun telif hakkı ihlali bildirim formunu aç (YouTube: "
        "'Copyright takedown' / Content ID uyuşmazlığı itiraz formu).\n"
        "2) Orijinal eser kaydı olarak aşağıdaki referans numaralarını ve "
        f"'{candidate.get('original_query') or ''}' sorgusuyla bulunan eseri belirt.\n"
        f"3) İçerik URL'sini ekle: {candidate.get('url') or ''}\n"
        "4) Talep türünü seç: 'Unauthorized derivative/cover' ve kanıt olarak "
        f"bu av raporunu ekle (rapor no: {candidate.get('report_token') or ''}).\n"
        "5) Platform genellikle 7-14 iş günü içinde yanıt verir; itiraz "
        "gelirse MüzikSEO destek ekibine ilet."
    )
    return {"instructions": instructions, "isrc_ref": isrc_ref, "iswc_ref": iswc_ref}


def enable_watchdog(user_id: int, track_query: str) -> dict:
    """Surekli izleme niyetini kaydeder (cover_hunts'a status='watchdog'
    satiri olarak). Gercek periyodik tarama sonraki asamada cron'a baglanir;
    burada sadece niyet + interval bilgisi doner."""
    if not track_query or not track_query.strip():
        raise ValueError("Şarkı/sanatçı sorgusu boş olamaz")
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO cover_hunts
                    (created_at, user_id, original_query, original_audio_profile,
                     status, report_token)
                VALUES (?, ?, ?, NULL, 'watchdog', ?)
                """,
                (db.now_iso(), user_id, track_query.strip(),
                 f"HUNT-{secrets.token_hex(3).upper()}"),
            )
    finally:
        conn.close()
    return {"ok": True, "interval_hours": WATCHDOG_INTERVAL_HOURS}
