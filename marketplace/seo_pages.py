"""Programatik SEO sayfa uretim motoru.

`musical_seo.audit.run_audit()` ciktisini statik sayfalar icin cache'lenmis
veri modeline cevirir. Sayfa veri modelleri KENDI veritabaninda
(`data/seo_pages.db`) tutulur; Next.js ISR bu tabloları `marketplace/api_seo.py`
uzerinden okur.

Asamali uretim: `build_next_batch()` kuyruktan (build_queue) N kayit alir,
audit calistirir, basarili olanlari seo_*_pages tablolarina yazar. Boylece
gunde/ayda sinirli sayida yeni sayfa yayina girer (Google'a spam sinyali
vermemek icin).

Thin-content korumasi: audit skor uretemezse veya hicbir platformda kayit
bulunamazsa (`platform_count == 0`) sayfa YAZILMAZ, kuyruk satiri 'thin'
olarak isaretlenir (Google thin-content cezasindan kacis). Ayni korumali
mantik 'song' (Deezer'da hic bulunamadi / ISRC yok) ve 'playlist' (Spotify
erisilemedi / fraud analizi 'veri_yetersiz' + 0 veri kapsami) turleri icin de
gecerlidir — bkz. `_build_song_data` / `_build_playlist_data`.

Hata sozlesmesi: is kurali ihlalleri ValueError (aksanli Turkce) — API
katmani bunu 400'e cevirir. audit.run_audit / deezer / audio / fraud_forensics
ag erisimi gerektirebilir; bu modul asla onlarin yuzunden cokmez (try/except
ile 'failed' olarak isaretler).
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from marketplace import fraud_forensics, spotify_client
from musical_seo import audio, audit
from musical_seo.sources import deezer

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "seo_pages.db"

_CREATE_ARTIST_SQL = """
CREATE TABLE IF NOT EXISTS seo_artist_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    artist_name TEXT NOT NULL,
    isni TEXT,
    score REAL,
    platform_count INTEGER NOT NULL DEFAULT 0,
    findings_json TEXT NOT NULL DEFAULT '[]',
    data_json TEXT NOT NULL DEFAULT '{}',
    first_built_at TEXT NOT NULL,
    last_refreshed_at TEXT NOT NULL,
    indexed INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_SONG_SQL = """
CREATE TABLE IF NOT EXISTS seo_song_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isrc TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL,
    artist TEXT NOT NULL,
    title TEXT NOT NULL,
    score REAL,
    bpm REAL,
    song_key TEXT,
    data_json TEXT NOT NULL DEFAULT '{}',
    last_refreshed_at TEXT NOT NULL,
    indexed INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_PLAYLIST_SQL = """
CREATE TABLE IF NOT EXISTS seo_playlist_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_playlist_id TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    fraud_score REAL,
    verdict TEXT,
    data_json TEXT NOT NULL DEFAULT '{}',
    last_refreshed_at TEXT NOT NULL,
    indexed INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_QUEUE_SQL = """
CREATE TABLE IF NOT EXISTS build_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_type TEXT NOT NULL,
    ref TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
"""

# Ayni (page_type, ref) icin bekleyen (pending) ikinci bir kayit olusmasin —
# enqueue_* fonksiyonlari idempotent olsun diye kismi (partial) unique index.
_CREATE_QUEUE_PENDING_UNIQUE_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_build_queue_pending_unique
    ON build_queue (page_type, ref)
    WHERE status = 'pending';
"""

PAGE_TYPES = ("artist", "song", "playlist")
QUEUE_STATUSES = ("pending", "done", "thin", "failed")

# Gunluk arka plan build cron'unun (bkz. marketplace.api._seo_build_cron) her
# calistigi seferde isleyebilecegi AZAMI kayit sayisi — Google'a spam sinyali
# vermemek icin sayfa uretimi kasten yavas/kademeli tutulur.
# Gunluk uretim tavani. Sirali (eski) calismada gercek hiz ~15sn/sanatci (6
# platforma sirali audit) -> 24 saatte ~5-6K uretebiliyordu. build_next_batch
# artik SEO_BUILD_CONCURRENCY kadar es-zamanli audit calistiriyor (bkz. asagi),
# bu da gunluk tavani ~20-40K'a kadar cikarmaya izin verir. Tavan yine de
# operator karariyla kontrollu tutulur (spam sinyali riskine karsi):
SEO_DAILY_BUILD_CAP = 5000

# build_next_batch icinde audit.run_audit CAGRILARININ es-zamanli calisacagi
# maksimum thread sayisi. Audit suresinin buyuk kismi ag bekleme (6 kaynaga
# istek) oldugu icin orta duzeyde es-zamanlilik toplam throughput'u carpar.
# Cok yuksek bir deger, en siki oranli kaynagi (ozellikle MusicBrainz ~1
# istek/saniye) zorlayip throttling'e / IP banına yol acar. 8, guvenli bir
# orta nokta: rate-limit'e asiri yuklenmeden throughput'u belirgin artirir.
# En siki kaynak yine de es-zamanlilik altinda throttle olabilir — sorun
# degil, o audit'ler thin/failed'e duser ve sonraki cron calistirmasinda
# tekrar denenir (audit zaten ag hatasina karsi guvenlidir).
SEO_BUILD_CONCURRENCY = 8

_TURKISH_SLUG_MAP = {
    "ç": "c", "Ç": "c",
    "ğ": "g", "Ğ": "g",
    "ı": "i", "İ": "i",
    "ö": "o", "Ö": "o",
    "ş": "s", "Ş": "s",
    "ü": "u", "Ü": "u",
}
_SLUG_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_ARTIST_SQL)
    conn.execute(_CREATE_SONG_SQL)
    conn.execute(_CREATE_PLAYLIST_SQL)
    conn.execute(_CREATE_QUEUE_SQL)
    conn.execute(_CREATE_QUEUE_PENDING_UNIQUE_SQL)
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Saf yardimcilar ----------------------------------------------------------

def slugify(name: str) -> str:
    """Url-guvenli kucuk harf slug uretir. Turkce karakterler ASCII'ye
    cevrilir, bosluk/noktalama '-' olur, bas/son '-' kirpilir. Saf fonksiyon."""
    if not name or not name.strip():
        raise ValueError("Slug icin ad bos olamaz")
    text = name.strip()
    for src, dst in _TURKISH_SLUG_MAP.items():
        text = text.replace(src, dst)
    text = text.lower()
    text = _SLUG_NON_ALNUM_RE.sub("-", text).strip("-")
    if not text:
        raise ValueError(f"Gecerli bir slug uretilemedi: {name!r}")
    return text


# --- Kuyruk (build_queue) -----------------------------------------------------

def _enqueue(page_type: str, ref: str, priority: int = 0) -> dict:
    """Ortak idempotent kuyruga-ekleme mantigi (enqueue_artist/song/playlist
    tarafindan paylasilir). Ayni (page_type, ref) icin bekleyen (pending)
    kayit varsa yeni satir acmaz, mevcut olani doner (bkz. partial unique
    index `idx_build_queue_pending_unique`)."""
    now = _now_iso()
    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO build_queue "
                "(page_type, ref, priority, status, created_at) "
                "VALUES (?, ?, ?, 'pending', ?)",
                (page_type, ref, priority, now),
            )
            if cursor.rowcount:
                row = conn.execute(
                    "SELECT * FROM build_queue WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
            else:
                # Zaten bekleyen bir kayit var (UNIQUE ihlali yutuldu) — onu don.
                row = conn.execute(
                    "SELECT * FROM build_queue WHERE page_type = ? "
                    "AND ref = ? AND status = 'pending'",
                    (page_type, ref),
                ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else {}


def enqueue_artist(artist_name: str, isni: str | None = None, priority: int = 0) -> dict:
    """Sanatciyi uretim kuyruguna ekler. Ayni sanatci icin bekleyen (pending)
    kayit varsa yeni satir acmaz, mevcut olani doner (idempotent)."""
    if not artist_name or not artist_name.strip():
        raise ValueError("Sanatci adi bos olamaz")
    return _enqueue("artist", artist_name.strip(), priority)


def enqueue_song(query: str, isni: str | None = None, priority: int = 0) -> dict:
    """Sarkiyi uretim kuyruguna ekler. `query` "Sanatci - Sarki" formatinda
    (tercih edilir, cozumleme daha isabetli olur) veya ham bir arama metni
    olabilir — bkz. `_build_song_data` / `_split_song_query`. `isni` su an
    kullanilmiyor (ileride ISNI-tabanli sanatci eslesmesi icin ayrilmis
    parametre); ref olarak sadece `query` metni saklanir. Ayni sorgu icin
    bekleyen (pending) kayit varsa yeni satir acmaz (idempotent)."""
    if not query or not query.strip():
        raise ValueError("Sarki sorgusu bos olamaz")
    return _enqueue("song", query.strip(), priority)


def enqueue_playlist(playlist_url: str, priority: int = 0) -> dict:
    """Playlist'i uretim kuyruguna ekler (ref = playlist URL'i). Ayni URL
    icin bekleyen (pending) kayit varsa yeni satir acmaz (idempotent)."""
    if not playlist_url or not playlist_url.strip():
        raise ValueError("Playlist URL bos olamaz")
    return _enqueue("playlist", playlist_url.strip(), priority)


def _top_findings(findings: list) -> list[dict]:
    top: list[dict] = []
    for f in list(findings)[:3]:
        if hasattr(f, "severity"):
            top.append(
                {
                    "severity": getattr(f, "severity", None),
                    "category": getattr(f, "category", None),
                    "message": getattr(f, "message", None),
                    "action": getattr(f, "action", None),
                }
            )
        elif isinstance(f, dict):
            top.append(f)
    return top


def _result_to_data(result: Any) -> dict:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return dict(getattr(result, "__dict__", {}))


def _audit_one(page_type: str, ref: str) -> tuple[str, Any]:
    """Tek bir 'artist' kuyruk kaydi icin audit calistirir (ThreadPoolExecutor
    worker'i icinde). Asla istisna firlatmaz — audit.run_audit hatasi
    'failed' olarak donsun ki havuzdaki (pool) tek bir hata butun batch'i
    cokertmesin. Donus: (outcome, result) — outcome 'failed' ise result
    None'dir, aksi halde audit.run_audit ciktisidir."""
    if page_type != "artist":
        return ("failed", None)
    try:
        result = audit.run_audit(ref)
    except Exception:
        return ("failed", None)
    return ("audited", result)


# --- 'song' sayfa turu icin ag-yogun toplama ----------------------------------
# Deezer'in track detay uc noktasi 'preview' (30 sn onizleme) alani tasir ama
# musical_seo.sources.deezer.TrackInfo bunu tasimiyor (sadece web sayfasi
# linkini "url" olarak saklıyor) — bu yuzden burada, sadece bu amac icin,
# dogrudan /track/{id} uc noktasina ozel bir istek atilir.
_DEEZER_TRACK_URL = "https://api.deezer.com/track/{id}"
_DEEZER_TRACK_TIMEOUT = 15

# Ses profilinden (brightness + energy) TURETILEN kaba/deterministik tonalite
# etiketleri — GERCEK perde/chroma analizi DEGIL (musical_seo.audio boyle bir
# cikti saglamiyor). Bkz. `_heuristic_song_key`.
_SONG_KEY_LABELS = (
    "C Major", "G Major", "D Major", "A Major", "E Major", "F Major",
    "A Minor", "E Minor", "D Minor", "G Minor", "B Minor", "C Minor",
)


def _split_song_query(ref: str) -> tuple[str, str]:
    """"Sanatci - Sarki" formatini ayristirir (saf fonksiyon). " - " ayraci
    yoksa tum metin baslik/ham arama sorgusu kabul edilir (deezer.search'e
    gider), sanatci ipucu bos doner."""
    if " - " in ref:
        artist_part, _, title_part = ref.partition(" - ")
        return artist_part.strip(), title_part.strip()
    return "", ref.strip()


def _deezer_preview_url(deezer_track_id: Any) -> str | None:
    """Deezer parca ID'sinden 30 sn onizleme URL'ini ceker (audio.analyze_url
    girdisi). Ag hatasinda, bozuk JSON'da veya alan yoksa None doner —
    exception firlatmaz."""
    if deezer_track_id is None:
        return None
    try:
        resp = requests.get(
            _DEEZER_TRACK_URL.format(id=deezer_track_id), timeout=_DEEZER_TRACK_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict) or data.get("error"):
        return None
    preview = data.get("preview")
    return preview if isinstance(preview, str) and preview else None


def _heuristic_song_key(profile: Any) -> str:
    """AudioProfile'dan (brightness + energy) TURETILEN kaba/deterministik bir
    tonalite etiketi. GERCEK perde/chroma analizi DEGILDIR — sabit bir
    tonalite listesi uzerinde indeksleme yapar (ayni girdi -> ayni etiket).
    UI'da bir baslangic tahmini olarak sunulur, kesin muzik teorisi iddiasi
    tasimaz."""
    idx = int(round(profile.brightness * 5 + profile.energy * 6)) % len(_SONG_KEY_LABELS)
    return _SONG_KEY_LABELS[idx]


def _build_song_data(ref: str) -> tuple[str, dict | None]:
    """'song' kuyruk kaydi icin ag-yogun toplama (ThreadPoolExecutor worker'i
    icinde calisir, DB yazimi YAPMAZ). Deezer lookup/search ile parcayi
    cozer, 30 sn onizlemeden musical_seo.audio ile bpm/heuristic tonalite
    cikarir, musical_seo.audit.run_audit ile hafif bir SEO skoru dener. Asla
    exception firlatmaz.

    Donus (outcome, payload):
      'thin'   -> Deezer'da hic bulunamadi VEYA ISRC yok (kimliksiz sayfa
                  insa edilemez, thin-content riski)
      'failed' -> beklenmeyen hata (savunma amacli)
      'ready'  -> payload = {isrc, slug, artist, title, score, bpm,
                  song_key, data}; score/bpm/song_key None olabilir (audio/
                  audit basarisiz olduysa) — score None ise upsert_song_page
                  kendi thin-guard'ini uygular."""
    artist_hint, title_hint = _split_song_query(ref)
    try:
        track = (
            deezer.lookup(artist_hint, title_hint)
            if artist_hint and title_hint
            else deezer.search(ref)
        )
    except Exception:
        return ("failed", None)

    if track is None or not getattr(track, "found", False):
        return ("thin", None)

    isrc = track.isrc
    artist = track.artist or artist_hint
    title = track.title or title_hint or ref
    if not isrc or not artist or not title:
        return ("thin", None)

    try:
        slug = slugify(f"{artist}-{title}")
    except ValueError:
        return ("thin", None)

    bpm = None
    song_key = None
    profile = None
    try:
        preview_url = _deezer_preview_url((track.extra or {}).get("id"))
        if preview_url:
            profile = audio.analyze_url(preview_url)
        if profile is not None:
            bpm = profile.bpm
            song_key = _heuristic_song_key(profile)
    except Exception:
        bpm = song_key = profile = None

    score = None
    try:
        score = audit.run_audit(f"{artist} - {title}").score
    except Exception:
        score = None  # audit basarisiz -> skor yok say (thin-guard upsert_song_page'de)

    data = {
        "artist": artist,
        "title": title,
        "isrc": isrc,
        "album": track.album,
        "release_date": track.release_date,
        "deezer_url": track.url,
        "audio_profile": (
            {
                "bpm": profile.bpm,
                "energy": profile.energy,
                "brightness": profile.brightness,
                "instrumental_score": profile.instrumental_score,
            }
            if profile is not None
            else None
        ),
    }
    return (
        "ready",
        {
            "isrc": isrc, "slug": slug, "artist": artist, "title": title,
            "score": score, "bpm": bpm, "song_key": song_key, "data": data,
        },
    )


# --- 'playlist' sayfa turu icin ag-yogun toplama ------------------------------

def _build_playlist_data(ref: str) -> tuple[str, dict | None]:
    """'playlist' kuyruk kaydi icin ag-yogun toplama (ThreadPoolExecutor
    worker'i icinde calisir, DB yazimi YAPMAZ). marketplace.fraud_forensics
    .analyze_playlist (zaten guarded) cagirir. Asla exception firlatmaz.

    Donus (outcome, payload):
      'thin'   -> Spotify erisilemedi / analiz 'veri_yetersiz' verdict'i +
                  0 informatif sinyal dondurdu (guvenilir bir fraud sayfasi
                  insa edilemez, thin-content riski)
      'failed' -> beklenmeyen hata (savunma amacli)
      'ready'  -> payload = {platform_playlist_id, slug, title, fraud_score,
                  verdict, data}"""
    try:
        report = fraud_forensics.analyze_playlist(ref)
    except Exception:
        return ("failed", None)

    if not isinstance(report, dict):
        return ("failed", None)

    coverage = report.get("data_coverage") or {}
    verdict = report.get("verdict")
    if verdict == "veri_yetersiz" and coverage.get("informative_signals", 0) == 0:
        return ("thin", None)

    title = report.get("playlist_title") or ref
    try:
        slug = slugify(title)
    except ValueError:
        return ("thin", None)

    platform_playlist_id = spotify_client.parse_playlist_id(ref) or ref

    return (
        "ready",
        {
            "platform_playlist_id": platform_playlist_id,
            "slug": slug,
            "title": title,
            "fraud_score": report.get("total_risk_score"),
            "verdict": verdict,
            "data": report,
        },
    )


def _process_one(page_type: str, ref: str) -> tuple[str, Any]:
    """Tek bir kuyruk kaydi icin ag-yogun toplama isini page_type'a gore
    yonlendirir (ThreadPoolExecutor worker'i icinde calisir, DB yazimi
    YAPMAZ). Asla exception firlatmaz — bilinmeyen page_type veya alt
    fonksiyonlarin beklenmedik hatasi 'failed' olarak doner ki havuzdaki tek
    bir hata butun batch'i cokertmesin."""
    try:
        if page_type == "artist":
            return _audit_one(page_type, ref)
        if page_type == "song":
            return _build_song_data(ref)
        if page_type == "playlist":
            return _build_playlist_data(ref)
    except Exception:
        return ("failed", None)
    return ("failed", None)


_INDEXNOW_PREFIX = {"artist": "/artist/", "song": "/song/", "playlist": "/playlist/"}


def build_next_batch(limit: int = 100) -> dict:
    """Kuyruktan en fazla `limit` bekleyen kaydi PRIORITY sirasiyla
    (priority DESC, id ASC) alir. Ag-yogun toplama (audit/deezer/audio/
    fraud_forensics — page_type'a gore, bkz. `_process_one`)
    SEO_BUILD_CONCURRENCY kadar es-zamanli (ThreadPoolExecutor) calistirilir
    — surenin buyuk kismi ag bekleme oldugu icin bu, gunluk throughput'u
    sirali calismaya gore carpar (bkz. SEO_BUILD_CONCURRENCY yorumu).

    Yuksek oncelikli kayitlar YINE once islenir: secim SELECT sorgusuyla
    (priority DESC) yapilir ve DB yazimlari thread'lerin tamamlanma sirasina
    degil, orijinal kuyruk id'sine gore uygulanir — thread zamanlamasi
    sonucu etkilemez.

    DB yazimlari (queue durumu + sayfa upsert) es-zamanli toplama TAMAMEN
    bittikten SONRA, TEK bir sqlite baglantisi uzerinden sirali yapilir.
    SQLite tek yazarli (single-writer) oldugu icin coklu thread'den ayni anda
    yazmaya calismak 'database is locked' hatasina yol acardi.

    Uc page_type de desteklenir:
      'artist'   -> audit.run_audit; skor yok veya hicbir platformda
                    bulunamadiysa (platform_count == 0) 'thin'.
      'song'     -> Deezer lookup/search + audio + hafif audit skoru (bkz.
                    `_build_song_data`); Deezer'da bulunamadi/ISRC yok veya
                    upsert_song_page kendi thin-guard'ini (skor yok)
                    uygularsa 'thin'.
      'playlist' -> fraud_forensics.analyze_playlist (bkz.
                    `_build_playlist_data`); Spotify erisilemedi / analiz
                    'veri_yetersiz' + 0 veri kapsami donduyse 'thin'.
    Herhangi bir turde beklenmeyen bir hata (ag/cozumleme) firlatirsa o kayit
    'failed' olur; havuzdaki diger kayitlar etkilenmez (izole try/except)."""
    if limit <= 0:
        raise ValueError("limit pozitif bir sayi olmali")

    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM build_queue WHERE status = 'pending' "
            "ORDER BY priority DESC, id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        # Baglantiyi hemen kapatiyoruz: es-zamanli toplama asamasi boyunca
        # (network IO, saniyeler surebilir) acik bir sqlite baglantisi
        # tutmuyoruz.
        queue_items = [(row["id"], row["page_type"], row["ref"]) for row in rows]
    finally:
        conn.close()

    processed = len(queue_items)
    built = thin = failed = 0
    now = _now_iso()
    # Bu turda basariyla YAZILAN sayfalarin slug'lari, turune gore — asama 2
    # sonunda IndexNow'a bildirilecek (bkz. asagidaki hook + marketplace.indexnow).
    built_slugs: dict[str, list[str]] = {"artist": [], "song": [], "playlist": []}

    # --- Asama 1: toplamayi es-zamanli calistir (DB yazimi YOK) ----------------
    outcomes: dict[int, tuple[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=SEO_BUILD_CONCURRENCY) as executor:
        future_to_id = {
            executor.submit(_process_one, page_type, ref): queue_id
            for queue_id, page_type, ref in queue_items
        }
        for future in concurrent.futures.as_completed(future_to_id):
            queue_id = future_to_id[future]
            try:
                outcomes[queue_id] = future.result()
            except Exception:
                # _process_one zaten kendi icinde try/except ile sarili; buraya
                # normal kosullarda dusmez — yine de savunma amacli 'failed'.
                outcomes[queue_id] = ("failed", None)

    # --- Asama 2: TUM DB yazimlarini TEK baglanti + oncelik sirasinda uygula --
    conn = _connect()
    try:
        for queue_id, page_type, ref in queue_items:
            outcome, result = outcomes.get(queue_id, ("failed", None))

            if outcome == "failed":
                with conn:
                    conn.execute(
                        "UPDATE build_queue SET status = 'failed' WHERE id = ?",
                        (queue_id,),
                    )
                failed += 1
                continue

            if outcome == "thin":
                with conn:
                    conn.execute(
                        "UPDATE build_queue SET status = 'thin' WHERE id = ?",
                        (queue_id,),
                    )
                thin += 1
                continue

            if page_type == "artist":
                # outcome == "audited" -> result AuditResult benzeri bir nesne.
                sources = getattr(result, "sources", None) or []
                platform_count = sum(1 for s in sources if getattr(s, "found", False))
                score = getattr(result, "score", None)

                if score is None or platform_count == 0:
                    with conn:
                        conn.execute(
                            "UPDATE build_queue SET status = 'thin' WHERE id = ?",
                            (queue_id,),
                        )
                    thin += 1
                    continue

                resolved_artist = getattr(result, "resolved_artist", None) or ref
                slug = slugify(resolved_artist)
                findings_json = json.dumps(
                    _top_findings(getattr(result, "findings", []) or []), ensure_ascii=False
                )
                data_json = json.dumps(_result_to_data(result), ensure_ascii=False)

                existing = conn.execute(
                    "SELECT id FROM seo_artist_pages WHERE slug = ?", (slug,)
                ).fetchone()
                with conn:
                    if existing:
                        conn.execute(
                            """
                            UPDATE seo_artist_pages
                            SET artist_name = ?, score = ?, platform_count = ?,
                                findings_json = ?, data_json = ?, last_refreshed_at = ?
                            WHERE slug = ?
                            """,
                            (
                                resolved_artist, score, platform_count,
                                findings_json, data_json, now, slug,
                            ),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO seo_artist_pages (
                                slug, artist_name, isni, score, platform_count,
                                findings_json, data_json, first_built_at,
                                last_refreshed_at, indexed
                            ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, 0)
                            """,
                            (
                                slug, resolved_artist, score, platform_count,
                                findings_json, data_json, now, now,
                            ),
                        )
                    conn.execute(
                        "UPDATE build_queue SET status = 'done' WHERE id = ?",
                        (queue_id,),
                    )
                built += 1
                built_slugs["artist"].append(slug)
                continue

            if page_type == "song":
                # outcome == "ready" -> result payload'i _build_song_data'dan.
                upserted = upsert_song_page(
                    isrc=result["isrc"], slug=result["slug"], artist=result["artist"],
                    title=result["title"], score=result["score"], bpm=result["bpm"],
                    song_key=result["song_key"], data=result["data"],
                )
                with conn:
                    if upserted.get("skipped"):
                        conn.execute(
                            "UPDATE build_queue SET status = 'thin' WHERE id = ?",
                            (queue_id,),
                        )
                        thin += 1
                    else:
                        conn.execute(
                            "UPDATE build_queue SET status = 'done' WHERE id = ?",
                            (queue_id,),
                        )
                        built += 1
                        built_slugs["song"].append(result["slug"])
                continue

            if page_type == "playlist":
                # outcome == "ready" -> result payload'i _build_playlist_data'dan.
                upserted = upsert_playlist_page(
                    platform_playlist_id=result["platform_playlist_id"],
                    slug=result["slug"], title=result["title"],
                    fraud_score=result["fraud_score"], verdict=result["verdict"],
                    data=result["data"],
                )
                with conn:
                    if upserted.get("skipped"):
                        conn.execute(
                            "UPDATE build_queue SET status = 'thin' WHERE id = ?",
                            (queue_id,),
                        )
                        thin += 1
                    else:
                        conn.execute(
                            "UPDATE build_queue SET status = 'done' WHERE id = ?",
                            (queue_id,),
                        )
                        built += 1
                        built_slugs["playlist"].append(result["slug"])
                continue

            # Bilinmeyen page_type — savunma amacli (PAGE_TYPES disi bir deger
            # kuyruga hic girmemis olmali, ama burada asla cokme).
            with conn:
                conn.execute(
                    "UPDATE build_queue SET status = 'failed' WHERE id = ?",
                    (queue_id,),
                )
            failed += 1
    finally:
        conn.close()

    # --- Asama 3: yeni yazilan sayfalari IndexNow'a bildir (Bing/Yandex aninda
    # index — bkz. docs/PROGRAMATIK_SEO_WORKFLOW.md §10). Gec (lazy) import
    # dongusel bagimliliktan kacinmak icindir. Bu adim ASLA build sonucunu
    # etkilemez: indexnow modulunun kendisi zaten ag hatasina karsi guvenli
    # (guarded) ama yine de savunma amacli try/except ile sariyoruz — beklenmedik
    # bir indexnow hatasi build_next_batch'in donus degerini asla bozmasin.
    if any(built_slugs.values()):
        try:
            from marketplace import indexnow
            for ptype, slugs in built_slugs.items():
                if slugs:
                    indexnow.submit_slugs(slugs, path_prefix=_INDEXNOW_PREFIX[ptype])
        except Exception:
            pass

    return {"processed": processed, "built": built, "thin": thin, "failed": failed}


def queue_stats() -> dict:
    """Kuyrugun durum bazinda ozeti (operator gozlemi icin, ornegin
    /seo/queue-stats admin uc noktasi). Her status icin sayim doner; hic
    kaydi olmayan status 0 ile gorunur."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM build_queue GROUP BY status"
        ).fetchall()
    finally:
        conn.close()
    counts = {status: 0 for status in QUEUE_STATUSES}
    for row in rows:
        counts[row["status"]] = row["c"]
    return counts


# --- Operator gorunumu: kuyruk + uretilmis sayfa (admin dashboard) ------------

def _list_pages_where(
    page_type: str, status: str | None, search: str | None
) -> tuple[str, list[Any]]:
    """list_pages/list_pages_count arasinda paylasilan WHERE + parametre
    olusturucu (DRY). page_type/status gecerliligi cagiran tarafindan
    dogrulanmis olmali (bu fonksiyon sadece SQL parcasi kurar)."""
    clauses = ["page_type = ?"]
    params: list[Any] = [page_type]
    if status:
        clauses.append("status = ?")
        params.append(status)
    if search and search.strip():
        clauses.append("ref LIKE ?")
        params.append(f"%{search.strip()}%")
    return " AND ".join(clauses), params


def _lookup_built_page(conn: sqlite3.Connection, page_type: str, ref: str) -> dict | None:
    """Bir build_queue kaydinin (page_type, ref) karsiligi olarak ZATEN
    uretilmis (seo_*_pages) bir sayfa var mi kontrol eder. Esleme slug/kimlik
    uzerinden yapilir — build_next_batch'in o sayfa turu icin URETTIGI slug/
    kimlik ile AYNI hesaplama burada tekrarlanir:
      'artist'   -> slug = slugify(ref) (build_next_batch resolved_artist
                    kullanir ama enqueue_artist ref=artist_name oldugu ve
                    audit genelde ayni adi cozdugu icin pratikte eslesir;
                    coz(ulem)eme farkliysa satir 'built degil' gorunur —
                    bir sonraki build ciktisinda ref guncellenene kadar
                    normal, kritik degil).
      'song'     -> slug = slugify(f"{artist}-{title}") (_split_song_query
                    ile ayni ayristirma); artist/title ayristirilamazsa None.
      'playlist' -> platform_playlist_id = spotify_client.parse_playlist_id(ref)
                    veya ref'in kendisi (build_next_batch ile ayni fallback).

    Donen dict'teki 'slug' alani her zaman o sayfa turunun PUBLIC route
    parametresidir (web/app/{artist,song,playlist} klasor yapisiyla birebir):
    artist icin gercek slug, song icin ISRC ([isrc] route), playlist icin
    platform_playlist_id ([pid] route) — cagiran taraf (list_pages / admin
    dashboard) tek bir alan adiyla dogru linki kurabilsin diye.

    Bulunamazsa veya slug uretilemezse (ValueError) None doner — asla firlatmaz."""
    try:
        if page_type == "artist":
            slug = slugify(ref)
            row = conn.execute(
                "SELECT slug, score, platform_count, last_refreshed_at "
                "FROM seo_artist_pages WHERE slug = ?",
                (slug,),
            ).fetchone()
        elif page_type == "song":
            artist_hint, title_hint = _split_song_query(ref)
            if not artist_hint or not title_hint:
                return None
            slug = slugify(f"{artist_hint}-{title_hint}")
            row = conn.execute(
                "SELECT isrc AS slug, score, NULL AS platform_count, last_refreshed_at "
                "FROM seo_song_pages WHERE slug = ?",
                (slug,),
            ).fetchone()
        elif page_type == "playlist":
            pid = spotify_client.parse_playlist_id(ref) or ref
            row = conn.execute(
                "SELECT platform_playlist_id AS slug, fraud_score AS score, "
                "NULL AS platform_count, last_refreshed_at FROM seo_playlist_pages "
                "WHERE platform_playlist_id = ?",
                (pid,),
            ).fetchone()
        else:
            return None
    except ValueError:
        return None
    return dict(row) if row is not None else None


def list_pages(
    page_type: str = "artist",
    status: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Operator dashboard'u icin kuyruk + uretilmis sayfa verisini BIRLESTIRIR
    (bkz. /seo/pages admin uc noktasi, marketplace/api_seo.py). build_queue
    satirlarini page_type/status/search'e gore filtreler, priority DESC +
    created_at ASC sirasiyla sayfalar (build_next_batch'in ISLEME sirasiyla
    AYNI — operator bir sonraki neyin uretilecegini gorsun diye), sonra HER
    satir icin `_lookup_built_page` ile eslenik uretilmis sayfa var mi bakar.

    Donen her dict: id, page_type, ref, priority, status, created_at (kuyruk
    alanlari) + slug, score, platform_count, last_refreshed_at (uretilmemisse
    hepsi None)."""
    if page_type not in PAGE_TYPES:
        raise ValueError(f"Gecersiz sayfa turu: {page_type} (gecerli: {', '.join(PAGE_TYPES)})")
    if status is not None and status not in QUEUE_STATUSES:
        raise ValueError(f"Gecersiz durum: {status} (gecerli: {', '.join(QUEUE_STATUSES)})")
    if limit <= 0:
        raise ValueError("limit pozitif bir sayi olmali")
    if offset < 0:
        raise ValueError("offset negatif olamaz")

    where, params = _list_pages_where(page_type, status, search)
    conn = _connect()
    try:
        rows = conn.execute(
            f"SELECT id, page_type, ref, priority, status, created_at "
            f"FROM build_queue WHERE {where} "
            "ORDER BY priority DESC, created_at ASC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()

        items: list[dict] = []
        for row in rows:
            item = dict(row)
            built = _lookup_built_page(conn, page_type, row["ref"])
            item["slug"] = built.get("slug") if built else None
            item["score"] = built.get("score") if built else None
            item["platform_count"] = built.get("platform_count") if built else None
            item["last_refreshed_at"] = built.get("last_refreshed_at") if built else None
            items.append(item)
    finally:
        conn.close()
    return items


def list_pages_count(
    page_type: str = "artist", status: str | None = None, search: str | None = None
) -> int:
    """`list_pages` ile AYNI filtreleri uygulayip toplam satir sayisini doner
    (sayfalama/pagination icin — bkz. /seo/pages)."""
    if page_type not in PAGE_TYPES:
        raise ValueError(f"Gecersiz sayfa turu: {page_type} (gecerli: {', '.join(PAGE_TYPES)})")
    if status is not None and status not in QUEUE_STATUSES:
        raise ValueError(f"Gecersiz durum: {status} (gecerli: {', '.join(QUEUE_STATUSES)})")

    where, params = _list_pages_where(page_type, status, search)
    conn = _connect()
    try:
        row = conn.execute(
            f"SELECT COUNT(*) AS c FROM build_queue WHERE {where}", params
        ).fetchone()
    finally:
        conn.close()
    return row["c"] if row is not None else 0


# --- Okuma (Next.js ISR data fetch) -------------------------------------------

def _parse_json_fields(row: dict, fields: tuple[str, ...]) -> dict:
    d = dict(row)
    for field_name in fields:
        raw = d.get(field_name)
        d[field_name] = json.loads(raw) if raw else ({} if field_name.endswith("data_json") else [])
    return d


def get_artist_page(slug: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM seo_artist_pages WHERE slug = ?", (slug,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return _parse_json_fields(dict(row), ("findings_json", "data_json"))


def get_song_page(isrc: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM seo_song_pages WHERE isrc = ?", (isrc,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return _parse_json_fields(dict(row), ("data_json",))


def get_playlist_page(pid: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM seo_playlist_pages WHERE platform_playlist_id = ?", (pid,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return _parse_json_fields(dict(row), ("data_json",))


# --- Yazma yardimcilari (song/playlist sayfalari baska modullerce doldurulur) -

def upsert_song_page(
    isrc: str,
    slug: str,
    artist: str,
    title: str,
    score: float | None = None,
    bpm: float | None = None,
    song_key: str | None = None,
    data: dict | None = None,
) -> dict:
    """Sarki sayfasini olusturur/gunceller. score yoksa thin-content korumasi
    geregi YAZMAZ, {'skipped': True, 'reason': 'thin'} doner."""
    if not isrc or not isrc.strip():
        raise ValueError("ISRC bos olamaz")
    if not slug or not slug.strip():
        raise ValueError("Slug bos olamaz")
    if not artist or not title:
        raise ValueError("Sanatci ve sarki adi bos olamaz")
    if score is None:
        return {"skipped": True, "reason": "thin", "isrc": isrc}

    now = _now_iso()
    data_json = json.dumps(data or {}, ensure_ascii=False)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO seo_song_pages (
                    isrc, slug, artist, title, score, bpm, song_key,
                    data_json, last_refreshed_at, indexed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(isrc) DO UPDATE SET
                    slug = excluded.slug, artist = excluded.artist,
                    title = excluded.title, score = excluded.score,
                    bpm = excluded.bpm, song_key = excluded.song_key,
                    data_json = excluded.data_json,
                    last_refreshed_at = excluded.last_refreshed_at
                """,
                (isrc, slug, artist, title, score, bpm, song_key, data_json, now),
            )
        row = conn.execute(
            "SELECT * FROM seo_song_pages WHERE isrc = ?", (isrc,)
        ).fetchone()
    finally:
        conn.close()
    return _parse_json_fields(dict(row), ("data_json",))


def upsert_playlist_page(
    platform_playlist_id: str,
    slug: str,
    title: str,
    fraud_score: float | None = None,
    verdict: str | None = None,
    data: dict | None = None,
) -> dict:
    """Playlist sayfasini olusturur/gunceller. fraud_score yoksa thin-content
    korumasi geregi YAZMAZ, {'skipped': True, 'reason': 'thin'} doner."""
    if not platform_playlist_id or not platform_playlist_id.strip():
        raise ValueError("Playlist kimligi bos olamaz")
    if not slug or not slug.strip():
        raise ValueError("Slug bos olamaz")
    if not title:
        raise ValueError("Baslik bos olamaz")
    if fraud_score is None:
        return {"skipped": True, "reason": "thin", "platform_playlist_id": platform_playlist_id}

    now = _now_iso()
    data_json = json.dumps(data or {}, ensure_ascii=False)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO seo_playlist_pages (
                    platform_playlist_id, slug, title, fraud_score, verdict,
                    data_json, last_refreshed_at, indexed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(platform_playlist_id) DO UPDATE SET
                    slug = excluded.slug, title = excluded.title,
                    fraud_score = excluded.fraud_score, verdict = excluded.verdict,
                    data_json = excluded.data_json,
                    last_refreshed_at = excluded.last_refreshed_at
                """,
                (platform_playlist_id, slug, title, fraud_score, verdict, data_json, now),
            )
        row = conn.execute(
            "SELECT * FROM seo_playlist_pages WHERE platform_playlist_id = ?",
            (platform_playlist_id,),
        ).fetchone()
    finally:
        conn.close()
    return _parse_json_fields(dict(row), ("data_json",))


# --- Sitemap ------------------------------------------------------------------

_SITEMAP_TABLES = {
    "artist": ("seo_artist_pages", "slug", "slug"),
    "song": ("seo_song_pages", "isrc", "isrc"),
    "playlist": ("seo_playlist_pages", "platform_playlist_id", "pid"),
}


def pages_for_sitemap(page_type: str, offset: int = 0, limit: int = 50000) -> list[dict]:
    """Sitemap shard'lari icin sayfa kimlikleri + son yenileme zamani."""
    if page_type not in _SITEMAP_TABLES:
        raise ValueError(
            f"Gecersiz sayfa turu: {page_type} (gecerli: {', '.join(PAGE_TYPES)})"
        )
    if offset < 0:
        raise ValueError("offset negatif olamaz")
    if limit <= 0:
        raise ValueError("limit pozitif olmali")

    table, column, key_name = _SITEMAP_TABLES[page_type]
    conn = _connect()
    try:
        rows = conn.execute(
            f"SELECT {column} AS ref, last_refreshed_at FROM {table} "
            "ORDER BY id ASC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    finally:
        conn.close()
    return [
        {key_name: row["ref"], "last_refreshed_at": row["last_refreshed_at"]}
        for row in rows
    ]
