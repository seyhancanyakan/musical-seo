"""Marketplace is mantigi: curator dogrulama, gonderim akisi, SLA, yerlesim kaniti.

Saf fonksiyonlar (curator_quality, should_auto_approve, compute_deadline,
is_expired, parse_playlist_id) network kullanmaz — unit test edilir.
Hata sozlesmesi: is kurali ihlalleri ValueError (Turkce mesaj); API katmani
bunlari HTTP 400'e cevirir.
"""
from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

from marketplace import accounts, db, growth, pricing
from musical_seo import db as seo_db
from musical_seo import pitch
from musical_seo.models import PlaylistMatch
from musical_seo.sources import deezer
from musical_seo.sources import spotify as spotify_source

SLA_HOURS = 72

# Kurator/profesyonel turleri (Groover paritesi): playlist kuratoru disindaki
# turler liste baglamadan basvurur, admin onayiyla acilir.
CURATOR_TYPES = (
    "playlist", "radyo", "medya", "label", "menajer", "booker",
    "dj", "mentor", "sync",
)

# Firsat sistemi: primary = somut sonuc, secondary = dolayli deger.
OPPORTUNITY_LEVELS = ("primary", "secondary")
PRIMARY_KINDS = (
    "playlist_ekleme", "radyo_calma", "haber_yazi", "label_degerlendirme",
    "menajerlik_gorusme", "booking_teklif", "dj_set", "mentorluk_seansi",
    "sync_degerlendirme",
)
SECONDARY_KINDS = ("sosyal_paylasim", "tavsiye", "iletisimde_kal")

# Kabul aninda firsat belirtilmezse kurator turune gore varsayilan primary tur.
DEFAULT_PRIMARY_KIND = {
    "playlist": "playlist_ekleme",
    "radyo": "radyo_calma",
    "medya": "haber_yazi",
    "label": "label_degerlendirme",
    "menajer": "menajerlik_gorusme",
    "booker": "booking_teklif",
    "dj": "dj_set",
    "mentor": "mentorluk_seansi",
    "sync": "sync_degerlendirme",
}

MIN_TRACKS = 20          # curator playlist alt siniri
MIN_DIVERSITY = 0.25     # benzersiz sanatci / parca orani alt siniri
                         # (gercek Deezer kullanici listelerinde 0.25-0.35 tipik)
MIN_QUALITY = 20.0       # otomatik onay esigi (0 fan normal; kalite siralama icindir)
_API = "https://api.deezer.com"
_HEADERS = {"User-Agent": "musical-seo/0.1"}
_MAX_TRACK_SCAN = 400


# --- Saf fonksiyonlar ---------------------------------------------------

def curator_quality(fans: int, track_count: int, diversity: float) -> float:
    """0-100: cesitlilik 50 puan, liste boyutu 25, fan 25 (tavanli)."""
    div_c = max(0.0, min(diversity, 1.0)) * 50
    size_c = min(max(track_count, 0), 100) / 100 * 25
    fan_c = min(max(fans, 0), 10_000) / 10_000 * 25
    return round(div_c + size_c + fan_c, 1)


def should_auto_approve(track_count: int, diversity: float, quality: float) -> bool:
    return track_count >= MIN_TRACKS and diversity >= MIN_DIVERSITY and quality >= MIN_QUALITY


def compute_deadline(created_iso: str, hours: int = SLA_HOURS) -> str:
    created = datetime.fromisoformat(created_iso)
    return (created + timedelta(hours=hours)).isoformat()


def is_expired(deadline_iso: str, now_iso: str) -> bool:
    return datetime.fromisoformat(now_iso) > datetime.fromisoformat(deadline_iso)


def fold(s: str) -> str:
    """Aksan-duyarsiz karsilastirma anahtari: 'Güzel' == 'Guzel'."""
    decomposed = unicodedata.normalize("NFD", s.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def parse_playlist_id(ref: str) -> str | None:
    """'https://www.deezer.com/tr/playlist/123' veya '123' -> '123'."""
    ref = ref.strip()
    if ref.isdigit():
        return ref
    m = re.search(r"deezer\.com/(?:[a-z]{2}/)?playlist/(\d+)", ref)
    return m.group(1) if m else None


_SPOTIFY_PL_RE = re.compile(r"open\.spotify\.com/playlist/([A-Za-z0-9]{10,})")


def parse_spotify_playlist_id(ref: str) -> str | None:
    """'https://open.spotify.com/playlist/<id>?si=..' -> '<id>'."""
    m = _SPOTIFY_PL_RE.search(ref.strip())
    return m.group(1) if m else None


def validate_opportunity(
    level: str | None, kind: str | None, action: str, curator_type: str,
) -> tuple[str | None, str | None]:
    """Firsat etiketini dogrula/varsayilanla. Donen (level, kind).

    Kurallar: kabul + etiket yok -> kurator turunun varsayilan primary firsati.
    Red'de etiket istege bagli (secondary olabilir: paylasim/tavsiye/iletisim).
    Gecersiz kombinasyon ValueError.
    """
    if level is None and kind is None:
        if action == "accepted":
            default_kind = DEFAULT_PRIMARY_KIND.get(curator_type, "playlist_ekleme")
            return "primary", default_kind
        return None, None
    if level not in OPPORTUNITY_LEVELS:
        raise ValueError(
            f"Gecersiz firsat seviyesi: {level} (primary|secondary)"
        )
    if level == "primary" and kind not in PRIMARY_KINDS:
        raise ValueError(
            f"Gecersiz primary firsat turu: {kind} ({', '.join(PRIMARY_KINDS)})"
        )
    if level == "secondary" and kind not in SECONDARY_KINDS:
        raise ValueError(
            f"Gecersiz secondary firsat turu: {kind} ({', '.join(SECONDARY_KINDS)})"
        )
    return level, kind


# --- Deezer yardimcilari -------------------------------------------------

def _get(path: str, **params) -> dict:
    try:
        resp = requests.get(f"{_API}{path}", params=params, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and not data.get("error"):
            return data
    except Exception:
        pass
    return {}


def _playlist_tracks(playlist_id: str) -> list[tuple[str, str]]:
    """(sanatci, baslik) ciftleri; en fazla _MAX_TRACK_SCAN parca taranir."""
    tracks: list[tuple[str, str]] = []
    index = 0
    while index < _MAX_TRACK_SCAN:
        data = _get(f"/playlist/{playlist_id}/tracks", limit=100, index=index)
        batch = data.get("data") or []
        if not batch:
            break
        for t in batch:
            artist = (t.get("artist") or {}).get("name", "")
            title = t.get("title") or ""
            if artist and title:
                tracks.append((artist, title))
        if len(batch) < 100:
            break
        index += 100
    return tracks


def inspect_playlist(playlist_id: str) -> dict | None:
    """Playlist gercekligi + kalite metrikleri. Bulunamazsa None."""
    detail = _get(f"/playlist/{playlist_id}")
    if not detail.get("id"):
        return None
    tracks = _playlist_tracks(playlist_id)
    unique_artists = {a.casefold() for a, _ in tracks}
    diversity = round(len(unique_artists) / len(tracks), 3) if tracks else 0.0
    creator = detail.get("creator") or {}
    return {
        "playlist_id": str(detail["id"]),
        "title": detail.get("title") or "",
        "url": detail.get("link") or f"https://www.deezer.com/playlist/{playlist_id}",
        "fans": int(detail.get("fans") or 0),
        "track_count": int(detail.get("nb_tracks") or len(tracks)),
        "diversity": diversity,
        "owner_name": creator.get("name"),
        "tracks": tracks,
    }


# --- Akislar -------------------------------------------------------------

def apply_curator(
    name: str, email: str, playlist_ref: str, curator_type: str = "playlist",
) -> dict:
    """Kurator basvurusu — Deezer VEYA Spotify playlist linkiyle.

    Spotify listeleri sahiplik dogrulamasi (verify_code) tamamlanana kadar
    otomatik onaylanmaz; Deezer'da eski otomatik-onay kurallari gecerli.
    Playlist disi profesyoneller (radyo/medya/label/...) liste vermeden
    basvurur; admin onayina duser (apply_pro_curator).
    """
    if curator_type not in CURATOR_TYPES:
        raise ValueError(
            f"Gecersiz kurator turu: {curator_type} ({', '.join(CURATOR_TYPES)})"
        )
    if curator_type != "playlist" and not playlist_ref.strip():
        return apply_pro_curator(name, email, curator_type)

    spotify_id = parse_spotify_playlist_id(playlist_ref)
    if spotify_id:
        return _apply_spotify_curator(name, email, spotify_id, curator_type)

    playlist_id = parse_playlist_id(playlist_ref)
    if not playlist_id:
        raise ValueError(
            f"Gecersiz playlist referansi (Deezer veya Spotify linki ver): {playlist_ref}"
        )
    info = inspect_playlist(playlist_id)
    if info is None:
        raise ValueError(f"Playlist Deezer'da bulunamadi: {playlist_ref}")

    quality = curator_quality(info["fans"], info["track_count"], info["diversity"])
    # GUVENLIK: kalite esigini gecmek TEK BASINA onaylamaz. Deezer'da da
    # sahiplik dogrulamasi (kod -> playlist aciklamasi) zorunlu; aksi halde
    # herkes sahibi olmadigi kaliteli bir listeyle kurator olabilirdi.
    # Kalite gectiyse quality_passed=1 yazilir; check_ownership sahiplik
    # kanitlaninca otomatik onaylar, gecmediyse admin onayina duser.
    quality_passed = should_auto_approve(info["track_count"], info["diversity"], quality)
    curator_id = db.add_curator(
        name=name, email=email, playlist_id=info["playlist_id"],
        playlist_title=info["title"], playlist_url=info["url"],
        fans=info["fans"], track_count=info["track_count"],
        diversity=info["diversity"], quality_score=quality, status="pending",
        curator_type=curator_type, quality_passed=quality_passed,
    )
    curator = db.get_curator(curator_id)
    if curator is None:
        raise ValueError("Curator kaydi olusturulamadi")
    return curator


def apply_pro_curator(name: str, email: str, curator_type: str) -> dict:
    """Playlist disi profesyonel basvurusu (radyo/medya/label/menajer/booker/
    dj/mentor/sync). Liste dogrulamasi yok -> her zaman admin onayina duser."""
    if curator_type not in CURATOR_TYPES or curator_type == "playlist":
        raise ValueError(
            f"Gecersiz profesyonel turu: {curator_type} "
            f"({', '.join(t for t in CURATOR_TYPES if t != 'playlist')})"
        )
    if not email.strip():
        raise ValueError("Profesyonel basvurusu icin e-posta zorunlu")
    # UNIQUE playlist_id sutunu sentetik anahtarla doldurulur.
    synthetic_id = f"pro_{curator_type}_{email.strip().lower()}"
    curator_id = db.add_curator(
        name=name, email=email, playlist_id=synthetic_id,
        playlist_title=f"{curator_type.capitalize()} — {name}",
        playlist_url="", fans=0, track_count=0, diversity=0.0,
        quality_score=0.0, status="pending", curator_type=curator_type,
    )
    curator = db.get_curator(curator_id)
    if curator is None:
        raise ValueError("Profesyonel kaydi olusturulamadi")
    return curator


def _apply_spotify_curator(
    name: str, email: str, spotify_id: str, curator_type: str = "playlist",
) -> dict:
    tracks = spotify_source.playlist_tracks(spotify_id)
    if not tracks:
        raise ValueError(
            "Spotify playlist okunamadi — liste herkese acik mi? (private liste kabul edilemez)"
        )
    unique_artists = {
        a.casefold() for t in tracks for a in t.get("artists", [])
    }
    diversity = round(len(unique_artists) / len(tracks), 3) if tracks else 0.0
    followers = spotify_source.playlist_followers(spotify_id)
    quality = curator_quality(followers, len(tracks), diversity)

    # Spotify'da sahiplik API'den bilinemez -> dogrulanana kadar pending.
    curator_id = db.add_curator(
        name=name, email=email, playlist_id=f"sp_{spotify_id}",
        playlist_title=name if not tracks else f"Spotify listesi ({len(tracks)} parça)",
        playlist_url=f"https://open.spotify.com/playlist/{spotify_id}",
        fans=followers, track_count=len(tracks),
        diversity=diversity, quality_score=quality, status="pending",
        curator_type=curator_type,
        quality_passed=should_auto_approve(len(tracks), diversity, quality),
    )
    curator = db.get_curator(curator_id)
    if curator is None:
        raise ValueError("Curator kaydi olusturulamadi")
    return curator


# --- Playlist sahiplik dogrulamasi (SubmitHub yontemi) --------------------

def start_ownership_verification(curator_id: int) -> str:
    """Benzersiz kod uret; kurator kodu playlist ACIKLAMASINA ekleyecek."""
    curator = db.get_curator(curator_id)
    if curator is None:
        raise ValueError(f"Curator bulunamadi: {curator_id}")
    code = f"MZK-{secrets.token_hex(3).upper()}"
    db.set_verify_code(curator_id, code)
    return code


def _playlist_description(playlist_id: str) -> str:
    """Kaynaga gore playlist aciklamasi (sp_ -> Spotify, sayi -> Deezer)."""
    if playlist_id.startswith("sp_"):
        return spotify_source.playlist_description(playlist_id[3:])
    data = _get(f"/playlist/{playlist_id}")
    return data.get("description") or ""


def check_ownership(curator_id: int) -> dict:
    """Kod aciklamada gorunuyorsa sahiplik kanitlanir + kurator onaylanir."""
    curator = db.get_curator(curator_id)
    if curator is None:
        raise ValueError(f"Curator bulunamadi: {curator_id}")
    code = curator.get("verify_code")
    if not code:
        raise ValueError("Once dogrulama kodu al (verify/start)")

    description = _playlist_description(curator["deezer_playlist_id"])
    if code not in description:
        raise ValueError(
            "Kod playlist aciklamasinda bulunamadi — ekledikten sonra tekrar dene "
            "(Spotify aciklama guncellemesi 1-2 dk gecikebilir)"
        )
    db.mark_ownership_verified(curator_id)
    # Otomatik onay = sahiplik kanitlandi VE kalite esigi gecildi. Kalitesi
    # dusuk liste sahiplik kanitlasa bile admin onayina duser.
    if curator.get("quality_passed"):
        db.update_curator_status(curator_id, "approved")
    updated = db.get_curator(curator_id)
    assert updated is not None
    return updated


def curator_pricing(curator: dict, stats: dict | None = None,
                    pro_artist: bool = False) -> dict:
    """Kurator kademesi + taban gonderim maliyeti (public katalog + gonderim)."""
    stats = stats or {}
    tier = pricing.curator_tier(
        curator.get("quality_score") or 0.0,
        curator.get("fans") or 0,
        response_rate=stats.get("response_rate"),
        success_rate=stats.get("success_rate"),
    )
    base_cost = pricing.submission_cost(
        tier, curator.get("curator_type") or "playlist", pro_artist=pro_artist
    )
    return {"tier": tier, "base_cost": base_cost}


def _latest_audit_score(artist: str, title: str) -> float | None:
    """SEO karnesindeki son skor -> 'yayina hazir' rozeti (readiness_score)."""
    try:
        rows = seo_db.history(artist, title)
    except Exception:
        return None
    if not rows:
        return None
    latest = max(rows, key=lambda r: r.get("created_at") or "")
    score = latest.get("score")
    return float(score) if score is not None else None


def create_submission(
    artist: str, title: str, curator_id: int, artist_user_id: int | None = None,
    guaranteed: bool = False, priority: bool = False,
) -> dict:
    curator = db.get_curator(curator_id)
    if curator is None:
        raise ValueError(f"Curator bulunamadi: {curator_id}")
    if curator["status"] != "approved":
        raise ValueError("Kürator henüz onaylı değil")

    user = None
    if artist_user_id is not None:
        user = accounts.get_user(artist_user_id)
        if user is None:
            raise ValueError(f"Kullanici bulunamadi: {artist_user_id}")

    # Sarki cozumleme: once Deezer, bulunamazsa Spotify (Spotify-only kataloglar)
    track = deezer.lookup(artist, title)
    if not track.found:
        track = spotify_source.lookup(artist, title)
    if not track.found:
        raise ValueError(
            f"Şarkı Deezer/Spotify'da bulunamadı: {artist} - {title}"
        )

    match = PlaylistMatch(
        source="deezer",
        playlist_id=curator["deezer_playlist_id"],
        title=curator["playlist_title"],
        url=curator["playlist_url"],
        fans=curator["fans"],
        track_count=curator["track_count"],
    )
    message = pitch.build_message(artist, title, match, track_url=track.url)
    created = db.now_iso()
    readiness = _latest_audit_score(artist, title)

    if artist_user_id is None:
        # CLI/misafir yolu: kredi yok -> eklentiler de yok.
        deadline = compute_deadline(created)
        submission_id = db.add_submission(
            artist=artist, title=title, track_url=track.url,
            curator_id=curator_id, message=message, deadline=deadline,
        )
    else:
        pro_artist = accounts.is_pro(user)
        stats = db.curator_stats(curator_id).get(curator_id)
        base_cost = curator_pricing(curator, stats, pro_artist)["base_cost"]
        total_cost = pricing.total_submission_cost(
            base_cost, guaranteed=guaranteed, priority=priority
        )
        deadline = compute_deadline(
            created, hours=pricing.sla_hours(priority, pro_artist, SLA_HOURS)
        )
        # TEK transaction: kosullu kredi dusumu + gonderim + defter kaydi.
        # Kredi dusmezse hicbir kayit olusmaz (orphan/ucretsiz gonderim yok).
        conn = accounts._connect()
        try:
            with conn:
                cur = conn.execute(
                    "UPDATE users SET credits = credits - ? "
                    "WHERE id = ? AND credits >= ?",
                    (total_cost, artist_user_id, total_cost),
                )
                if not cur.rowcount:
                    raise ValueError(
                        f"Yetersiz kredi ({total_cost} gerekli) — paket satın almalısın"
                    )
                sub_cur = conn.execute(
                    """
                    INSERT INTO submissions
                        (created_at, artist, title, track_url, curator_id,
                         message, deadline, artist_user_id, cost_credits,
                         guaranteed, priority, readiness_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (created, artist, title, track.url, curator_id,
                     message, deadline, artist_user_id, total_cost,
                     int(guaranteed), int(priority), readiness),
                )
                submission_id = int(sub_cur.lastrowid)
                conn.execute(
                    "INSERT INTO transactions "
                    "(created_at, user_id, delta, reason, submission_id) "
                    "VALUES (?, ?, ?, 'submission', ?)",
                    (db.now_iso(), artist_user_id, -total_cost, submission_id),
                )
        finally:
            conn.close()
        # Referans bonusu: davet edilen kullanicinin ILK gonderiminde iki
        # tarafa da kredi (idempotent; growth kontrol eder).
        growth.apply_referral_bonus(artist_user_id)

    submission = db.get_submission(submission_id)
    if submission is None:
        raise ValueError("Gonderim kaydi olusturulamadi")
    return submission


def open_submission(submission_id: int) -> dict:
    """Kurator gonderimi acti: dinleme kapisi sayaci baslar (idempotent)."""
    submission = db.get_submission(submission_id)
    if submission is None:
        raise ValueError(f"Gonderim bulunamadi: {submission_id}")
    db.mark_submission_opened(submission_id)
    updated = db.get_submission(submission_id)
    assert updated is not None
    return updated


def respond(
    submission_id: int, action: str, feedback: str = "",
    opportunity_level: str | None = None, opportunity_kind: str | None = None,
) -> dict:
    if action not in ("accepted", "rejected"):
        raise ValueError(f"Gecersiz aksiyon: {action} (accepted|rejected)")
    submission = db.get_submission(submission_id)
    if submission is None:
        raise ValueError(f"Gonderim bulunamadi: {submission_id}")
    if submission["status"] != "pending":
        raise ValueError(f"Gonderim zaten sonuclanmis: {submission['status']}")
    if is_expired(submission["deadline"], db.now_iso()):
        db.expire_overdue()
        raise ValueError("SLA suresi dolmus; gonderim expired olarak isaretlendi")
    # Dinleme kapisi: yanit ancak gonderim ACILDIKTAN belirli sure sonra
    # verilebilir — kopyala-yapistir aninda-yanit geri bildirimi engellenir
    # (rakiplerin en cok sikayet edilen zaafi).
    if pricing.LISTEN_GATE_SECONDS > 0:
        opened_at = submission.get("opened_at")
        if not opened_at:
            raise ValueError(
                "Önce gönderimi aç ve şarkıyı dinle — sonra yanıtla"
            )
        elapsed = (
            datetime.fromisoformat(db.now_iso())
            - datetime.fromisoformat(opened_at)
        ).total_seconds()
        if elapsed < pricing.LISTEN_GATE_SECONDS:
            raise ValueError(
                f"Dinleme kanıtı: yanıt için açılıştan sonra en az "
                f"{pricing.LISTEN_GATE_SECONDS} saniye geçmeli"
            )
    # Garantili geri bildirim: KABUL de RED de 120+ karakter yazili
    # degerlendirme ister — urunun sattigi sey tam olarak bu.
    if not accounts.is_qualified_feedback(feedback):
        raise ValueError(
            f"En az {accounts.QUALIFIED_FEEDBACK_MIN_CHARS} karakter geri bildirim zorunlu "
            "(sanatçı nitelikli değerlendirme için ödeme yapıyor)"
        )

    curator = db.get_curator(submission["curator_id"])
    curator_type = (curator or {}).get("curator_type") or "playlist"
    level, kind = validate_opportunity(
        opportunity_level, opportunity_kind, action, curator_type
    )

    db.set_submission_response(
        submission_id, action, feedback.strip(),
        opportunity_level=level, opportunity_kind=kind,
    )

    # Nitelikli geri bildirim -> kurator kazanci. Kabul/red FARK ETMEZ
    # (editoryal bagimsizlik); playlist'e ekleme odeme sarti DEGIL.
    # One cikan (priority) gonderimi yanitlayan kurator bonus alir.
    if accounts.is_qualified_feedback(feedback):
        curator_user = accounts.user_for_curator(submission["curator_id"])
        if curator_user is not None:
            amount = accounts.FEEDBACK_EARNING_USD
            if submission.get("priority"):
                amount += pricing.PRIORITY_BONUS_USD
            accounts.accrue_earning(curator_user["id"], submission_id, amount)

    updated = db.get_submission(submission_id)
    assert updated is not None
    return updated


def expire_and_refund() -> dict:
    """SLA'si dolan gonderimleri expired isaretle + kredileri OTOMATIK iade et.

    Normal gonderim odedigini geri alir; GARANTILI gonderim 2 katini alir
    (pricing.refund_amount). Idempotent: refund_credit ayni gonderime ikinci
    iadeyi yazmaz. Kurator inbox'i her cekildiginde ve /maintenance/expire
    ile cagrilir.
    """
    expired_count = db.expire_overdue()
    refunded = 0
    for sub in db.list_submissions(status="expired"):
        if sub.get("artist_user_id"):
            amount = pricing.refund_amount(
                sub.get("cost_credits") or 1, bool(sub.get("guaranteed"))
            )
            if accounts.refund_credit(sub["artist_user_id"], sub["id"], amount):
                refunded += 1
    return {"expired": expired_count, "refunded": refunded}


PLACEMENT_GUARANTEE_HOURS = 48


def enforce_placement_guarantee() -> dict:
    """Yerlesim garantisi: GARANTILI + kabul edilmis playlist gonderimi,
    kabulden PLACEMENT_GUARANTEE_HOURS sonra hala playlist'te dogrulanamiyorsa
    kredinin tamami iade edilir (reason='placement_refund', tek sefer).

    Sahte-kabul (kabul et, ekleme) davranisini ekonomik olarak cezalandirir —
    rakiplerde olmayan, Deezer/Spotify API'siyle kanitlanan guvence.
    """
    checked = refunded = 0
    now = datetime.fromisoformat(db.now_iso())
    for sub in db.list_submissions(status="accepted"):
        if not sub.get("guaranteed") or not sub.get("artist_user_id"):
            continue
        if sub.get("placement_verified"):
            continue
        if sub.get("opportunity_kind") not in (None, "playlist_ekleme"):
            continue  # radyo/haber gibi firsatlar playlist kaniti gerektirmez
        responded_at = sub.get("responded_at")
        if not responded_at:
            continue
        age_hours = (now - datetime.fromisoformat(responded_at)).total_seconds() / 3600
        if age_hours < PLACEMENT_GUARANTEE_HOURS:
            continue
        checked += 1
        try:
            result = verify_placement(sub["id"])
        except ValueError:
            continue
        if not result.get("placement_verified"):
            if accounts.refund_credit(
                sub["artist_user_id"], sub["id"],
                amount=sub.get("cost_credits") or 1, reason="placement_refund",
            ):
                refunded += 1
    return {"checked": checked, "refunded": refunded}


def verify_placement(submission_id: int) -> dict:
    """Kabul edilen sarkinin playlist'e GERCEKTEN eklendigini Deezer'dan dogrular."""
    submission = db.get_submission(submission_id)
    if submission is None:
        raise ValueError(f"Gonderim bulunamadi: {submission_id}")
    if submission["status"] != "accepted":
        raise ValueError("Yerlesim kaniti sadece kabul edilen gonderimler icin")
    curator = db.get_curator(submission["curator_id"])
    if curator is None:
        raise ValueError("Curator kaydi bulunamadi")

    playlist_ref = curator["deezer_playlist_id"]
    if playlist_ref.startswith("sp_"):
        tracks = [
            (t["artists"][0] if t.get("artists") else "", t.get("title", ""))
            for t in spotify_source.playlist_tracks(playlist_ref[3:])
        ]
    else:
        tracks = _playlist_tracks(playlist_ref)
    artist_f = fold(submission["artist"])
    title_f = fold(submission["title"])
    verified = any(
        fold(a) == artist_f and fold(t) == title_f for a, t in tracks
    )
    if verified:
        db.set_placement_verified(submission_id)
    result = db.get_submission(submission_id)
    assert result is not None
    result["placement_checked"] = True
    result["placement_verified"] = 1 if verified else 0
    return result
