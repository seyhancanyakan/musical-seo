"""Optimum Yayin Tarihi Optimizatoru - yayin oncesi hazirlik + hedef tarih
rekabet analizi.

4 sinyal birlestirilip tavsiye uretilir:
    1. signal_readiness            - audit.run_audit uzerinden metadata/
                                      gorunurluk hazirligi (0-100).
    2. signal_keyword_competition   - autocomplete doluluguyla anahtar kelime
                                      rekabeti (dusuk/orta/yuksek).
    3. signal_competitor_releases   - hedef tarih penceresinde MusicBrainz'de
                                      yayinlanan/yayinlanacak diger kayitlar.
    4. signal_day_optimization      - saf tarih matematigi: global muzik
                                      endustrisi standardi Cuma yayin.

Sinyal fonksiyonlari agdan bagimsiz calisabilir: kaynak erisilemez/hata
verirse CRASH ETMEZ, notr deger doner (audit.py'deki "asla exception firlatma
disina kaynagi sizdirma" ilkesiyle ayni). advise_release() dorduneu birlestirip
tavsiye (hazir/hazirlan/ertele), onerilen tarih ve aksiyon plani uretir.

Rapor persistansi (marketplace.db, release_timing_reports tablosu):
save_report/get_report/reports_for_user API katmanini ince tutmak icin burada.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timedelta

from marketplace import db

from musical_seo import audit
from musical_seo.sources import autocomplete, musicbrainz

_DATE_FMT = "%Y-%m-%d"

READINESS_THRESHOLD = 70
COMPETITION_LOW_CROWDING = 0.34   # bu esigin altinda "low" rekabet
COMPETITION_HIGH_CROWDING = 0.67  # bu esigin ustunde "high" rekabet

COMPETITOR_HIGH_COUNT = 10  # pencere icinde bu kadar rakip yayin -> yuksek risk
COMPETITOR_MEDIUM_COUNT = 3

_MB_BASE = "https://musicbrainz.org/ws/2"
_MB_HEADERS = {"User-Agent": "musical-seo/0.1 (https://github.com/musical-seo; release-timing)"}
_MB_TIMEOUT = 15

_SCHEMA = """
CREATE TABLE IF NOT EXISTS release_timing_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    track_query TEXT NOT NULL,
    target_date TEXT NOT NULL,
    verdict TEXT NOT NULL,
    recommended_date TEXT NOT NULL,
    report_json TEXT NOT NULL,
    report_token TEXT NOT NULL UNIQUE
);
"""


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    conn.execute(_SCHEMA)
    return conn


def _parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime((date_str or "").strip(), _DATE_FMT)
    except (ValueError, TypeError):
        raise ValueError(
            f"Gecersiz hedef tarih formati (YYYY-MM-DD bekleniyor): {date_str!r}"
        )


def validate_date_format(date_str: str) -> None:
    """API katmaninin kredi dusmeden ONCE ucretsiz format kontrolu icin."""
    _parse_date(date_str)


# --- Sinyal 1: yayin oncesi hazirlik -----------------------------------------

def signal_readiness(track_query: str) -> dict:
    """audit.run_audit skoruna dayanir. Sarki bulunamazsa / kaynaklar
    erisilemezse notr (50) skorle devam eder, crash etmez."""
    try:
        result = audit.run_audit(track_query)
        findings = [
            {
                "severity": f.severity,
                "category": f.category,
                "message": f.message,
                "action": f.action,
            }
            for f in result.findings
        ]
        fixable_issues = [
            f.message for f in result.findings if f.severity in ("critical", "warn")
        ]
        return {
            "score": result.score,
            "findings": findings,
            "fixable_issues": fixable_issues,
        }
    except Exception:
        return {"score": 50, "findings": [], "fixable_issues": []}


# --- Sinyal 2: anahtar kelime rekabeti ---------------------------------------

def signal_keyword_competition(track_query: str) -> dict:
    """Autocomplete onerilerinin ne kadari sorgudaki kelimelerle alakasiz
    (=rakip/alternatif icerik doldurmus) buna gore rekabet seviyesi. Ag hatasi
    / bos sonuc -> notr orta rekabet."""
    try:
        suggestions = autocomplete.suggest(track_query, engine="google")
    except Exception:
        suggestions = []

    if not suggestions:
        return {"competition": "medium", "score": 0.5, "alternatives": []}

    own_terms = {t.casefold() for t in track_query.split() if t.strip()}
    alternatives = [
        s for s in suggestions
        if not any(term and term in s.casefold() for term in own_terms)
    ]
    crowding = round(len(alternatives) / max(len(suggestions), 1), 2)

    if crowding < COMPETITION_LOW_CROWDING:
        competition = "low"
    elif crowding < COMPETITION_HIGH_CROWDING:
        competition = "medium"
    else:
        competition = "high"

    return {
        "competition": competition,
        "score": crowding,
        "alternatives": alternatives[:5],
    }


# --- Sinyal 3: rakip yayinlar (hedef tarih penceresi) ------------------------

def _mb_search_releases_window(start: str, end: str) -> list[dict]:
    """MusicBrainz release arama: [start TO end] tarih penceresi. Anahtar
    gerekmez. Hata/timeout -> bos liste (cagiran taraf notr davranir)."""
    import requests

    query = f"date:[{start} TO {end}]"
    r = requests.get(
        f"{_MB_BASE}/release",
        params={"query": query, "fmt": "json", "limit": 25},
        headers=_MB_HEADERS,
        timeout=_MB_TIMEOUT,
    )
    if r.status_code != 200:
        return []
    return r.json().get("releases") or []


def signal_competitor_releases(target_date: str, window_days: int = 7) -> dict:
    """Hedef tarih etrafindaki +-window_days penceresinde MusicBrainz'e
    kayitli yayin sayisi. MusicBrainz erisilemezse / hata olursa notr bos
    sonuc (risk yok varsayilir) - crash etmez."""
    dt = _parse_date(target_date)
    start = (dt - timedelta(days=window_days)).strftime(_DATE_FMT)
    end = (dt + timedelta(days=window_days)).strftime(_DATE_FMT)

    try:
        releases = _mb_search_releases_window(start, end)
    except Exception:
        return {"competitor_count": 0, "competitors": [], "risk": "low"}

    competitors = []
    for rel in releases:
        credits = rel.get("artist-credit") or []
        artist_name = None
        if credits and isinstance(credits[0], dict):
            artist_name = (credits[0].get("artist") or {}).get("name") or credits[0].get("name")
        competitors.append({
            "title": rel.get("title"),
            "artist": artist_name,
            "date": rel.get("date"),
        })

    count = len(competitors)
    if count >= COMPETITOR_HIGH_COUNT:
        risk = "high"
    elif count >= COMPETITOR_MEDIUM_COUNT:
        risk = "medium"
    else:
        risk = "low"

    return {
        "competitor_count": count,
        "competitors": competitors[:10],
        "risk": risk,
    }


# --- Sinyal 4: gun optimizasyonu (saf tarih matematigi, AG YOK) --------------

def signal_day_optimization(target_date: str, market: str = "TR") -> dict:
    """Global muzik endustrisi standardi: Cuma yayin (DSP'lerin haftalik
    listeleri Cuma guncellenir). Turkiye pazarinda da ayni kural gecerlidir.
    Saf tarih matematigi - ag cagrisi yok."""
    dt = _parse_date(target_date)
    weekday = dt.weekday()  # Monday=0 ... Friday=4 ... Sunday=6

    if weekday == 4:
        return {
            "recommended_day": "Friday",
            "reason": "Hedef tarih zaten Cuma - global muzik endustrisi standardi",
            "score": 1.0,
            "nearest_friday": dt.strftime(_DATE_FMT),
        }

    days_forward = (4 - weekday) % 7   # ileri giderek en yakin Cuma
    days_backward = (weekday - 4) % 7  # geri giderek en yakin Cuma
    if days_backward <= days_forward:
        offset = -days_backward
    else:
        offset = days_forward
    nearest_friday = dt + timedelta(days=offset)
    distance = abs(offset)
    score = max(0.0, round(1.0 - distance * 0.15, 2))

    return {
        "recommended_day": "Friday",
        "reason": (
            f"Hedef tarih {dt.strftime('%A')} - global standart Cuma yayin icin "
            f"en yakin Cuma {nearest_friday.strftime(_DATE_FMT)} ({distance} gun fark)"
        ),
        "score": score,
        "nearest_friday": nearest_friday.strftime(_DATE_FMT),
    }


# --- Birlesik tavsiye ---------------------------------------------------------

def advise_release(track_query: str, target_date: str) -> dict:
    """4 sinyali birlestirip nihai tavsiyeyi uretir.

    Verdict kurali:
        - rakip yayin riski yuksek -> "ertele" (cakisan haftadan kac)
        - hazirlik skoru esikin altinda -> "hazirlan" (once eksikleri gider)
        - hazirlik yeterli + rekabet dusuk -> "hazir"
        - digerleri -> "hazirlan" (temkinli varsayilan)
    """
    validate_date_format(target_date)  # bozuk tarihte erken ValueError

    readiness = signal_readiness(track_query)
    competition = signal_keyword_competition(track_query)
    competitors = signal_competitor_releases(target_date)
    day = signal_day_optimization(target_date)

    readiness_score = readiness["score"]
    competitor_risk_high = competitors["risk"] == "high"
    competition_low = competition["competition"] == "low"

    if competitor_risk_high:
        verdict = "ertele"
    elif readiness_score < READINESS_THRESHOLD:
        verdict = "hazirlan"
    elif readiness_score >= READINESS_THRESHOLD and competition_low:
        verdict = "hazir"
    else:
        verdict = "hazirlan"

    recommended_date = day["nearest_friday"]
    if competitor_risk_high:
        # cakisan haftadan kacmak icin bir sonraki Cuma'ya kaydir
        base = _parse_date(recommended_date)
        recommended_date = (base + timedelta(days=7)).strftime(_DATE_FMT)

    action_plan: list[str] = []
    action_plan.extend(readiness["fixable_issues"])
    if competition["competition"] != "low":
        action_plan.append(
            "Anahtar kelime rekabeti yuksek - alternatif basliklandirma/marka "
            "aramasi buyutmeyi dusun"
        )
    if competitor_risk_high:
        action_plan.append(
            f"{competitors['competitor_count']} rakip yayin hedef haftada - "
            f"tarihi {recommended_date} olarak kaydirmayi dusun"
        )
    if recommended_date != target_date and not competitor_risk_high:
        action_plan.append(f"Onerilen yayin tarihi: {recommended_date} (Cuma)")
    if not action_plan:
        action_plan.append("Ek aksiyon gerekmiyor - yayina hazir")

    projected_score = round(
        (readiness_score + day["score"] * 100 + (1 - competition["score"]) * 100) / 3
    )

    return {
        "track_query": track_query,
        "target_date": target_date,
        "readiness": readiness,
        "competition": competition,
        "competitors": competitors,
        "day": day,
        "overall_verdict": verdict,
        "recommended_date": recommended_date,
        "action_plan": action_plan,
        "projected_score": projected_score,
        "report_token": f"TIME-{secrets.token_hex(3).upper()}",
    }


# --- Rapor persistansi (marketplace.db) --------------------------------------

def save_report(user_id: int, advice: dict) -> dict:
    """advise_release() ciktisini kalici kaydeder (paylasilabilir token)."""
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO release_timing_reports "
                "(created_at, user_id, track_query, target_date, verdict, "
                " recommended_date, report_json, report_token) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    db.now_iso(),
                    user_id,
                    advice["track_query"],
                    advice["target_date"],
                    advice["overall_verdict"],
                    advice["recommended_date"],
                    json.dumps(advice, ensure_ascii=False),
                    advice["report_token"],
                ),
            )
        return advice
    finally:
        conn.close()


def get_report(token: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT report_json FROM release_timing_reports WHERE report_token = ?",
            (token,),
        ).fetchone()
        return json.loads(row["report_json"]) if row else None
    finally:
        conn.close()


def reports_for_user(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT created_at, track_query, target_date, verdict, "
            "recommended_date, report_token FROM release_timing_reports "
            "WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
