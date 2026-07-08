"""Retention alert motoru: kullanici geri donmek icin sebep bulsun.

Acı gercek (docs/PROGRAMATIK_SEO_WORKFLOW.md SS9): insanlar ucretsiz gelir,
bir kez bakar, gider. Cogu SEO araci burada olur. Bu modul TAKIP EDILEN
varliklarda (cover avi, fraud raporu, SEO skoru, rakip) degisiklik oldugunda
kullaniciya somut bir DONME sebebi ureten gunluk tarama motorudur.

Alert turleri:
    cover       - cover_hunter'da yeni 'pending' aday bulundu (hunt basina).
    fraud       - takip edilen playliste dair riskli/cok_riskli/sahte adli
                  rapor (fraud_forensics).
    score       - SEO skoru degisti (musical_seo.db.history delta) - best-effort,
                  asagida run_daily() icinde neden HENUZ taranmadigi belgeli.
    competitor  - rakip yeni cikti / daha populer - stub girdili saf fonksiyon,
                  gercek veri kaynagi gelene kadar run_daily bunu CAGIRMAZ.

Idempotentlik: alert_log tablosu (user_id, alert_type, ref) UNIQUE index'i ile
ayni olayin iki kez uretilmesini engeller (run_daily gunde birden fazla kez
calisirsa bile ayni degisiklik icin tekrar bildirim gitmez). Bildirimler
marketplace.growth.add_notification uzerinden (mevcut notifications tablosuna)
push edilir - bu cagri GUARDED'dir: growth API'si patlarsa alert_log kaydi
yine de kalir (sent=0), run_daily hicbir zaman cokmez.

Her kaynak (cover/fraud/score/competitor) run_daily() icinde BAGIMSIZ
try/except icindedir - bir kaynagin hatasi digerlerini durdurmaz.
"""
from __future__ import annotations

import sqlite3

from marketplace import cover_hunter, db, fraud_forensics, growth

RISKY_FRAUD_VERDICTS = ("riskli", "cok_riskli", "sahte")
_FRAUD_SCAN_LIMIT = 500

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS alert_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        alert_type TEXT NOT NULL,
        ref TEXT NOT NULL,
        message TEXT NOT NULL,
        sent INTEGER NOT NULL DEFAULT 0
    );
    """,
    # (user_id, alert_type, ref) UNIQUE -> ayni olay iki kez loglanamaz/gonderilemez.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_log_dedupe "
    "ON alert_log (user_id, alert_type, ref);",
    "CREATE INDEX IF NOT EXISTS idx_alert_log_user ON alert_log (user_id, id);",
]


def _connect() -> sqlite3.Connection:
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


# --- Saf(a yakin) alert builder'lari — network/DB yok, dogrudan test edilir --

def build_cover_alert(user_id: int, hunt_ref: str, new_count: int) -> dict:
    """Bir cover avinda (hunt_ref) su an pending durumda new_count aday var.

    ref = "{hunt_ref}:{new_count}" -> pending sayisi ARTMADIKCA ayni ref
    tekrar uretilir, alert_log bunu idempotent olarak atlar; sayi artinca
    yeni bir ref (dolayisiyla yeni bir bildirim) dogar.
    """
    return {
        "user_id": user_id,
        "alert_type": "cover",
        "ref": f"{hunt_ref}:{new_count}",
        "message": f"Şarkının izinsiz cover'ı bulundu: {new_count} yeni aday",
    }


def build_fraud_alert(
    user_id: int, playlist_title: str, verdict: str, ref: str | None = None,
) -> dict:
    """Takip edilen bir playlist icin adli analiz riskli/cok_riskli/sahte cikti.

    ref verilmezse (playlist_title, verdict) ciftinden turetilir; run_daily
    gercek rapor kimligini (fraud_reports.id) ref olarak gecer -- boylece her
    YENI rapor kendi basina bir kez bildirilir.
    """
    label = playlist_title or "Playlist"
    return {
        "user_id": user_id,
        "alert_type": "fraud",
        "ref": ref or f"{label}:{verdict}",
        "message": f"Takip ettiğin playlist'te şüpheli aktivite: {label} ({verdict})",
    }


def build_score_alert(
    user_id: int, track_query: str, old_score: float, new_score: float,
) -> dict:
    """SEO skoru old_score -> new_score degisti (dusus ya da yukselis)."""
    return {
        "user_id": user_id,
        "alert_type": "score",
        "ref": f"{track_query}:{old_score:.0f}->{new_score:.0f}",
        "message": f"SEO skorun {old_score:.0f}→{new_score:.0f} değişti ({track_query})",
    }


def build_competitor_alert(user_id: int, competitor: str, delta_pct: float) -> dict:
    """Stub: rakip takibi icin gercek veri kaynagi henuz yok (run_daily bunu
    su an CAGIRMIYOR); fonksiyon ileride entegre edilecek girdi icin hazir."""
    return {
        "user_id": user_id,
        "alert_type": "competitor",
        "ref": f"{competitor}:{delta_pct:.0f}",
        "message": f"Rakip {competitor} yeni çıktı, %{delta_pct:.0f} daha popüler",
    }


# --- alert_log idempotent kayit + growth notifications push (guarded) -------

def _record_alert(alert: dict) -> bool:
    """alert_log'a idempotent kayit dener; zaten varsa (unique index ihlali)
    False doner -- yeni bildirim uretilmedi demektir. Yeni kayitta,
    growth.add_notification uzerinden kullaniciya bildirim de push edilir;
    bu cagri basarisiz olursa alert_log kaydi yine de kalir (sent=0)."""
    conn = _connect()
    try:
        with conn:
            try:
                conn.execute(
                    "INSERT INTO alert_log "
                    "(created_at, user_id, alert_type, ref, message, sent) "
                    "VALUES (?, ?, ?, ?, ?, 0)",
                    (
                        db.now_iso(), alert["user_id"], alert["alert_type"],
                        alert["ref"], alert["message"],
                    ),
                )
            except sqlite3.IntegrityError:
                return False  # (user_id, alert_type, ref) zaten loglanmis
    finally:
        conn.close()

    sent = False
    try:
        sent = bool(growth.add_notification(
            alert["user_id"], alert["alert_type"], alert["message"],
            dedupe_same_day=False,  # idempotentlik zaten alert_log'da saglaniyor
        ))
    except Exception:
        sent = False  # growth API'si patlarsa alert_log kaydi yine de kalir

    if sent:
        conn = _connect()
        try:
            with conn:
                conn.execute(
                    "UPDATE alert_log SET sent = 1 "
                    "WHERE user_id = ? AND alert_type = ? AND ref = ?",
                    (alert["user_id"], alert["alert_type"], alert["ref"]),
                )
        except Exception:
            pass
        finally:
            conn.close()
    return True


# --- Kaynak tarayicilari (her biri kendi semasini kurar, sonuc bulamazsa []) -

def _pending_cover_counts() -> list[tuple[int, int, int]]:
    """(hunt_id, user_id, pending_count) -- en az 1 pending adayi olan avlar.
    cover_hunter._connect() kullanilir ki cover_hunts/cover_candidates semasi
    hic calismamis bir DB'de bile hazir olsun (bos liste doner, hata degil)."""
    conn = cover_hunter._connect()
    try:
        rows = conn.execute(
            """
            SELECT ch.id AS hunt_id, ch.user_id AS user_id,
                   COUNT(*) AS pending_count
            FROM cover_candidates cc
            JOIN cover_hunts ch ON ch.id = cc.hunt_id
            WHERE cc.status = 'pending'
            GROUP BY ch.id
            """
        ).fetchall()
    finally:
        conn.close()
    return [(r["hunt_id"], r["user_id"], r["pending_count"]) for r in rows]


def _risky_fraud_reports(limit: int = _FRAUD_SCAN_LIMIT) -> list[tuple[int, int, str, str]]:
    """(report_id, user_id, playlist_title, verdict) -- sahibi bilinen
    (user_id NOT NULL) riskli/cok_riskli/sahte raporlar, en yeniden eskiye."""
    conn = fraud_forensics._connect()
    try:
        placeholders = ",".join("?" * len(RISKY_FRAUD_VERDICTS))
        rows = conn.execute(
            f"""
            SELECT id, user_id, playlist_title, verdict
            FROM fraud_reports
            WHERE user_id IS NOT NULL AND verdict IN ({placeholders})
            ORDER BY id DESC
            LIMIT ?
            """,
            (*RISKY_FRAUD_VERDICTS, limit),
        ).fetchall()
    finally:
        conn.close()
    return [(r["id"], r["user_id"], r["playlist_title"] or "", r["verdict"]) for r in rows]


# --- Gunluk orkestrasyon ------------------------------------------------------

def run_daily() -> dict:
    """Gunluk retention taramasi (cron: bkz marketplace/api.py). Her kaynagi
    tarar, HENUZ bildirilmemis degisiklikler icin alert uretir + kaydeder +
    growth bildirimlerine push eder. Hicbir kaynak/adim run_daily'yi
    cokertmez (her biri kendi try/except icinde). Doner: {generated, by_type}.
    """
    generated = 0
    by_type: dict[str, int] = {}

    def _bump(alert_type: str) -> None:
        nonlocal generated
        generated += 1
        by_type[alert_type] = by_type.get(alert_type, 0) + 1

    # --- 1) Cover: pending aday sayisi degisen avlar -------------------------
    try:
        for hunt_id, user_id, pending_count in _pending_cover_counts():
            if not pending_count:
                continue
            alert = build_cover_alert(user_id, str(hunt_id), pending_count)
            if _record_alert(alert):
                _bump("cover")
    except Exception:
        pass  # tek kaynagin hatasi run_daily'yi durdurmasin

    # --- 2) Fraud: riskli/cok_riskli/sahte raporlar --------------------------
    try:
        for report_id, user_id, playlist_title, verdict in _risky_fraud_reports():
            alert = build_fraud_alert(user_id, playlist_title, verdict, ref=str(report_id))
            if _record_alert(alert):
                _bump("fraud")
    except Exception:
        pass

    # --- 3) Score: SEO skoru degisti -----------------------------------------
    # TODO(best-effort): musical_seo.db.history(artist, title) gecmis skor
    # verisi sunuyor ve growth.detect_score_drops zaten TEK bir kullanicinin
    # takip ettigi parcalarda DUSUS'u tespit ediyor. Ama burada TUM
    # kullanicilar icin toplu tarama yapabilmek icin "hangi kullanici hangi
    # (artist, title)'i takip ediyor" iliskisini veren bir
    # accounts.list_users()/kullanici bazli takip listesi marketplace/
    # accounts.py'da HENUZ yok (submissions.artist_user_id tek basina yeterli
    # degil - skor artislarini da yakalamak icin tum kullanicilarin butun
    # gecmis parcalarini taramak gerekir). Uydurma/varsayimsal veri uretmek
    # yerine burada HICBIR ALERT URETILMIYOR. build_score_alert() yukarida
    # saf/test edilebilir sekilde HAZIR; ilerideki entegrasyon sadece bu
    # dongude bir "for user_id in <kullanici+takip listesi>" eklemeli.

    # --- 4) Competitor: rakip cikisi/populerlik degisimi ---------------------
    # TODO(best-effort): rakip takibi icin veri kaynagi (rakip sanatci listesi
    # + periyodik popularite olcumu) henuz baglanmadi. build_competitor_alert()
    # yukarida saf fonksiyon olarak HAZIR (stub girdili) ama gercek veri
    # gelene kadar run_daily bunu CAGIRMIYOR -- uydurma alert olusturulmuyor.

    return {"generated": generated, "by_type": by_type}


# --- Sorgu yardimcilari --------------------------------------------------------

def pending_alerts(user_id: int) -> list[dict]:
    """Henuz growth bildirimine push edilememis (sent=0) uyarilar (en yeniden
    eskiye). 'Guarded push' basarisiz olduysa burada gorunur - tekrar
    denenebilir bir kuyruk gibi okunabilir."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM alert_log WHERE user_id = ? AND sent = 0 "
            "ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def alert_history(user_id: int, limit: int = 50) -> list[dict]:
    """Kullanicinin son uyari gecmisi (sent olsun/olmasin), en yeniden eskiye."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM alert_log WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
