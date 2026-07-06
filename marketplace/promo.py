"""Otomatik tanitim videosu / animasyonlu kanit karti (promo).

Sanatcinin SEO skoru + dogrulanmis yerlesimlerini paylasilabilir, animasyonlu
bir kanit kartina (1080x1920, Instagram/TikTok Story boyutu) donusturur.
SMIL animasyonlari (<animate>/<animateTransform>) ile canli gorunum: yavas
donen halka, nabiz gibi buyuyup kucuen daireler, SEO skoru halkasi.

Token kalicidir (bir kez ucret alinir); SVG her istekte GUNCEL veriyle
(kapak/skor/dogrulanmis yerlesim sayisi) yeniden render edilir — bu yuzden
render_svg disaridan cover/score/placements alir, kendisi DB/network'e
dokunmaz (test edilebilirlik).

Is kurali ihlalleri ValueError (Turkce) — API katmani 400'e cevirir.
"""
from __future__ import annotations

import html
import secrets

import requests

from marketplace import accounts, db

PROMO_COST = 1                 # kredi (pro ucretsiz)
STYLES = ("dark", "light")

_DEEZER_SEARCH_URL = "https://api.deezer.com/search"
_TIMEOUT = 10

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS promo_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id),
        token TEXT NOT NULL UNIQUE,
        artist TEXT NOT NULL,
        title TEXT NOT NULL,
        style TEXT NOT NULL DEFAULT 'dark'
    );
    """,
]


def _connect():
    conn = db._connect()  # marketplace.db + ana sema hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


def _charge_unless_pro(user: dict, amount: int, reason: str) -> bool:
    """Pro'ya ucretsiz; degilse kredi dus. Donen deger: ucret alindi mi."""
    if accounts.is_pro(user):
        return False
    accounts.charge_credits(user["id"], amount, reason)
    return True


# --- Kapak gorseli (Deezer) --------------------------------------------------

def cover_url(artist: str, title: str) -> str | None:
    """Deezer arama API'sinden ilk sonucun album kapagi (cover_xl).
    Hata veya sonuc yoksa None doner (SVG gradient placeholder kullanir)."""
    try:
        resp = requests.get(
            _DEEZER_SEARCH_URL,
            params={"q": f"{artist} {title}", "limit": 1},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    results = data.get("data")
    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    album = first.get("album") or {}
    cover = album.get("cover_xl")
    return cover if isinstance(cover, str) and cover else None


# --- SEO skoru + dogrulanmis yerlesim sayisi ---------------------------------

def latest_score(artist: str, title: str) -> float | None:
    """SEO karnesi son skoru (musical_seo.db.history). Hata tolere edilir."""
    try:
        from musical_seo import db as seo_db
        rows = seo_db.history(artist, title)
    except Exception:
        return None
    if not rows:
        return None
    return rows[-1].get("score")


def verified_placement_count(user_id: int) -> int:
    """Kullanicinin dogrulanmis (placement_verified) gonderim sayisi."""
    subs = db.list_submissions(artist_user_id=user_id)
    return sum(1 for s in subs if s.get("placement_verified"))


# --- Promo kaydi (token) ------------------------------------------------------

def create_promo(user: dict, artist: str, title: str, style: str = "dark") -> dict:
    """Yeni kanit karti kaydi olustur. Ucret PROMO_COST (pro ucretsiz).
    Token kalicidir; SVG her istekte guncel veriyle render edilir."""
    artist = artist.strip()
    title = title.strip()
    if not artist or not title:
        raise ValueError("Sanatci ve sarki adi bos olamaz")
    if style not in STYLES:
        raise ValueError(f"Gecersiz stil: {style} (dark|light olmali)")
    _charge_unless_pro(user, PROMO_COST, "promo")
    token = f"PRM-{secrets.token_hex(6)}"
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO promo_assets "
                "(created_at, user_id, token, artist, title, style) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (db.now_iso(), user["id"], token, artist, title, style),
            )
            row_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT * FROM promo_assets WHERE id = ?", (row_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_promo(token: str, user: dict) -> dict:
    """Sahiplik kontrollu tekil kayit."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM promo_assets WHERE token = ?", (token,)
        ).fetchone()
    finally:
        conn.close()
    if row is None or dict(row)["user_id"] != user["id"]:
        raise ValueError(f"Promo bulunamadi: {token}")
    return dict(row)


def list_promos(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM promo_assets WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Animasyonlu SVG render ----------------------------------------------------

def render_svg(asset: dict, cover: str | None, score: float | None,
               placements: int) -> str:
    """1080x1920 animasyonlu kanit karti (SMIL). Degrade zemin, yavas donen
    halka, nabiz gibi buyuyup kucuen daireler, kapak gorseli (yoksa gradient
    placeholder), SEO skoru halkasi (varsa), 'Dogrulanmis Yerlesim xN' rozeti
    (varsa), altta 'muzikseo' markasi."""
    e = html.escape
    dark = asset.get("style", "dark") != "light"
    bg1, bg2 = ("#0d1117", "#161b22") if dark else ("#f5f0e6", "#e8ddc8")
    fg = "#e6edf3" if dark else "#1c1c1c"
    sub = "#8b949e" if dark else "#6e6456"
    accent = "#d4a017"
    artist = asset.get("artist", "")
    title = asset.get("title", "")

    if cover:
        cover_block = f"""
    <clipPath id="coverClip"><rect x="290" y="260" width="500" height="500" rx="24"/></clipPath>
    <image href="{e(cover)}" x="290" y="260" width="500" height="500"
        preserveAspectRatio="xMidYMid slice" clip-path="url(#coverClip)"/>
    <rect x="290" y="260" width="500" height="500" rx="24" fill="none"
        stroke="{accent}" stroke-width="4"/>"""
    else:
        initial = e((artist[:1] or "?").upper())
        cover_block = f"""
    <rect x="290" y="260" width="500" height="500" rx="24" fill="url(#coverGrad)"/>
    <text x="540" y="545" text-anchor="middle" fill="{fg}" font-size="140"
        font-family="Georgia" font-weight="bold">{initial}</text>"""

    score_block = ""
    if score is not None:
        pct = max(0.0, min(100.0, float(score))) / 100.0
        circumference = round(2 * 3.14159265 * 70, 1)
        dash = round(circumference * pct, 1)
        score_block = f"""
    <g transform="translate(540,1430)">
      <circle r="80" fill="none" stroke="{sub}" stroke-width="10" opacity="0.25"/>
      <circle r="70" fill="none" stroke="{accent}" stroke-width="10"
          stroke-linecap="round" transform="rotate(-90)"
          stroke-dasharray="{dash} {circumference}">
        <animate attributeName="stroke-dasharray"
            values="0 {circumference};{dash} {circumference}"
            dur="1.4s" fill="freeze"/>
      </circle>
      <text text-anchor="middle" dy="14" fill="{fg}" font-size="44"
          font-family="Georgia" font-weight="bold">{score:.0f}</text>
    </g>
    <text x="540" y="1530" text-anchor="middle" fill="{sub}" font-size="26"
        font-family="Georgia" letter-spacing="4">SEO SKORU</text>"""

    badge_block = ""
    if placements > 0:
        badge_block = f"""
    <g transform="translate(540,1630)">
      <rect x="-230" y="-34" width="460" height="68" rx="34" fill="none"
          stroke="{accent}" stroke-width="3"/>
      <text text-anchor="middle" dy="10" fill="{accent}" font-size="28"
          font-family="Georgia" letter-spacing="1">DOGRULANMIS YERLESIM x{placements}</text>
    </g>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1080" height="1920" viewBox="0 0 1080 1920">
  <defs>
    <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{bg1}"/>
      <stop offset="100%" stop-color="{bg2}"/>
    </linearGradient>
    <linearGradient id="coverGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{accent}"/>
      <stop offset="100%" stop-color="{bg2}"/>
    </linearGradient>
  </defs>
  <rect width="1080" height="1920" fill="url(#bgGrad)"/>

  <g transform="translate(540,150)">
    <g>
      <animateTransform attributeName="transform" type="rotate"
          from="0 0 0" to="360 0 0" dur="24s" repeatCount="indefinite"/>
      <circle r="120" fill="none" stroke="{accent}" stroke-width="2"
          stroke-dasharray="6 18" opacity="0.6"/>
      <circle r="150" fill="none" stroke="{sub}" stroke-width="1"
          stroke-dasharray="2 14" opacity="0.4"/>
    </g>
    <circle r="18" fill="{accent}" opacity="0.85">
      <animate attributeName="r" values="14;22;14" dur="3s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.9;0.4;0.9" dur="3s" repeatCount="indefinite"/>
    </circle>
  </g>
  <circle cx="180" cy="900" r="10" fill="{accent}" opacity="0.5">
    <animate attributeName="r" values="6;16;6" dur="4s" repeatCount="indefinite"/>
  </circle>
  <circle cx="920" cy="1000" r="8" fill="{sub}" opacity="0.5">
    <animate attributeName="r" values="5;14;5" dur="5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="860" cy="200" r="6" fill="{accent}" opacity="0.6">
    <animate attributeName="r" values="4;12;4" dur="3.5s" repeatCount="indefinite"/>
  </circle>

  {cover_block}

  <text x="540" y="880" text-anchor="middle" fill="{accent}" font-size="26"
      font-family="Georgia" letter-spacing="8">MUZIKSEO KANIT KARTI</text>
  <text x="540" y="960" text-anchor="middle" fill="{fg}" font-size="72"
      font-family="Georgia" font-weight="bold">{e(artist)}</text>
  <text x="540" y="1040" text-anchor="middle" fill="{sub}" font-size="48"
      font-family="Georgia">&#8220;{e(title)}&#8221;</text>

  {score_block}
  {badge_block}

  <text x="540" y="1860" text-anchor="middle" fill="{sub}" font-size="26"
      font-family="Georgia" letter-spacing="6">muzikseo</text>
</svg>"""
