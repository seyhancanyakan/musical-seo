"""Promosyon ROI Atif Motoru: uc veri akisini birlestirip degisim-noktasi
(changepoint) bazli olay atifi ureten rapor.

Veri akislari:
    1. SEO skoru      -> musical_seo.db.history() (snapshots.db zaman serisi).
    2. Playlist yerlesimi -> marketplace.db submissions (kabul edilen/status=accepted).
    3. Radyo yayini    -> marketplace.fingerprint fp_detections (dogrulanmis calinma).

Algoritma: SEO skor serisinde 7 gunluk hareketli ortalama onceki 7 gu
penceresine gore >5 puan yukseldiginde bir "changepoint" isaretlenir. Her
changepoint deltasi, o tarihten onceki 7 gun icinde gerceklesen olaylara
(radyo > playlist > organik agirlik sirasiyla) dagitilir; dagitilamayan
kalan pay "organik" kovaya yazilir (korunum: dagitilan toplam == delta).

Tablolar (marketplace.db):
    attribution_reports: kullanici basina uretilen rapor ozeti + token.
    attribution_events:  raporun arkasindaki tekil olay-bazli atif satirlari.

Is kurali ihlalleri ValueError (aksanli Turkce) — router katmani 400'e cevirir.
Veri eksikse (snapshot/yerlesim/yayin yok) fonksiyonlar ASLA patlamaz; notr
(organik agirlikli, sifir delta) rapor doner.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import date, timedelta

from marketplace import accounts, db, pricing
from musical_seo import db as seo_db

# Olay agirliklari: radyo > playlist > organik (kalan pay).
_RADYO_WEIGHT = 3.0
_PLAYLIST_WEIGHT = 2.0
_ORGANIC_WEIGHT = 1.0
_CHANGEPOINT_MIN_DELTA = 5.0
_MOVING_AVG_DAYS = 7

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS attribution_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        track_query TEXT NOT NULL,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        total_score_delta INTEGER NOT NULL DEFAULT 0,
        breakdown TEXT NOT NULL,
        recommendation TEXT NOT NULL,
        report_token TEXT NOT NULL UNIQUE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS attribution_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL REFERENCES attribution_reports(id),
        event_type TEXT NOT NULL,
        event_date TEXT,
        source_id INTEGER,
        attributed_delta REAL NOT NULL,
        confidence REAL NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_attribution_reports_user "
    "ON attribution_reports (user_id, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_attribution_events_report "
    "ON attribution_events (report_id);",
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema (curators/submissions) hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


# --- Yardimcilar --------------------------------------------------------------

def _split_track_query(track_query: str) -> tuple[str, str]:
    """"Artist - Title" bicimini ayristirir; ayrac yoksa tumunu sanatci sayar."""
    if " - " in track_query:
        artist, _, title = track_query.partition(" - ")
        return artist.strip(), title.strip()
    return track_query.strip(), ""


def _to_date(value) -> date | None:
    """ISO tarih/zaman damgasini gun cozunurlugunde date'e cevirir. Gecersizse None."""
    if not value:
        return None
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


# --- Veri akisi 1: SEO skoru ----------------------------------------------------

def _collect_seo_series(track_query: str, start: str, end: str) -> list[dict]:
    """snapshots.db uzerinden [start, end] araligindaki SEO skor serisi.
    Kayit yoksa veya cozumleme basarisizsa bos liste (asla patlamaz)."""
    artist, title = _split_track_query(track_query)
    try:
        rows = seo_db.history(artist, title)
    except Exception:
        return []
    start_key, end_key = (start or "")[:10], (end or "")[:10]
    series = []
    for row in rows:
        created = row.get("created_at") or ""
        if not created:
            continue
        key = created[:10]
        if start_key and key < start_key:
            continue
        if end_key and key > end_key:
            continue
        score = row.get("score")
        if score is None:
            continue
        series.append({"date": created, "score": int(score)})
    return series


# --- Veri akisi 2: playlist yerlesimi --------------------------------------------

def _collect_placement_events(user_id: int, start: str, end: str) -> list[dict]:
    """Kabul edilen (accepted) gonderimler -> playlist yerlesim olaylari."""
    try:
        subs = db.list_submissions(artist_user_id=user_id, status="accepted")
    except Exception:
        return []
    start_key, end_key = (start or "")[:10], (end or "")[:10]
    events = []
    for sub in subs:
        when = sub.get("responded_at") or sub.get("created_at") or ""
        if not when:
            continue
        key = when[:10]
        if start_key and key < start_key:
            continue
        if end_key and key > end_key:
            continue
        events.append({"date": when, "type": "playlist", "source_id": sub.get("curator_id")})
    return events


# --- Veri akisi 3: radyo yayini ---------------------------------------------------

def _collect_airplay_events(user_id: int, start: str, end: str) -> list[dict]:
    """Dogrulanmis radyo yayinlari (fp_detections) -> kullanicinin siparisleriyle
    (buyer_email eslesmesi) eslenen olaylar. Tablo/modul yoksa bos liste doner."""
    user = accounts.get_user(user_id)
    email = (user or {}).get("email")
    if not email:
        return []
    try:
        from marketplace import fingerprint
        conn = fingerprint._connect()
    except Exception:
        return []
    try:
        rows = conn.execute(
            "SELECT fd.detected_at AS date, fd.station_id AS source_id "
            "FROM fp_detections fd JOIN radio_ad_orders o ON o.id = fd.order_id "
            "WHERE LOWER(o.buyer_email) = LOWER(?) "
            "AND fd.detected_at >= ? AND fd.detected_at <= ?",
            (email, start, end),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return [{"date": r["date"], "type": "radyo", "source_id": r["source_id"]} for r in rows]


# --- Changepoint tespiti + olay atifi (PURE, IO yok) ------------------------------

def _detect_changepoints(scores: list[dict]) -> list[dict]:
    """7 gunluk hareketli ortalama onceki 7 gune gore >5 puan yukselirse
    changepoint sayilir. Duz (flat) veya azalan seri -> []. Saf fonksiyon,
    birim test edilir (IO yok)."""
    parsed: list[tuple[date, float]] = []
    for s in scores:
        d = _to_date(s.get("date"))
        score = s.get("score")
        if d is not None and score is not None:
            parsed.append((d, float(score)))
    parsed.sort(key=lambda t: t[0])
    if len(parsed) < 2:
        return []

    changepoints: list[dict] = []
    last_cp_date: date | None = None
    for d, _score in parsed:
        window_start = d - timedelta(days=_MOVING_AVG_DAYS)
        prior_start = d - timedelta(days=2 * _MOVING_AVG_DAYS)
        current = [sc for pd, sc in parsed if window_start < pd <= d]
        prior = [sc for pd, sc in parsed if prior_start < pd <= window_start]
        if not current or not prior:
            continue
        cur_avg = sum(current) / len(current)
        prior_avg = sum(prior) / len(prior)
        delta = cur_avg - prior_avg
        if delta > _CHANGEPOINT_MIN_DELTA:
            # Ayni yukselisi art arda tekrar tekrar changepoint sayma.
            if last_cp_date is not None and (d - last_cp_date).days < _MOVING_AVG_DAYS:
                continue
            confidence = round(min(1.0, delta / 20.0), 2)
            changepoints.append({
                "date": d.isoformat(),
                "delta": round(delta, 2),
                "confidence": confidence,
            })
            last_cp_date = d
    return changepoints


def _attribute_to_events(changepoint: dict, events: list[dict]) -> list[dict]:
    """changepoint deltasini onceki 7 gun icindeki olaylara dagitir. Agirlik:
    radyo > playlist > organik (agirliksiz olaylar/olay yoklugu). KORUNUM:
    sum(attributed_delta) == changepoint['delta'] — kalan pay organik kovaya
    gider. Saf fonksiyon, birim test edilir (IO yok)."""
    total_delta = float(changepoint.get("delta", 0.0))
    base_confidence = float(changepoint.get("confidence", 0.5))
    cp_date = _to_date(changepoint.get("date"))

    relevant: list[tuple[dict, date]] = []
    if cp_date is not None:
        window_start = cp_date - timedelta(days=_MOVING_AVG_DAYS)
        for e in events:
            e_date = _to_date(e.get("date"))
            if e_date is not None and window_start <= e_date <= cp_date:
                relevant.append((e, e_date))

    weight_map = {"radyo": _RADYO_WEIGHT, "playlist": _PLAYLIST_WEIGHT}
    weights = [weight_map.get(e.get("type"), 1.0) for e, _ in relevant]
    total_weight = sum(weights) + _ORGANIC_WEIGHT
    max_weight = max(weights) if weights else 1.0

    results: list[dict] = []
    allocated = 0.0
    for (e, _e_date), w in zip(relevant, weights):
        share = round(total_delta * w / total_weight, 4)
        allocated += share
        results.append({
            "channel": e.get("type"),
            "source_id": e.get("source_id"),
            "event_date": e.get("date"),
            "attributed_delta": share,
            "confidence": round(min(1.0, base_confidence * (w / max_weight)), 2),
        })

    organic_share = round(total_delta - allocated, 4)
    organic_confidence = 0.3 if total_delta == 0 else round(
        max(0.1, 1.0 - min(1.0, allocated / total_delta)), 2
    )
    results.append({
        "channel": "organik",
        "source_id": None,
        "event_date": changepoint.get("date"),
        "attributed_delta": organic_share,
        "confidence": organic_confidence,
    })
    return results


def _build_recommendation(breakdown: list[dict]) -> str:
    real = [b for b in breakdown if b["channel"] != "organik" and b["attributed_delta"] > 0]
    if not real:
        return (
            "Henuz yeterli veri yok; daha fazla snapshot ve yerlesim biriktikce "
            "rapor daha isabetli olur."
        )
    best = max(real, key=lambda b: b["attributed_delta"])
    label = {"radyo": "radyo yayini", "playlist": "playlist yerlesimi"}.get(
        best["channel"], best["channel"]
    )
    return (
        f"En yuksek etkiyi {label} yaratiyor (+{best['attributed_delta']} puan); "
        "bu kanala yatirimi artirmani oneririz."
    )


# --- Rapor uretimi + kalicilik ---------------------------------------------------

def build_attribution_report(
    user_id: int, track_query: str, period_start: str, period_end: str,
) -> dict:
    """3 veri akisini birlestirip changepoint bazli atif raporu uretir ve
    kalici olarak yazar. Veri yoksa asla patlamaz — notr (organik) rapor doner."""
    scores = _collect_seo_series(track_query, period_start, period_end)
    scores_sorted = sorted(scores, key=lambda s: s.get("date") or "")
    placement_events = _collect_placement_events(user_id, period_start, period_end)
    airplay_events = _collect_airplay_events(user_id, period_start, period_end)
    events = placement_events + airplay_events

    changepoints = _detect_changepoints(scores_sorted)

    channel_totals: dict[str, dict[str, float]] = {}
    event_rows: list[dict] = []
    total_score_delta = 0.0
    for cp in changepoints:
        total_score_delta += cp["delta"]
        distributed = _attribute_to_events(cp, events)
        for item in distributed:
            channel = item.get("channel") or "organik"
            bucket = channel_totals.setdefault(
                channel, {"events": 0, "attributed_delta": 0.0}
            )
            bucket["events"] += 1
            bucket["attributed_delta"] += item["attributed_delta"]
            event_rows.append({
                "event_type": channel,
                "event_date": item.get("event_date") or cp["date"],
                "source_id": item.get("source_id"),
                "attributed_delta": item["attributed_delta"],
                "confidence": item.get("confidence", 0.0),
            })

    if not channel_totals:
        channel_totals["organik"] = {"events": 0, "attributed_delta": 0.0}

    breakdown = [
        {
            "channel": channel,
            "events": vals["events"],
            "attributed_delta": round(vals["attributed_delta"], 2),
            "roi_per_credit": round(
                vals["attributed_delta"] / pricing.ATTRIBUTION_REPORT_COST, 2
            ),
        }
        for channel, vals in sorted(
            channel_totals.items(),
            key=lambda kv: kv[1]["attributed_delta"],
            reverse=True,
        )
    ]

    recommendation = _build_recommendation(breakdown)
    report_token = f"ATTR-{secrets.token_hex(3).upper()}"
    created_at = db.now_iso()
    total_score_delta_int = int(round(total_score_delta))

    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO attribution_reports "
                "(created_at, user_id, track_query, period_start, period_end, "
                "total_score_delta, breakdown, recommendation, report_token) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    created_at, user_id, track_query, period_start, period_end,
                    total_score_delta_int, json.dumps(breakdown, ensure_ascii=False),
                    recommendation, report_token,
                ),
            )
            report_id = int(cur.lastrowid)
            for row in event_rows:
                conn.execute(
                    "INSERT INTO attribution_events "
                    "(report_id, event_type, event_date, source_id, "
                    "attributed_delta, confidence) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        report_id, row["event_type"], row["event_date"],
                        row["source_id"], row["attributed_delta"], row["confidence"],
                    ),
                )
    finally:
        conn.close()

    return {
        "track_query": track_query,
        "period": {"start": period_start, "end": period_end},
        "total_score_delta": total_score_delta_int,
        "breakdown": breakdown,
        "recommendation": recommendation,
        "report_token": report_token,
    }


def get_report(token: str) -> dict | None:
    """Token ile tekil rapor + arkasindaki olay-bazli atif satirlari."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM attribution_reports WHERE report_token = ?", (token,)
        ).fetchone()
        if row is None:
            return None
        report = dict(row)
        report["breakdown"] = json.loads(report["breakdown"]) if report.get("breakdown") else []
        events = conn.execute(
            "SELECT * FROM attribution_events WHERE report_id = ?", (report["id"],)
        ).fetchall()
        report["events"] = [dict(e) for e in events]
        return report
    finally:
        conn.close()


def reports_for_user(user_id: int) -> list[dict]:
    """Kullanicinin gecmis raporlari, en yeni once."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM attribution_reports WHERE user_id = ? "
            "ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    result = []
    for row in rows:
        r = dict(row)
        r["breakdown"] = json.loads(r["breakdown"]) if r.get("breakdown") else []
        result.append(r)
    return result
