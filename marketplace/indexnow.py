"""IndexNow ile yeni programatik SEO sayfalarini Bing/Yandex'e ANINDA bildirir.

Google icin ayrica sitemap + Google Search Console kullanilir (Google IndexNow
protokolune katilmadi); burada yer alan `ping_google_sitemap` sadece eski
(2023'te resmen kullanimdan kaldirilan ama zararsiz) sitemap ping uc noktasina
best-effort bir istek atar.

Bkz. docs/PROGRAMATIK_SEO_WORKFLOW.md §10 — `marketplace.seo_pages.build_next_batch`
her calistiginda yeni uretilen sanatci sayfalarinin slug'larini bu modul
uzerinden IndexNow'a gonderir (aciklamali kanca icin seo_pages.py'ye bakiniz).

Anahtar yonetimi: IndexNow protokolu, sitenin kok dizininde `{key}.txt`
adinda staic bir dosya servis etmeni ister (icerigi = anahtarin kendisi).
`get_key()` bu anahtari uretir/okur: once INDEXNOW_KEY ortam degiskeni,
yoksa `data/indexnow_key.txt` (yoksa `secrets.token_hex(16)` ile BIR KERE
uretilip dosyaya yazilir — boylece anahtar sunucu yeniden baslasa da SABIT
kalir, `{key}.txt` yolu degismez).

Ag guvenligi: bu modulun HICBIR fonksiyonu ag hatasi yuzunden cokmez.
Basarisizlikta {'ok': False, 'submitted': 0, 'error': ...} (veya benzeri)
doner; cagiran taraf (build_next_batch) bu sonucu yutar, build akisini
etkilemez.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

import requests

_KEY_PATH = Path(__file__).resolve().parent.parent / "data" / "indexnow_key.txt"

INDEXNOW_URL = "https://api.indexnow.org/indexnow"
SITE_URL = os.environ.get("SEO_SITE_URL", "https://sozyecho.live").rstrip("/")

# IndexNow protokolu tek istekte azami 10.000 URL kabul eder.
_BATCH_MAX = 10000
_REQUEST_TIMEOUT_SECONDS = 15


def get_key() -> str:
    """IndexNow anahtarini doner (kararli/stabil): once INDEXNOW_KEY ortam
    degiskeni, o da yoksa data/indexnow_key.txt icerigi. Dosya da yoksa
    secrets.token_hex(16) ile BIR KERE uretilip dosyaya yazilir. Anahtar
    boylece surec/sunucu yeniden baslasa da ayni kalir — `keyLocation`
    (ve dolayisiyla `{key}.txt` dosya yolu) degismemis olur."""
    env_key = os.environ.get("INDEXNOW_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    if _KEY_PATH.is_file():
        cached = _KEY_PATH.read_text(encoding="utf-8").strip()
        if cached:
            return cached

    key = secrets.token_hex(16)
    _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _KEY_PATH.write_text(key, encoding="utf-8")
    return key


def submit(urls: list[str]) -> dict:
    """Verilen URL listesini IndexNow API'sine tek istekte gonderir (Bing/
    Yandex aninda indexler). Bos liste icin ag istegi bile atmadan basarili
    sayilir. Liste 10.000'i asarsa (protokol siniri) sadece ilk 10.000 URL
    gonderilir. ASLA istisna firlatmaz: ag hatasi/HTTP hatasi
    {'ok': False, 'submitted': 0, 'error': ...} olarak doner."""
    if not urls:
        return {"ok": True, "submitted": 0}

    batch = list(urls)[:_BATCH_MAX]
    key = get_key()
    host = urlparse(SITE_URL).netloc or SITE_URL
    payload = {
        "host": host,
        "key": key,
        "keyLocation": f"{SITE_URL}/{key}.txt",
        "urlList": batch,
    }
    try:
        resp = requests.post(INDEXNOW_URL, json=payload, timeout=_REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return {"ok": False, "submitted": 0, "error": str(exc)}

    # IndexNow basari kodlari: 200 (islendi) veya 202 (kabul edildi, kuyrukta).
    if resp.status_code not in (200, 202):
        return {
            "ok": False,
            "submitted": 0,
            "error": f"IndexNow HTTP {resp.status_code}: {resp.text[:200]}",
        }
    return {"ok": True, "submitted": len(batch)}


def submit_slugs(slugs: list[str], path_prefix: str = "/artist/") -> dict:
    """Slug listesinden `SITE_URL + path_prefix + slug` seklinde tam URL'ler
    uretip submit() cagirir. Bos liste icin submit'e bile ugramadan
    {'ok': True, 'submitted': 0} doner."""
    if not slugs:
        return {"ok": True, "submitted": 0}
    urls = [f"{SITE_URL}{path_prefix}{slug}" for slug in slugs]
    return submit(urls)


def ping_google_sitemap() -> dict:
    """Google'in eski sitemap ping uc noktasina GET atar. Not: Google bu
    uc noktayi 2023'te resmen kullanimdan kaldirdi; yine de zararsizdir ve
    guarded (ag hatasinda cokmez) oldugu icin burada tutuluyor — asil Google
    indexlemesi sitemap.xml + Search Console uzerinden yapilir."""
    sitemap_url = f"{SITE_URL}/sitemap.xml"
    try:
        resp = requests.get(
            "https://www.google.com/ping",
            params={"sitemap": sitemap_url},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}

    if resp.status_code != 200:
        return {"ok": False, "error": f"Google ping HTTP {resp.status_code}"}
    return {"ok": True}
