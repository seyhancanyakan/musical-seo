"""Sahte Playlist Dedektoru — playlist yerlesimi oncesi adli (forensic) analiz.

Amac: sanatcinin "kredi harcayip sahte/bot playliste mi ekleniyorum" riskini
yerlesim ONCESINDE gormesi. Bes bagimsiz sinyal (0..1) tanimlanir, ancak
SADECE GERCEK VERIYE DAYANAN (informatif) sinyaller agirlikli ortalamaya
katilir — kalan agirliklar 1'e RENORMALIZE edilir (asagida "Veri kapsami"):

    follower_anomaly     (0.30) — takipci sayisinda anormal sicrama [GERCEK:
                                  Spotify snapshot zaman-serisi, 2+ olcum gerekir]
    track_churn          (0.20) — parca listesinin kisa surede asiri degismesi
                                  [GERCEK: Spotify snapshot zaman-serisi]
    geo_cluster          (0.15) — dinleyici/takipci cografyasinin sirasiz
                                  yogunlasmasi [VERI YOK: Spotify Web API
                                  dinleyici konumu vermiyor — HER ZAMAN notr,
                                  agirlikli skora KATILMAZ]
    audio_label_mismatch (0.20) — playlist etiketi (ör. "sakin") ile gercek ses
                                  profili (enerji/BPM) arasindaki uyumsuzluk
                                  [GERCEK: playlist parca ornegi -> Deezer
                                  onizleme -> musical_seo.audio]
    track_seo_poverty    (0.15) — parca havuzunun SEO/kalite skorlarinin dusuklugu
                                  [GERCEK: playlist parca ornegi -> musical_seo.audit]

Her sinyal fonksiyonu SAF'a yakindir: veri disaridan (parametre) verilir,
verilmezse yerel fraud_snapshots tablosundan okumaya calisir; hicbir kaynak
yoksa asla patlamaz — NOTR (0.5) skor + aciklayici detay doner. Boylece
network olmadan da unit test edilebilir ve gercek veri kaynagi (Spotify/
Deezer/audit) erisilemedigi durumda sistem asiri iddiali bir yargida
bulunmaz.

Veri kapsami / renormalizasyon: geo_cluster icin gercek bir veri kaynagi
yok (Spotify Web API dinleyici cografyasi paylasmiyor) — bu sinyal HER ZAMAN
notr (0.5) doner ve agirlikli risk skoruna dahil EDILMEZ. Diger 4 sinyalden
hangileri o an informatif ise (gercek veriye dayaniyorsa) SADECE onlarin
agirliklari toplamda 1 olacak sekilde yeniden olceklenir (bkz.
`_weighted_risk_score`); boylece eksik geo sinyali skoru yapay olarak 50'ye
cekmez. Hicbir sinyal informatif degilse (ör. Spotify hic erisilemedi) eski
davranis korunur (tum sinyaller notr -> skor 50, verdict 'veri_yetersiz').

Tablolar (marketplace.db):
    fraud_reports:   uretilen her adli analiz raporu (token ile paylasilabilir).
    fraud_snapshots: playlist icin zaman ici toplanan (takipci/parca/parca id
                     listesi) anlik goruntuler — follower_anomaly ve
                     track_churn sinyallerinin yerel veri kaynagi.
                     `snapshot_playlist` her analyze_playlist cagrisinda
                     (ve gunluk cron'da) Spotify'dan taze bir satir ekler.

Is kurali ihlalleri ValueError (Turkce) — API katmani 400'e cevirir.
"""
from __future__ import annotations

import json
import secrets
import sqlite3

import requests

from marketplace import db, spotify_client
from musical_seo import audio
from musical_seo import audit as seo_audit

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

# Verdict verebilmek icin gereken ASGARI informatif (gercek veriye dayanan)
# sinyal sayisi. geo HER ZAMAN notr (API yok), follower/churn 2+ Spotify
# snapshot ister (zaman), audio-label baslikta mood etiketi yoksa notr kalir —
# bu yuzden ILK analizde cogu zaman sadece parca-SEO gercektir. Esik 2 olsaydi
# ilk analiz hep 'veri_yetersiz' cikardi. 1: tek gercek sinyal bile (renormalize
# edilmis) bir verdict uretir; guven duzeyi rapordaki data_coverage (ör. 1/5) ile
# gosterilir. 0 informatif (tum sinyaller notr, ör. editoryal/erisilemez playlist)
# -> yine 'veri_yetersiz'.
MIN_INFORMATIVE_SIGNALS = 1

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

# Playlist'ten audio_label_mismatch + track_seo_poverty icin ornekleme sinirin
# — Deezer onizleme indirme + librosa analizi + audit.run_audit agir/yavas
# oldugundan playlist basina en fazla bu kadar parca islenir.
SAMPLE_TRACK_LIMIT = 8

# Deezer'da 30 sn onizleme aramak icin (audio_label_mismatch girdisi).
# musical_seo.sources.deezer.TrackInfo onizleme URL'ini tasimiyor (sadece
# metadata) — bu yuzden marketplace.cover_hunter'daki ayni desenle dogrudan
# arama uc noktasina gidilir.
_DEEZER_SEARCH_URL = "https://api.deezer.com/search"
_DEEZER_TIMEOUT = 15

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


def snapshot_playlist(playlist_url: str) -> dict | None:
    """Spotify'dan (Client Credentials) playlist'i ceker ve fraud_snapshots'a
    taze bir satir yazar — zaman-serisi biriktirme boylece ilerler (her
    analyze_playlist cagrisi + gunluk cron bir satir ekler).

    Spotify musait degilse (kimlik bilgisi yok, URL bir Spotify playlist
    URL'i degil, ag hatasi, kota asimi, 404/editoryal liste) None doner;
    hicbir zaman exception firlatmaz — cagiran taraf (analyze_playlist) bunu
    "veri yok" olarak ele alir. Donen dict, spotify_client.get_playlist ile
    ayni sozlesme: {name, followers, track_count, tracks}."""
    playlist_id = spotify_client.parse_playlist_id(playlist_url)
    if not playlist_id:
        return None
    playlist = spotify_client.get_playlist(playlist_id)
    if playlist is None:
        return None

    track_ids = [t["id"] for t in (playlist.get("tracks") or []) if t.get("id")]
    save_snapshot(
        playlist_url, playlist.get("followers"), playlist.get("track_count"), track_ids,
    )
    return playlist


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


# --- Playlist ornekleminden gercek veri cikarma (audio + parca SEO) ---------
# snapshot_playlist Spotify'dan taze bir parca listesi getirdiginde,
# analyze_playlist bu yardimcilarla audio_label_mismatch ve
# track_seo_poverty icin GERCEK girdi uretir (aciykca profiles/track_scores
# verilmediginde). Her adim guvenceli: tek bir parcanin Deezer/audit
# basarisiz olmasi ornegin tamamini bozmaz, sadece o parca atlanir.

def _sample_tracks(tracks: list[dict] | None) -> list[dict]:
    """Ad + en az bir sanatcisi olan parcalardan ilk SAMPLE_TRACK_LIMIT
    tanesini secer (agir analiz/audit cagrilarini sinirlamak icin)."""
    usable = [t for t in (tracks or []) if t.get("name") and t.get("artists")]
    return usable[:SAMPLE_TRACK_LIMIT]


def _track_audio_profile(artist: str, title: str) -> "audio.AudioProfile | None":
    """Deezer'da parcayi arar, 30 sn onizlemeyi ceker, musical_seo.audio ile
    ses profili cikarir. librosa kurulu degilse, Deezer'da sonuc yoksa ya da
    herhangi bir adim basarisiz olursa None doner — asla patlamaz."""
    if not audio.available():
        return None
    try:
        response = requests.get(
            _DEEZER_SEARCH_URL, params={"q": f"{artist} {title}", "limit": 1},
            timeout=_DEEZER_TIMEOUT,
        )
        response.raise_for_status()
        results = (response.json() or {}).get("data") or []
    except (requests.RequestException, ValueError):
        return None
    if not results:
        return None
    preview_url = results[0].get("preview")
    if not preview_url:
        return None
    return audio.analyze_url(preview_url)


def _gather_audio_profiles(tracks: list[dict] | None) -> list:
    """Playlist ornegindeki parcalar icin ses profili listesi (mumkun
    oldugu kadar) — signal_audio_label_mismatch girdisi. Hicbir parca
    cozumlenemezse [] doner (sinyal notr kalir, cokme yok)."""
    profiles = []
    for track in _sample_tracks(tracks):
        artist = (track.get("artists") or [None])[0]
        title = track.get("name")
        if not artist or not title:
            continue
        try:
            profile = _track_audio_profile(artist, title)
        except Exception:
            profile = None
        if profile is not None:
            profiles.append(profile)
    return profiles


def _gather_track_scores(tracks: list[dict] | None) -> list[float]:
    """Playlist ornegindeki parcalar icin musical_seo.audit SEO/kalite
    skorlari — signal_track_seo_poverty girdisi. audit.run_audit sarki
    bulunamazsa ValueError firlatir; burada yutulur (parca atlanir)."""
    scores: list[float] = []
    for track in _sample_tracks(tracks):
        artist = (track.get("artists") or [None])[0]
        title = track.get("name")
        if not artist or not title:
            continue
        try:
            result = seo_audit.run_audit(f"{artist} - {title}")
            scores.append(float(result.score))
        except Exception:
            continue
    return scores


# --- Notr veri toplama (test/gelecek entegrasyon icin izole nokta) ----------

def _gather_inputs(playlist_url: str) -> dict:
    """Su an icin tek yerel/ag-siz veri kaynagi: fraud_snapshots. Diger
    sinyaller (geo/audio/seo) icin varsayilan notr; analyze_playlist bunlari
    snapshot_playlist ile gelen canli playlist ornegiyle (veya test/entegrasyon
    icin dogrudan parametreyle) doldurur."""
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


def _is_informative(score: float) -> bool:
    """Sinyal notr fallback (0.5) DISINDA bir deger dondurduyse gercek
    veriye dayaniyor demektir. MIN_INFORMATIVE_SIGNALS esigi ve agirlik
    renormalizasyonu ayni bu heuristigi kullanir."""
    return abs(score - 0.5) > 1e-9


def _weighted_risk_score(signals: dict[str, dict]) -> tuple[float, list[str]]:
    """0..100 agirlikli risk skoru + informatif (gercek veriye dayanan)
    sinyal adlari.

    RENORMALIZASYON: notr (veri yok) sinyaller (ör. geo_cluster her zaman,
    veya henuz yeterli snapshot'i olmayan follower_anomaly/track_churn)
    agirlikli ortalamadan TAMAMEN CIKARILIR; kalan informatif sinyallerin
    agirliklari toplamda 1 olacak sekilde yeniden olceklenir. Boylece ör.
    sadece geo eksikken skor, geo'nun sabit 0.5*0.15'i yuzunden yapay olarak
    50'ye cekilmez — kalan 4 sinyal 0.85 toplam agirlik yerine 1.0'a
    olceklenmis halleriyle skoru belirler.

    Hicbir sinyal informatif degilse (ör. Spotify/Deezer/audit hicbirine
    erisilemedi) renormalizasyon tanimsizdir; bu durumda eski davranisa
    (tum sinyaller * ham agirlik) donulur — zaten tum sinyaller notr
    oldugundan bu her zaman 50.0 verir ve MIN_INFORMATIVE_SIGNALS kontrolu
    verdict'i 'veri_yetersiz' yapar (skor deger degil, sadece bilgi)."""
    informative = [name for name, s in signals.items() if _is_informative(s["score"])]
    if not informative:
        raw_score = sum(
            signals[name]["score"] * weight * 100
            for name, weight in SIGNAL_WEIGHTS.items()
        )
        return round(raw_score, 1), informative

    weight_sum = sum(SIGNAL_WEIGHTS[name] for name in informative)
    renormalized_score = sum(
        signals[name]["score"] * SIGNAL_WEIGHTS[name] for name in informative
    ) / weight_sum * 100
    return round(renormalized_score, 1), informative


def _data_coverage(signals: dict[str, dict]) -> dict:
    """Kac sinyalin gercek veriye dayandigini raporlar — skorun ne kadar
    'grounded' oldugunu UI/kullaniciya gostermek icin. geo_cluster gercek
    veri kaynagi olmadigindan neredeyse her zaman notr sayilir (0/5 yerine
    en fazla 4/5 gorulmesi beklenir)."""
    informative_names = [name for name, s in signals.items() if _is_informative(s["score"])]
    total = len(SIGNAL_WEIGHTS)
    return {
        "informative_signals": len(informative_names),
        "total_signals": total,
        "ratio": round(len(informative_names) / total, 2) if total else 0.0,
        "informative_signal_names": informative_names,
    }


def _recommendation_for(
    verdict: str, signals: dict[str, dict], coverage: dict | None = None,
) -> str:
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
    if coverage is not None:
        base += (
            f" (Veri kapsami: {coverage['informative_signals']}/"
            f"{coverage['total_signals']} sinyal gercek veriye dayaniyor; "
            "skor bu sinyallerin agirlikli renormalizasyonuyla hesaplandi.)"
        )
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
    signals = json.loads(row["signal_breakdown"])
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "playlist_url": row["playlist_url"],
        "playlist_title": row["playlist_title"],
        "total_risk_score": row["total_risk_score"],
        "verdict": row["verdict"],
        "signals": signals,
        "recommendation": row["recommendation"],
        "report_token": row["report_token"],
        # Kaydedilmedi (eski satirlarla geriye uyum) — saklanan sinyallerden
        # yeniden hesaplanir, boylece gecmis raporlar da veri kapsamini gosterir.
        "data_coverage": _data_coverage(signals),
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
    kaydeder ve doner.

    ONCE (guarded) snapshot_playlist(playlist_url) cagrilir: playlist bir
    Spotify playlist URL'i ise ve kimlik bilgisi musaitse taze bir
    fraud_snapshots satiri eklenir VE playlist'in guncel parca listesi
    audio_label_mismatch / track_seo_poverty icin GERCEK girdi uretmekte
    kullanilir (playlist_title/profiles/track_scores acikca verilmediyse).
    Spotify musait degilse (kimlik yok, URL Spotify degil, ag hatasi) bu
    adim sessizce atlanir — analiz eskisi gibi notr fallback'lerle devam
    eder, asla patlamaz.

    Ek anahtar-kelime parametreleri (playlist_title, geo_distribution,
    profiles, track_scores) test/entegrasyon icin veri enjeksiyonu saglar ve
    HER ZAMAN canli Spotify verisinden ONCELIKLIDIR.
    """
    if not playlist_url or not playlist_url.strip():
        raise ValueError("Playlist URL bos olamaz")

    try:
        live_playlist = snapshot_playlist(playlist_url)
    except Exception:
        live_playlist = None  # Spotify/ag hatasi analiz akisini asla durdurmasin

    inputs = _gather_inputs(playlist_url)

    if live_playlist is not None:
        if playlist_title is None and live_playlist.get("name"):
            inputs["playlist_title"] = live_playlist["name"]
        live_tracks = live_playlist.get("tracks") or []
        if profiles is None:
            live_profiles = _gather_audio_profiles(live_tracks)
            if live_profiles:
                inputs["profiles"] = live_profiles
        if track_scores is None:
            live_scores = _gather_track_scores(live_tracks)
            if live_scores:
                inputs["track_scores"] = live_scores

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

    total_risk_score, informative_names = _weighted_risk_score(signals)
    coverage = _data_coverage(signals)

    # Yeterli informatif sinyal yoksa risk skoru anlamsiz -> "sahte" gostermeyelim.
    # "Kanit yok" != "sahte".
    if len(informative_names) < MIN_INFORMATIVE_SIGNALS:
        verdict = "veri_yetersiz"
        recommendation = (
            "Yeterli veri yok — bu skor GUVENILIR DEGIL ve 'sahte' anlamina "
            "GELMEZ. Playlist zaman-serisi (2+ Spotify anlik goruntusu), "
            "audio profili ve parca SEO kaynaklari henuz yeterli veri "
            "uretmedigi icin sinyaller notr dondu. Guvenilir bir risk "
            "analizi icin tekrar analiz et (zaman serisi birikir) veya "
            "playlist'in Spotify'da erisilebilir oldugunu dogrula. "
            f"(Veri kapsami: {coverage['informative_signals']}/{coverage['total_signals']}.)"
        )
    else:
        verdict = _verdict_for(total_risk_score)
        recommendation = _recommendation_for(verdict, signals, coverage)
    report_token = f"FRAUD-{secrets.token_hex(3).upper()}"

    report = {
        "playlist_url": playlist_url,
        "playlist_title": inputs["playlist_title"],
        "total_risk_score": total_risk_score,
        "verdict": verdict,
        "signals": signals,
        "recommendation": recommendation,
        "report_token": report_token,
        "data_coverage": coverage,
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


# --- Gunluk zaman-serisi biriktirme (cron) ------------------------------------

def _distinct_playlist_urls() -> list[str]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT playlist_url FROM fraud_reports"
        ).fetchall()
    finally:
        conn.close()
    return [r["playlist_url"] for r in rows]


def snapshot_all_known_playlists() -> int:
    """fraud_reports'ta gorulen her DISTINCT playlist icin taze bir anlik
    goruntu alir — follower_anomaly/track_churn'un zaman-serisi ihtiyaci
    boylece gunden gune birikir (bkz. marketplace.api._fraud_snapshot_cron).

    Her playlist bagimsiz guvenceli: biri (ag hatasi, Spotify disi URL, kota
    asimi) basarisiz olursa digerleri etkilenmez. Basariyla anlik goruntusu
    alinan playlist sayisini doner (test/gozlem icin)."""
    count = 0
    for url in _distinct_playlist_urls():
        try:
            if snapshot_playlist(url) is not None:
                count += 1
        except Exception:
            continue
    return count
