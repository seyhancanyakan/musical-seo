"""Sahte Playlist Dedektoru — playlist yerlesimi oncesi adli (forensic) analiz.

Amac: sanatcinin "kredi harcayip sahte/bot playliste mi ekleniyorum" riskini
yerlesim ONCESINDE gormesi. Bes bagimsiz sinyal (0..1) agirlikli toplanip
0..100 risk skoruna cevrilir:

    follower_anomaly     (0.30) — takipci sayisinda anormal sicrama
    track_churn          (0.20) — parca listesinin kisa surede asiri degismesi
    geo_cluster          (0.15) — dinleyici/takipci cografyasinin sirasiz yogunlasmasi
    audio_label_mismatch (0.20) — playlist etiketi (ör. "sakin") ile gercek ses
                                  profili (enerji/BPM) arasindaki uyumsuzluk
    track_seo_poverty    (0.15) — parca havuzunun SEO/kalite skorlarinin dusuklugu

Her sinyal fonksiyonu SAF'a yakindir: veri disaridan (parametre) verilir,
verilmezse yerel fraud_snapshots tablosundan okumaya calisir; hicbir kaynak
yoksa asla patlamaz — NOTR (0.5) skor + aciklayici detay doner. Boylece
network olmadan da unit test edilebilir ve entegrasyon gelene kadar sistem
"veri yok" durumunda asiri iddiali bir yargida bulunmaz.

Tablolar (marketplace.db):
    fraud_reports:   uretilen her adli analiz raporu (token ile paylasilabilir).
    fraud_snapshots: playlist icin zaman ici toplanan (takipci/parca/parca id
                     listesi) anlik goruntuler — follower_anomaly ve
                     track_churn sinyallerinin yerel veri kaynagi.

Is kurali ihlalleri ValueError (Turkce) — API katmani 400'e cevirir.
"""
from __future__ import annotations

import json
import secrets
import sqlite3

from marketplace import db

# --- Agirliklar + esikler ----------------------------------------------------

SIGNAL_WEIGHTS = {
    "follower_anomaly": 0.30,
    "track_churn": 0.20,
    "geo_cluster": 0.15,
    "audio_label_mismatch": 0.20,
    "track_seo_poverty": 0.15,
}

VERDICT_THRESHOLDS = (
    (25.0, "guvenli"),
    (50.0, "riskli"),
    (75.0, "cok_riskli"),
)
VERDICT_FALLBACK = "sahte"

FOLLOWER_JUMP_SCALE = 1.0          # ardisik anlik goruntu arasi %100 sicrama = tam risk
GEO_CONCENTRATION_FLOOR = 0.4      # bu payin altinda cografi yogunlasma normal sayilir
GEO_CONCENTRATION_CEILING = 1.0
CALM_KEYWORDS = {
    "sakin", "chill", "relax", "relaxing", "ambient", "calm", "peaceful",
    "yumusak", "huzur", "meditation", "sleep",
}
ENERGETIC_KEYWORDS = {
    "parti", "party", "dans", "dance", "energy", "workout", "upbeat",
    "enerjik", "gym", "motivation",
}
AUDIO_ENERGY_CALM_MAX = 0.6
AUDIO_ENERGY_ENERGETIC_MIN = 0.4
POVERTY_SCORE_THRESHOLD = 40.0    # bu skorun altindaki parca "SEO fakiri" sayilir

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS fraud_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        playlist_url TEXT NOT NULL,
        playlist_title TEXT,
        owner_name TEXT,
        total_risk_score REAL NOT NULL,
        verdict TEXT NOT NULL,
        signal_breakdown TEXT NOT NULL,
        recommendation TEXT NOT NULL,
        report_token TEXT NOT NULL UNIQUE,
        user_id INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS fraud_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        playlist_url TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        follower_count INTEGER,
        track_count INTEGER,
        track_ids TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_fraud_reports_user ON fraud_reports (user_id);",
    "CREATE INDEX IF NOT EXISTS idx_fraud_snapshots_playlist "
    "ON fraud_snapshots (playlist_url, captured_at);",
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


# --- Anlik goruntu (snapshot) deposu -----------------------------------------

def save_snapshot(
    playlist_url: str, follower_count: int | None, track_count: int | None,
    track_ids: list[str] | None = None,
) -> int:
    """Playlist icin zaman serisi anlik goruntusu kaydeder (fraud sinyalleri
    icin girdi). Gelecekte periyodik toplayici (cron) bunu besler."""
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO fraud_snapshots "
                "(playlist_url, captured_at, follower_count, track_count, track_ids) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    playlist_url, db.now_iso(), follower_count, track_count,
                    json.dumps(track_ids or [], ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid)
    finally:
        conn.close()


def _fetch_snapshots(playlist_url: str) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT captured_at, follower_count, track_count, track_ids "
            "FROM fraud_snapshots WHERE playlist_url = ? ORDER BY captured_at ASC",
            (playlist_url,),
        ).fetchall()
    finally:
        conn.close()
    result = []
    for row in rows:
        item = dict(row)
        raw_ids = item.get("track_ids")
        item["track_ids"] = json.loads(raw_ids) if raw_ids else []
        result.append(item)
    return result


# --- Sinyaller (0..1, saf/test edilebilir) -----------------------------------

def signal_follower_anomaly(playlist_url: str, snapshots: list[dict] | None = None) -> dict:
    """Ardisik anlik goruntuler arasi takipci sicramasi. Organik buyume kucuk
    adimlarla ilerler; bot/satin alma takipci sayisini bir gecede sicratir."""
    if snapshots is None:
        snapshots = _fetch_snapshots(playlist_url)
    counts = [s["follower_count"] for s in snapshots if s.get("follower_count") is not None]
    if len(counts) < 2:
        return {
            "score": 0.5,
            "detail": "Yetersiz gecmis veri (en az 2 anlik goruntu gerekli)",
            "evidence": {"snapshot_count": len(counts)},
        }
    max_jump_ratio = 0.0
    for prev, curr in zip(counts, counts[1:]):
        if prev <= 0:
            continue
        max_jump_ratio = max(max_jump_ratio, abs(curr - prev) / prev)
    score = round(min(max_jump_ratio / FOLLOWER_JUMP_SCALE, 1.0), 3)
    return {
        "score": score,
        "detail": f"En buyuk ardisik takipci sicramasi: %{max_jump_ratio * 100:.0f}",
        "evidence": {
            "max_jump_ratio": round(max_jump_ratio, 3),
            "snapshot_count": len(counts),
            "counts": counts,
        },
    }


def signal_track_churn(playlist_url: str, snapshots: list[dict] | None = None) -> dict:
    """Parca listesinin ardisik anlik goruntuler arasindaki degisim orani
    (Jaccard mesafesi). Asiri yuksek churn, parca rotasyonuyla sahte
    'aktiflik' yaratma paterniyle uyumludur."""
    if snapshots is None:
        snapshots = _fetch_snapshots(playlist_url)
    with_tracks = [s for s in snapshots if s.get("track_ids")]
    if len(with_tracks) < 2:
        return {
            "score": 0.5,
            "detail": "Parca listesi gecmisi yetersiz (en az 2 anlik goruntu gerekli)",
            "evidence": {"snapshot_count": len(with_tracks)},
        }
    churn_rates = []
    for prev, curr in zip(with_tracks, with_tracks[1:]):
        prev_set, curr_set = set(prev["track_ids"]), set(curr["track_ids"])
        union = prev_set | curr_set
        if not union:
            continue
        churn_rates.append(len(prev_set ^ curr_set) / len(union))
    if not churn_rates:
        return {
            "score": 0.5,
            "detail": "Parca kimligi karsilastirmasi yapilamadi",
            "evidence": {"snapshot_count": len(with_tracks)},
        }
    avg_churn = sum(churn_rates) / len(churn_rates)
    score = round(min(avg_churn, 1.0), 3)
    return {
        "score": score,
        "detail": f"Ortalama parca degisim orani: %{avg_churn * 100:.0f}",
        "evidence": {"avg_churn_rate": round(avg_churn, 3), "samples": len(churn_rates)},
    }


def signal_geo_cluster(playlist_url: str, geo_distribution: dict[str, float] | None = None) -> dict:
    """Dinleyici/takipci cografi dagiliminin tek bir ulkede sirasiz
    yogunlasmasi (click-farm/bot bolgesi belirtisi). Girdi henuz gercek bir
    kaynaga bagli degil; deger verilmezse notr doner."""
    if not geo_distribution:
        return {
            "score": 0.5,
            "detail": "Cografi dagilim verisi yok (dinleyici konum entegrasyonu bekleniyor)",
            "evidence": {},
        }
    total = sum(geo_distribution.values())
    if total <= 0:
        return {
            "score": 0.5,
            "detail": "Cografi dagilim verisi gecersiz (toplam sifir)",
            "evidence": {},
        }
    normalized = {k: v / total for k, v in geo_distribution.items()}
    top_country, top_share = max(normalized.items(), key=lambda kv: kv[1])
    span = GEO_CONCENTRATION_CEILING - GEO_CONCENTRATION_FLOOR
    score = round(
        max(0.0, min((top_share - GEO_CONCENTRATION_FLOOR) / span, 1.0)), 3
    )
    return {
        "score": score,
        "detail": f"En yogun ulke: {top_country} (%{top_share * 100:.0f})",
        "evidence": {
            "top_country": top_country,
            "top_share": round(top_share, 3),
            "distribution": normalized,
        },
    }


def _profile_energy(profile) -> float | None:
    if isinstance(profile, dict):
        return profile.get("energy")
    return getattr(profile, "energy", None)


def signal_audio_label_mismatch(
    playlist_url: str, playlist_title: str = "", profiles: list | None = None,
) -> dict:
    """Playlist basligindaki mood iddiasi ('sakin'/'enerjik') ile parcalarin
    gercek ses profili (musical_seo.audio.AudioProfile.energy) arasindaki
    uyumsuzluk. Uyumsuzluk, alakasiz parcayla doldurulmus (padded) playlist
    belirtisi olabilir."""
    if not profiles:
        return {
            "score": 0.5,
            "detail": "Ses profili verisi yok (once onizleme analizi calistirilmali)",
            "evidence": {},
        }
    energies = [e for e in (_profile_energy(p) for p in profiles) if e is not None]
    if not energies:
        return {
            "score": 0.5,
            "detail": "Ses profillerinde enerji degeri bulunamadi",
            "evidence": {},
        }
    avg_energy = sum(energies) / len(energies)
    title_l = (playlist_title or "").casefold()
    claims_calm = any(k in title_l for k in CALM_KEYWORDS)
    claims_energetic = any(k in title_l for k in ENERGETIC_KEYWORDS)

    if not (claims_calm or claims_energetic):
        return {
            "score": 0.5,
            "detail": "Baslikta belirgin mood etiketi yok, karsilastirma yapilamadi",
            "evidence": {"avg_energy": round(avg_energy, 3)},
        }

    mismatch = 0.0
    if claims_calm and avg_energy > AUDIO_ENERGY_CALM_MAX:
        mismatch = min(
            (avg_energy - AUDIO_ENERGY_CALM_MAX) / (1.0 - AUDIO_ENERGY_CALM_MAX), 1.0
        )
        detail = f"Playlist 'sakin' iddia ediyor ama ortalama enerji {avg_energy:.2f}"
    elif claims_energetic and avg_energy < AUDIO_ENERGY_ENERGETIC_MIN:
        mismatch = min(
            (AUDIO_ENERGY_ENERGETIC_MIN - avg_energy) / AUDIO_ENERGY_ENERGETIC_MIN, 1.0
        )
        detail = f"Playlist 'enerjik' iddia ediyor ama ortalama enerji {avg_energy:.2f}"
    else:
        detail = f"Etiket ile ses profili tutarli (ortalama enerji {avg_energy:.2f})"

    return {
        "score": round(mismatch, 3),
        "detail": detail,
        "evidence": {
            "avg_energy": round(avg_energy, 3),
            "claims_calm": claims_calm,
            "claims_energetic": claims_energetic,
        },
    }


def signal_track_seo_poverty(playlist_url: str, track_scores: list[float] | None = None) -> dict:
    """Playlist'teki parcalarin SEO/kalite karne skorlari (musical_seo.audit).
    Genuine kuratorluk yerine miktar odakli doldurma yapilan playlist'lerde
    parca havuzu genelde dusuk-kaliteli/optimize edilmemis olur."""
    if not track_scores:
        return {
            "score": 0.5,
            "detail": "Parca SEO skorlari yok (karne verisi entegrasyonu bekleniyor)",
            "evidence": {},
        }
    scored = [s for s in track_scores if s is not None]
    if not scored:
        return {
            "score": 0.5,
            "detail": "Parca SEO skorlari gecersiz",
            "evidence": {},
        }
    poor = sum(1 for s in scored if s < POVERTY_SCORE_THRESHOLD)
    ratio = poor / len(scored)
    return {
        "score": round(ratio, 3),
        "detail": (
            f"{poor}/{len(scored)} parca dusuk SEO skoruna sahip "
            f"(<{POVERTY_SCORE_THRESHOLD:.0f})"
        ),
        "evidence": {
            "poor_count": poor,
            "track_count": len(scored),
            "poverty_threshold": POVERTY_SCORE_THRESHOLD,
        },
    }


# --- Notr veri toplama (test/gelecek entegrasyon icin izole nokta) ----------

def _gather_inputs(playlist_url: str) -> dict:
    """Su an icin tek yerel/ag-siz veri kaynagi: fraud_snapshots. Diger
    sinyaller (geo/audio/seo) icin gercek zamanli entegrasyon henuz yok; test
    veya ileri entegrasyonlar bu fonksiyonu monkeypatch'leyerek veya
    analyze_playlist'e dogrudan parametre gecerek veri saglayabilir."""
    return {
        "snapshots": _fetch_snapshots(playlist_url),
        "playlist_title": "",
        "profiles": None,
        "geo_distribution": None,
        "track_scores": None,
    }


def _verdict_for(total_risk_score: float) -> str:
    for ceiling, verdict in VERDICT_THRESHOLDS:
        if total_risk_score < ceiling:
            return verdict
    return VERDICT_FALLBACK


def _recommendation_for(verdict: str, signals: dict[str, dict]) -> str:
    risky = [name for name, s in signals.items() if s["score"] >= 0.6]
    if verdict == "guvenli":
        base = "Belirgin sahtecilik sinyali yok; yerlesim icin guvenli gorunuyor."
    elif verdict == "riskli":
        base = "Dikkatli ol: bazi sinyaller anomali gosteriyor."
    elif verdict == "cok_riskli":
        base = "Yuksek risk: yerlesim onerilmez, ek dogrulama yap."
    else:
        base = "Guclu sahtecilik izleri: bu playliste yerlesim onerilmiyor."
    if risky:
        base += " Riskli sinyaller: " + ", ".join(risky) + "."
    return base


def _save_report(report: dict, user: dict | None) -> None:
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO fraud_reports "
                "(created_at, playlist_url, playlist_title, owner_name, "
                "total_risk_score, verdict, signal_breakdown, recommendation, "
                "report_token, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    db.now_iso(),
                    report["playlist_url"],
                    report["playlist_title"],
                    "",
                    report["total_risk_score"],
                    report["verdict"],
                    json.dumps(report["signals"], ensure_ascii=False),
                    report["recommendation"],
                    report["report_token"],
                    user["id"] if user else None,
                ),
            )
    finally:
        conn.close()


def _row_to_report(row: dict) -> dict:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "playlist_url": row["playlist_url"],
        "playlist_title": row["playlist_title"],
        "total_risk_score": row["total_risk_score"],
        "verdict": row["verdict"],
        "signals": json.loads(row["signal_breakdown"]),
        "recommendation": row["recommendation"],
        "report_token": row["report_token"],
    }


# --- Ana giris noktasi --------------------------------------------------------

def analyze_playlist(
    playlist_url: str,
    user: dict | None = None,
    *,
    playlist_title: str | None = None,
    geo_distribution: dict[str, float] | None = None,
    profiles: list | None = None,
    track_scores: list[float] | None = None,
) -> dict:
    """5 sinyali toplar, agirlikli 0..100 risk skoru + verdict uretir, rapor
    kaydeder ve doner. Ek anahtar-kelime parametreleri (playlist_title,
    geo_distribution, profiles, track_scores) test/entegrasyon icin veri
    enjeksiyonu sağlar; hicbiri verilmezse _gather_inputs'un yerel
    fraud_snapshots'tan cikardigi veriyle (veya notr fallback'lerle) calisir.
    """
    if not playlist_url or not playlist_url.strip():
        raise ValueError("Playlist URL bos olamaz")

    inputs = _gather_inputs(playlist_url)
    if playlist_title is not None:
        inputs["playlist_title"] = playlist_title
    if geo_distribution is not None:
        inputs["geo_distribution"] = geo_distribution
    if profiles is not None:
        inputs["profiles"] = profiles
    if track_scores is not None:
        inputs["track_scores"] = track_scores

    signals = {
        "follower_anomaly": signal_follower_anomaly(
            playlist_url, snapshots=inputs["snapshots"]
        ),
        "track_churn": signal_track_churn(playlist_url, snapshots=inputs["snapshots"]),
        "geo_cluster": signal_geo_cluster(
            playlist_url, geo_distribution=inputs["geo_distribution"]
        ),
        "audio_label_mismatch": signal_audio_label_mismatch(
            playlist_url, playlist_title=inputs["playlist_title"], profiles=inputs["profiles"]
        ),
        "track_seo_poverty": signal_track_seo_poverty(
            playlist_url, track_scores=inputs["track_scores"]
        ),
    }

    total_risk_score = round(
        sum(
            signals[name]["score"] * weight * 100
            for name, weight in SIGNAL_WEIGHTS.items()
        ),
        1,
    )
    verdict = _verdict_for(total_risk_score)
    recommendation = _recommendation_for(verdict, signals)
    report_token = f"FRAUD-{secrets.token_hex(3).upper()}"

    report = {
        "playlist_url": playlist_url,
        "playlist_title": inputs["playlist_title"],
        "total_risk_score": total_risk_score,
        "verdict": verdict,
        "signals": signals,
        "recommendation": recommendation,
        "report_token": report_token,
    }
    _save_report(report, user)
    return report


def get_report(token: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM fraud_reports WHERE report_token = ?", (token,)
        ).fetchone()
        return _row_to_report(dict(row)) if row else None
    finally:
        conn.close()


def reports_for_user(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM fraud_reports WHERE user_id = ? ORDER BY id DESC", (user_id,)
        ).fetchall()
        return [_row_to_report(dict(r)) for r in rows]
    finally:
        conn.close()
