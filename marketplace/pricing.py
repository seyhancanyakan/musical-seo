"""Fiyatlandirma cekirdegi — kurator kademeleri, gonderim maliyeti, paketler.

Tamami saf fonksiyon/sabit: network ve DB yok, dogrudan unit test edilir.
Gelir modeli ozet:
    - Kurator kademesi (bronze..platinum) eristigi kitleye gore kredi maliyeti
      belirler (reach-bazli fiyat). Platinum "elit": kanitlanmis performans
      (response_rate/success_rate) sart.
    - Playlist-disi profesyoneller (radyo/medya/label/...) sabit premium fiyat.
    - Garanti: ek ucret karsiligi SLA kacarsa 2x kredi iadesi.
    - One cikan (rush): +1 kredi, 48 saat SLA, inbox'ta ust sira, kurator bonusu.
    - Artist Pro: aylik kredi tahsisi + maliyet indirimi + 48s SLA.
"""
from __future__ import annotations

import math

# --- Kurator kademeleri ----------------------------------------------------

TIERS = ("bronze", "silver", "gold", "platinum")
TIER_COST = {"bronze": 1, "silver": 2, "gold": 3, "platinum": 4}

SILVER_MIN_QUALITY = 40.0
SILVER_MIN_FANS = 1_000
GOLD_MIN_QUALITY = 60.0
GOLD_MIN_FANS = 2_500
ELITE_MIN_RESPONSE_RATE = 80   # platinum icin kanitlanmis disiplin
ELITE_MIN_SUCCESS_RATE = 25    # platinum icin kanitlanmis kabul orani

# Playlist-disi profesyonel erisimi (radyo/medya/label/menajer/booker/dj/
# mentor/sync): yerel pazarda rekabetsiz nis -> sabit premium fiyat.
PRO_TYPE_COST = 8

# --- Gonderim eklentileri ---------------------------------------------------

GUARANTEE_RATE = 0.5           # ek ucret: taban maliyetin yarisi (yukari yuvarla)
GUARANTEE_REFUND_FACTOR = 2    # SLA kacarsa toplam maliyetin 2 kati iade
PRIORITY_SURCHARGE = 1         # one cikan gonderim ek kredisi
PRIORITY_SLA_HOURS = 48
PRIORITY_BONUS_USD = 0.5       # one cikan gonderimi yanitlayan kurator bonusu

# --- Artist Pro aboneligi ---------------------------------------------------

PRO_MONTHLY_CREDITS = 15
PRO_SLA_HOURS = 48
PRO_PRICE_TRY = 399            # aylik (odeme entegrasyonu gelene kadar bilgi amacli)

# --- Kredi paketleri (self-servis talep; odeme pilotta manuel) ---------------

PACKAGES = {
    "baslangic": {"credits": 5, "price_try": 149, "label": "Baslangic"},
    "buyume": {"credits": 20, "price_try": 499, "label": "Buyume"},
    "studyo": {"credits": 50, "price_try": 999, "label": "Studyo"},
}

# --- Premium urunler ---------------------------------------------------------

CERTIFICATE_COST = 1           # dogrulanmis yerlesim sertifikasi (ilk uretim)
IMPACT_REPORT_COST = 1         # premium etki raporu (pro'ya ucretsiz)
EPK_COST = 2                   # elektronik basin kiti (pro'ya ucretsiz)
AUTOPILOT_FEE = 1              # otopilot servis ucreti (pro'ya ucretsiz)
READY_BADGE_MIN_SCORE = 70.0   # "yayina hazir" rozeti esigi

# --- Kurator odemeleri --------------------------------------------------------

PAYOUT_MIN_USD = 20.0          # standart (ucretsiz) payout esigi
INSTANT_PAYOUT_FEE_RATE = 0.12 # aninda payout kesintisi

# --- Dinleme kapisi ------------------------------------------------------------

LISTEN_GATE_SECONDS = 90       # acilis -> yanit arasi asgari sure (dinleme kaniti)


def curator_tier(
    quality_score: float, fans: int,
    response_rate: int | None = None, success_rate: int | None = None,
) -> str:
    """Reach + kanitlanmis performans -> kademe.

    Platinum SADECE yeterli gecmisi olan kuratore verilir (None = veri yok
    = platinum olamaz); yeni kurator en fazla gold'dan baslar.
    """
    gold_base = quality_score >= GOLD_MIN_QUALITY and fans >= GOLD_MIN_FANS
    if (
        gold_base
        and response_rate is not None and response_rate >= ELITE_MIN_RESPONSE_RATE
        and success_rate is not None and success_rate >= ELITE_MIN_SUCCESS_RATE
    ):
        return "platinum"
    if gold_base:
        return "gold"
    if quality_score >= SILVER_MIN_QUALITY or fans >= SILVER_MIN_FANS:
        return "silver"
    return "bronze"


def submission_cost(
    tier: str, curator_type: str = "playlist", pro_artist: bool = False,
) -> int:
    """Taban gonderim maliyeti (garanti/rush haric).

    Pro tur (radyo/medya/...) sabit premium; Artist Pro 1 kredi indirim alir
    ama taban asla 1'in altina dusmez.
    """
    if curator_type != "playlist":
        cost = PRO_TYPE_COST
    else:
        cost = TIER_COST.get(tier, 1)
    if pro_artist and cost > 1:
        cost -= 1
    return cost


def guarantee_surcharge(base_cost: int) -> int:
    return max(1, math.ceil(base_cost * GUARANTEE_RATE))


def total_submission_cost(
    base_cost: int, guaranteed: bool = False, priority: bool = False,
) -> int:
    total = base_cost
    if guaranteed:
        total += guarantee_surcharge(base_cost)
    if priority:
        total += PRIORITY_SURCHARGE
    return total


def refund_amount(cost_credits: int, guaranteed: bool) -> int:
    """SLA kacirilinca iade: normal = odedigi, garantili = 2 kati."""
    return cost_credits * GUARANTEE_REFUND_FACTOR if guaranteed else cost_credits


def sla_hours(priority: bool = False, pro_artist: bool = False,
              default_hours: int = 72) -> int:
    if priority:
        return PRIORITY_SLA_HOURS
    if pro_artist:
        return PRO_SLA_HOURS
    return default_hours


def instant_payout_fee(amount_usd: float) -> float:
    return round(amount_usd * INSTANT_PAYOUT_FEE_RATE, 2)
