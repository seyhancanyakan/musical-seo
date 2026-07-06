"""Ses parmak izi (audio fingerprint) yayin dogrulama motoru.

Basitlestirilmis dejavu-benzeri landmark hashing: sinyalin spektrogramindan
yerel tepe (peak) noktalari cikarilir, komsu tepe ciftlerinden (f1, f2, dt)
hash'ler uretilir. Iki sesin fingerprint kumeleri kesisimi ne kadar buyukse
o kadar eslesir — kucuk gurultu/kirpma degisimlerine dayanikli, tam dosya
karsilastirmasindan (byte-byte) cok daha saglam.

Kullanim akisi:
    1. register_spot(order_id, wav_path)  -> reklam spotunun parmak izi kaydedilir.
    2. scan_chunk(station_id, samples, rate) -> canli/kayitli bir istasyon
       parcasi kayitli tum spotlarla karsilastirilir; esik ustu eslesme
       fp_detections'a yazilir + radio_ad_orders.verified_plays +1 artar
       (ayni order+istasyon icin DEDUPE_MINUTES icinde tekrar sayilmaz).
    3. capture_stream_chunk(stream_url) -> ffmpeg ile canli akistan kisa bir
       ses parcasi yakalar (ffmpeg yoksa None doner, sessizce vazgecer).
    4. watch_once(stations) -> tum istasyonlari tek seferde tarar (manuel
       tetik / cron endpoint icin). SUREKLI IZLEYICI THREAD'I YOK — sonraki
       adimda eklenecek.

Tablolar (marketplace.db, radio_ads.py'nin uzerine kurulur):
    ad_spot_prints: kayitli reklam spotu parmak izleri (order_id UNIQUE).
    fp_detections:  tespit edilen yayin kayitlari (order_id + station_id + zaman).

Hata sozlesmesi: is kurali ihlalleri ValueError (aksanli Turkce) — API
katmani 400'e cevirir. ffmpeg yoksa fonksiyonlar hata firlatmaz, None doner
(canli izleme dongusu tek istasyon/arac eksikligiyle durmamali).
"""
from __future__ import annotations

import hashlib
import pickle
import shutil
import sqlite3
import subprocess
import tempfile
import wave
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

import numpy as np

from marketplace import db, radio_ads

# --- Spektrogram / parmak izi parametreleri ---------------------------------

WINDOW_SIZE = 4096          # FFT pencere boyutu (ornek sayisi)
HOP_SIZE = WINDOW_SIZE // 2  # %50 ortusme
PEAK_NEIGHBORHOOD_TIME = 3   # yerel maksimum komsulugu: zaman ekseni (kare)
PEAK_NEIGHBORHOOD_FREQ = 6   # yerel maksimum komsulugu: frekans ekseni (bin)
PEAK_AMP_STD_FACTOR = 1.5    # esik = ortalama + factor * std (log-magnitude)
FAN_VALUE = 15               # dejavu-tarzi fan-out: her tepe en fazla 15 sonraki ile eslenir
MIN_FAN = 5                  # yeterli tepe varsa en az bu kadar eslesme aranir (dokuman amacli)
STREAM_SAMPLE_RATE = 11025   # ffmpeg yakalama orneklem hizi
DEDUPE_MINUTES = 10          # ayni order+istasyon icin tekrar sayilmama penceresi

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS ad_spot_prints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        order_id INTEGER NOT NULL UNIQUE,
        source_path TEXT NOT NULL,
        hash_blob BLOB NOT NULL,
        hash_count INTEGER NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS fp_detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        detected_at TEXT NOT NULL,
        order_id INTEGER NOT NULL,
        station_id INTEGER NOT NULL,
        confidence REAL NOT NULL,
        UNIQUE(order_id, station_id, detected_at)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_fp_detections_order "
    "ON fp_detections (order_id, station_id, detected_at);",
]


def _connect() -> sqlite3.Connection:
    conn = radio_ads._connect()  # marketplace.db + db semasi + radio_ad_* tablolari hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


# --- Spektrogram + yerel tepe (peak) cikarimi -------------------------------

def _spectrogram(samples: np.ndarray, rate: int) -> np.ndarray:
    """Pencereli FFT, %50 ortusme, log-magnitude. Donen sekil: (frame, freq_bin)."""
    samples = np.asarray(samples, dtype=np.float64)
    n = samples.shape[0]
    if n < WINDOW_SIZE:
        padded = np.zeros(WINDOW_SIZE, dtype=np.float64)
        padded[:n] = samples
        samples = padded
        n = WINDOW_SIZE

    window = np.hanning(WINDOW_SIZE)
    n_frames = 1 + (n - WINDOW_SIZE) // HOP_SIZE
    freq_bins = WINDOW_SIZE // 2

    spec = np.empty((n_frames, freq_bins), dtype=np.float64)
    for i in range(n_frames):
        start = i * HOP_SIZE
        frame = samples[start:start + WINDOW_SIZE] * window
        magnitude = np.abs(np.fft.rfft(frame)[:freq_bins])
        spec[i] = np.log(magnitude + 1e-6)
    return spec


def _local_maxima_mask(arr: np.ndarray, size_row: int, size_col: int) -> np.ndarray:
    """arr'daki her hucrenin (size_row, size_col) komsulugundaki en buyuk deger
    olup olmadigini isaretler (scipy.ndimage olmadan saf numpy ile)."""
    rows, cols = arr.shape
    running_max = arr.copy()
    for dr in range(-size_row, size_row + 1):
        for dc in range(-size_col, size_col + 1):
            if dr == 0 and dc == 0:
                continue
            shifted = np.full_like(arr, -np.inf)
            r0, r1 = max(0, dr), rows + min(0, dr)
            c0, c1 = max(0, dc), cols + min(0, dc)
            sr0, sr1 = max(0, -dr), rows + min(0, -dr)
            sc0, sc1 = max(0, -dc), cols + min(0, -dc)
            if r1 > r0 and c1 > c0:
                shifted[r0:r1, c0:c1] = arr[sr0:sr1, sc0:sc1]
            running_max = np.maximum(running_max, shifted)
    return arr >= running_max


def _peaks(spec: np.ndarray) -> list[tuple[int, int]]:
    """Esik ustu yerel maksimum tepeler. Donen: [(frame_idx, freq_idx), ...]
    zaman ekseninde artan sirada."""
    if spec.size == 0:
        return []
    threshold = spec.mean() + PEAK_AMP_STD_FACTOR * spec.std()
    mask = _local_maxima_mask(spec, PEAK_NEIGHBORHOOD_TIME, PEAK_NEIGHBORHOOD_FREQ)
    mask &= spec > threshold
    frame_idx, freq_idx = np.where(mask)
    order = np.argsort(frame_idx, kind="stable")
    return list(zip(frame_idx[order].tolist(), freq_idx[order].tolist()))


def _hash_peaks(peaks: list[tuple[int, int]]) -> set[int]:
    """Tepe ciftlerinden (f1, f2, dt) sha1 tabanli, deterministik 32-bit hash'ler
    uretir (dejavu fan-out=15 mantigi)."""
    hashes: set[int] = set()
    n = len(peaks)
    for i in range(n):
        t1, f1 = peaks[i]
        for j in range(1, FAN_VALUE + 1):
            k = i + j
            if k >= n:
                break
            t2, f2 = peaks[k]
            dt = t2 - t1
            if dt <= 0:
                continue
            digest = hashlib.sha1(f"{f1}|{f2}|{dt}".encode("utf-8")).hexdigest()
            hashes.add(int(digest[:8], 16))
    return hashes


def fingerprint_samples(samples: Sequence[float] | np.ndarray, rate: int) -> set[int]:
    """Ham ornekten (mono varsayilir, coklu kanal ise ortalanir) fingerprint hash
    kumesi cikarir."""
    arr = np.asarray(samples, dtype=np.float64)
    if arr.ndim > 1:
        arr = arr.mean(axis=1)
    if arr.size == 0:
        return set()
    peak_abs = np.max(np.abs(arr))
    if peak_abs > 1.0:  # int16 araligi gorunuyor -> normalize et
        arr = arr / 32768.0
    spec = _spectrogram(arr, rate)
    peaks = _peaks(spec)
    return _hash_peaks(peaks)


def fingerprint_wav(path: str | Path) -> set[int]:
    """16-bit PCM WAV dosyasindan (mono'ya indirilerek) fingerprint cikarir.
    MP3 icin: ffmpeg varsa once WAV'a cevrilir; yoksa ValueError."""
    path = Path(path)
    if path.suffix.lower() == ".mp3":
        if shutil.which("ffmpeg") is None:
            raise ValueError("MP3 icin ffmpeg gerekli")
        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "converted.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(path), "-ac", "1",
                 "-ar", str(STREAM_SAMPLE_RATE), str(wav_path)],
                capture_output=True, timeout=60, check=True,
            )
            return fingerprint_wav(wav_path)

    with wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        samp_width = wf.getsampwidth()
        rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if samp_width != 2:
        raise ValueError("Sadece 16-bit PCM WAV destekleniyor")

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    if n_channels > 1:
        samples = samples.reshape(-1, n_channels).mean(axis=1)
    return fingerprint_samples(samples, rate)


def match_score(spot_hashes: set[int], chunk_hashes: set[int]) -> float:
    """kesisim / spot boyutu, 0..1. Bos spot fingerprint'i 0.0 doner."""
    if not spot_hashes:
        return 0.0
    return len(spot_hashes & chunk_hashes) / len(spot_hashes)


# --- Kayit (register) --------------------------------------------------------

def register_spot(order_id: int, wav_path: str | Path) -> dict:
    """Reklam spotunun parmak izini cikarir + kaydeder. Ayni order_id icin
    tekrar cagrilirsa parmak izi guncellenir (UPSERT)."""
    hashes = fingerprint_wav(wav_path)
    if not hashes:
        raise ValueError("Ses dosyasından parmak izi çıkarılamadı")

    blob = pickle.dumps(hashes)
    conn = _connect()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO ad_spot_prints
                    (created_at, order_id, source_path, hash_blob, hash_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(order_id) DO UPDATE SET
                    created_at = excluded.created_at,
                    source_path = excluded.source_path,
                    hash_blob = excluded.hash_blob,
                    hash_count = excluded.hash_count
                """,
                (db.now_iso(), order_id, str(wav_path), blob, len(hashes)),
            )
        row = conn.execute(
            "SELECT id, created_at, order_id, source_path, hash_count "
            "FROM ad_spot_prints WHERE order_id = ?", (order_id,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def _all_spot_prints(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT order_id, hash_blob FROM ad_spot_prints"
    ).fetchall()
    return [
        {"order_id": r["order_id"], "hashes": pickle.loads(r["hash_blob"])}
        for r in rows
    ]


# --- Tarama (scan) + tespit ---------------------------------------------------

def scan_chunk(
    station_id: int, samples: Sequence[float] | np.ndarray, rate: int,
    threshold: float = 0.15,
) -> list[dict]:
    """Bir istasyondan alinan ses parcasini kayitli tum spot parmak izleriyle
    karsilastirir. Esik ustu eslesme icin fp_detections'a yazar + ilgili
    order'in verified_plays sayacini +1 artirir (dogrudan SQL, radio_ads ile
    ayni dedupe mantigi: ayni order+istasyon DEDUPE_MINUTES icinde tekrar
    sayilmaz)."""
    chunk_hashes = fingerprint_samples(samples, rate)
    if not chunk_hashes:
        return []

    conn = _connect()
    detections: list[dict] = []
    try:
        prints = _all_spot_prints(conn)
        now = db.now_iso()
        since = (
            datetime.fromisoformat(now) - timedelta(minutes=DEDUPE_MINUTES)
        ).isoformat()

        for entry in prints:
            score = match_score(entry["hashes"], chunk_hashes)
            if score < threshold:
                continue
            order_id = entry["order_id"]
            recent = conn.execute(
                "SELECT 1 FROM fp_detections "
                "WHERE order_id = ? AND station_id = ? AND detected_at > ? LIMIT 1",
                (order_id, station_id, since),
            ).fetchone()
            if recent is not None:
                continue

            with conn:
                conn.execute(
                    "INSERT INTO fp_detections "
                    "(detected_at, order_id, station_id, confidence) "
                    "VALUES (?, ?, ?, ?)",
                    (now, order_id, station_id, score),
                )
                conn.execute(
                    "UPDATE radio_ad_orders SET verified_plays = verified_plays + 1 "
                    "WHERE id = ?",
                    (order_id,),
                )
            detections.append({
                "order_id": order_id, "station_id": station_id,
                "confidence": score, "detected_at": now,
            })
        return detections
    finally:
        conn.close()


def list_detections(order_id: int | None = None) -> list[dict]:
    sql, params = "SELECT * FROM fp_detections", []
    if order_id is not None:
        sql += " WHERE order_id = ?"
        params.append(order_id)
    sql += " ORDER BY id DESC"
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# --- Canli akis yakalama (ffmpeg) --------------------------------------------

def capture_stream_chunk(stream_url: str, seconds: int = 12) -> np.ndarray | None:
    """ffmpeg ile canli akistan kisa bir mono ses parcasi yakalar.
    ffmpeg kurulu degilse (veya yakalama basarisiz olursa) None doner —
    yoklama dongusu tek istasyon hatasiyla durmamali."""
    if shutil.which("ffmpeg") is None:
        return None
    cmd = [
        "ffmpeg", "-y", "-i", stream_url, "-t", str(seconds),
        "-ac", "1", "-ar", str(STREAM_SAMPLE_RATE), "-f", "wav", "pipe:1",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=seconds + 15, check=True,
        )
    except Exception:
        return None

    try:
        import io
        with wave.open(io.BytesIO(result.stdout), "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            n_channels = wf.getnchannels()
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)
        return samples
    except Exception:
        return None


def watch_once(stations: list[dict]) -> dict:
    """Verilen istasyon listesini ({id, stream_url}) tek seferde tarar
    (manuel admin tetigi / cron endpoint). SUREKLI IZLEYICI THREAD'I YOK —
    sonraki adimda eklenecek."""
    scanned = 0
    detections: list[dict] = []
    for station in stations:
        samples = capture_stream_chunk(station["stream_url"])
        if samples is None:
            continue
        scanned += 1
        detections.extend(scan_chunk(station["id"], samples, STREAM_SAMPLE_RATE))
    return {"scanned": scanned, "detections": detections}
