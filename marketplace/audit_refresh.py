"""Takipli sarkilarin gunluk yeniden-denetimi — SEO skoru zaman-serisini
(snapshots.db) besler.

Neden gerekli: attribution (ROI atif motoru) ve skor-degisim alert'leri
(alerts.run_daily) skorun ZAMAN ICINDEKI degisimini okur. Bu seri ancak ayni
sarki tekrar tekrar denetlenirse dolar. Kullanici elle bir kez audit edince
tek nokta olusur; delta/atif icin 2+ nokta gerekir. Bu cron takipli her
sarkiyi HER GUN yeniden denetleyip snapshots.db'ye bir skor noktasi yazar —
boylece seri kendiliginden birikir.

Guarded: her audit ag erisimi (6 platform) ister; tek sarki hatasi
digerlerini etkilemez, fonksiyon asla patlamaz.
"""
from __future__ import annotations

from marketplace import tracking
from musical_seo import audit as seo_audit
from musical_seo import db as seo_db


def refresh_tracked_audits(limit: int = 2000) -> dict:
    """tracking.all_tracked(kind='song') icindeki her sarkiyi yeniden denetler
    ve snapshots.db'ye bir skor noktasi ekler (gunluk cron hedefi). Zaman-serisi
    boylece birikir; attribution + skor alert'leri gercek veriyle calisir.

    ref formati 'Sanatci - Sarki' (tracking.track ile ayni). Donus:
    {refreshed, failed, skipped}."""
    refreshed = 0
    failed = 0
    skipped = 0
    try:
        items = tracking.all_tracked(kind="song")
    except Exception:
        return {"refreshed": 0, "failed": 0, "skipped": 0, "error": "tracking_read"}
    for item in items[:limit]:
        ref = (item.get("ref") or "").strip()
        if not ref:
            skipped += 1
            continue
        try:
            result = seo_audit.run_audit(ref)
            seo_db.save(result)  # snapshots.db'ye 1 skor noktasi
            refreshed += 1
        except Exception:
            failed += 1  # ag/cozumleme hatasi -> bu sarkiyi atla, digerlerine devam
    return {"refreshed": refreshed, "failed": failed, "skipped": skipped}
