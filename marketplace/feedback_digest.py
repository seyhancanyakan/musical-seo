"""Geri bildirim sentez raporu — sanatcinin aldigi kurator geri bildirimlerini
tek raporda ozetler: anahtar kelime frekansi, tema tespiti, kabul/firsat
istatistikleri. Ucret DIGEST_COST kredi (pro ucretsiz, bkz. premium._charge_unless_pro
deseni). Is kurali ihlalleri ValueError (Turkce) — API katmani 400'e cevirir.

Tablolar (marketplace.db): feedback_digests(id, created_at, user_id, digest_json).
"""
from __future__ import annotations

import json
import re
from collections import Counter

from marketplace import accounts, db, pricing, service

DIGEST_COST = 1           # rapor uretim ucreti (pro'ya ucretsiz)
MIN_FEEDBACKS = 2         # rapor icin gereken en az dolu geri bildirim sayisi
TOP_KEYWORDS_LIMIT = 10
MIN_KEYWORD_LEN = 4
THEME_MIN_MENTIONS = 2    # tema aksiyonu icin en az kac FARKLI feedback'te gecmeli

# Not: service.fold() Turkce aksanlari NFD ile ayristirip birlesik isaretleri
# atar (ör. 'ç'->'c', 'ö'->'o'); 'ı' (noktasiz i) atomik kaldigindan kelime
# regex'ine dahil edilir.
_WORD_RE = re.compile(r"[a-zı]+")

TR_STOPWORDS = {
    "ve", "ile", "bir", "bu", "su", "o", "cok", "daha", "en", "icin", "ama",
    "fakat", "ancak", "lakin", "gibi", "de", "da", "ki", "ne", "mi", "mu",
    "mı", "ya", "yada", "ise", "yani", "sanki", "hem", "veya", "boyle",
    "oyle", "ben", "sen", "biz", "siz", "onlar", "sonra", "once", "simdi",
    "hala", "artik", "belki", "tabii", "tabi", "var", "yok",
}

THEME_ACTIONS = {
    "intro": "Intro suresini kisaltmayi dene — birden fazla kurator giristen bahsetti",
    "mix": "Mix/mastering gozden gecir",
    "vokal": "Vokal katmanlarini one cikar",
    "tempo": "Tempo/enerji uyumu playlist secimini etkiliyor",
    "nakarat": "Nakarat guclu — pitch mesajlarinda vurgula",
    "sure": "Parca suresi konusuldu — radio edit dusun",
}

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS feedback_digests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        digest_json TEXT NOT NULL
    );
    """,
]


def _connect():
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


def _keywords(text: str) -> list[str]:
    """Fold + stopword filtre + uzunluk esigi (>=4) ile kelime listesi doner."""
    folded = service.fold(text)
    return [
        w for w in _WORD_RE.findall(folded)
        if len(w) >= MIN_KEYWORD_LEN and w not in TR_STOPWORDS
    ]


def _tier_breakdown(feedbacks: list[dict]) -> dict[str, dict]:
    """Kurator kademesine gore kabul kirilimi (opsiyonel bilgi — kurator
    kaydi bulunamazsa ilgili gonderim sessizce atlanir)."""
    breakdown: dict[str, dict] = {}
    for sub in feedbacks:
        curator = db.get_curator(sub["curator_id"])
        if curator is None:
            continue
        tier = pricing.curator_tier(
            curator.get("quality_score") or 0.0, curator.get("fans") or 0
        )
        entry = breakdown.setdefault(tier, {"total": 0, "accepted": 0})
        entry["total"] += 1
        if sub["status"] == "accepted":
            entry["accepted"] += 1
    return breakdown


def synthesize(user: dict) -> dict:
    """Kullanicinin dolu geri bildirimlerinden sentez raporu uretir, kaydeder
    ve doner. MIN_FEEDBACKS alti dolu geri bildirim varsa ValueError (ucret
    bu durumda ALINMAZ). Pro kullaniciya ucretsiz."""
    subs = db.list_submissions(artist_user_id=user["id"])
    feedbacks = [s for s in subs if (s.get("feedback") or "").strip()]
    if len(feedbacks) < MIN_FEEDBACKS:
        raise ValueError(
            f"Yeterli geri bildirim yok (en az {MIN_FEEDBACKS} dolu geri "
            "bildirim gerekli)"
        )

    if not accounts.is_pro(user):
        accounts.charge_credits(user["id"], DIGEST_COST, "feedback_digest")

    total = len(feedbacks)
    accepted = sum(1 for s in feedbacks if s["status"] == "accepted")
    acceptance_rate = round(accepted / total * 100, 1)

    opportunity_breakdown = dict(
        Counter(
            s["opportunity_kind"] for s in feedbacks if s.get("opportunity_kind")
        )
    )

    word_counter: Counter = Counter()
    theme_counts: Counter = Counter()
    for sub in feedbacks:
        text = sub["feedback"]
        word_counter.update(_keywords(text))
        folded_text = service.fold(text)
        for keyword in THEME_ACTIONS:
            if keyword in folded_text:
                theme_counts[keyword] += 1

    top_keywords = [
        {"keyword": word, "count": count}
        for word, count in sorted(
            word_counter.items(), key=lambda kv: (-kv[1], kv[0])
        )[:TOP_KEYWORDS_LIMIT]
    ]

    themes = sorted(
        (
            {"keyword": keyword, "mentions": count, "action": THEME_ACTIONS[keyword]}
            for keyword, count in theme_counts.items()
            if count >= THEME_MIN_MENTIONS
        ),
        key=lambda t: (-t["mentions"], t["keyword"]),
    )

    created_at = db.now_iso()
    digest = {
        "stats": {
            "total_feedback": total,
            "accepted": accepted,
            "acceptance_rate": acceptance_rate,
            "tier_breakdown": _tier_breakdown(feedbacks),
        },
        "top_keywords": top_keywords,
        "themes": themes,
        "opportunity_breakdown": opportunity_breakdown,
        "created_at": created_at,
    }

    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO feedback_digests (created_at, user_id, digest_json) "
                "VALUES (?, ?, ?)",
                (created_at, user["id"], json.dumps(digest, ensure_ascii=False)),
            )
    finally:
        conn.close()
    return digest


def latest(user_id: int) -> dict | None:
    """Kullanicinin son sentez raporunu getirir; hic uretilmemisse None."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT digest_json FROM feedback_digests WHERE user_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        return json.loads(row["digest_json"]) if row else None
    finally:
        conn.close()
