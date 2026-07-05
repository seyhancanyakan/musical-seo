"""Marketplace is mantigi: curator dogrulama, gonderim akisi, SLA, yerlesim kaniti.

Saf fonksiyonlar (curator_quality, should_auto_approve, compute_deadline,
is_expired, parse_playlist_id) network kullanmaz — unit test edilir.
Hata sozlesmesi: is kurali ihlalleri ValueError (Turkce mesaj); API katmani
bunlari HTTP 400'e cevirir.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

from marketplace import accounts, db
from musical_seo import pitch
from musical_seo.models import PlaylistMatch
from musical_seo.sources import deezer

SLA_HOURS = 72
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

def apply_curator(name: str, email: str, playlist_ref: str) -> dict:
    playlist_id = parse_playlist_id(playlist_ref)
    if not playlist_id:
        raise ValueError(f"Gecersiz Deezer playlist referansi: {playlist_ref}")
    info = inspect_playlist(playlist_id)
    if info is None:
        raise ValueError(f"Playlist Deezer'da bulunamadi: {playlist_ref}")

    quality = curator_quality(info["fans"], info["track_count"], info["diversity"])
    status = (
        "approved"
        if should_auto_approve(info["track_count"], info["diversity"], quality)
        else "pending"
    )
    curator_id = db.add_curator(
        name=name, email=email, playlist_id=info["playlist_id"],
        playlist_title=info["title"], playlist_url=info["url"],
        fans=info["fans"], track_count=info["track_count"],
        diversity=info["diversity"], quality_score=quality, status=status,
    )
    curator = db.get_curator(curator_id)
    if curator is None:
        raise ValueError("Curator kaydi olusturulamadi")
    return curator


def create_submission(
    artist: str, title: str, curator_id: int, artist_user_id: int | None = None
) -> dict:
    curator = db.get_curator(curator_id)
    if curator is None:
        raise ValueError(f"Curator bulunamadi: {curator_id}")
    if curator["status"] != "approved":
        raise ValueError("Curator henuz onayli degil")

    # Kredi on-kontrolu: bakiye yoksa gonderim hic olusturulmaz. Asil dusum
    # kayit olustuktan sonra atomik yapilir (spend_credit); ayni kullanicinin
    # es zamanli iki gonderiminde nadir yaris pilotta kabul edilebilir.
    if artist_user_id is not None:
        user = accounts.get_user(artist_user_id)
        if user is None:
            raise ValueError(f"Kullanici bulunamadi: {artist_user_id}")
        if user["credits"] < 1:
            raise ValueError("Yetersiz kredi — paket satin almalisin")

    track = deezer.lookup(artist, title)
    if not track.found:
        raise ValueError(f"Sarki Deezer'da bulunamadi: {artist} - {title}")

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
    submission_id = db.add_submission(
        artist=artist, title=title, track_url=track.url,
        curator_id=curator_id, message=message,
        deadline=compute_deadline(created),
        artist_user_id=artist_user_id,
    )
    if artist_user_id is not None:
        accounts.spend_credit(artist_user_id, submission_id)
    submission = db.get_submission(submission_id)
    if submission is None:
        raise ValueError("Gonderim kaydi olusturulamadi")
    return submission


def respond(submission_id: int, action: str, feedback: str = "") -> dict:
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
    if action == "rejected" and not feedback.strip():
        raise ValueError("Red icin kisa bir geri bildirim zorunlu")

    db.set_submission_response(submission_id, action, feedback.strip())

    # Nitelikli geri bildirim -> kurator kazanci. Kabul/red FARK ETMEZ
    # (editoryal bagimsizlik); playlist'e ekleme odeme sarti DEGIL.
    if accounts.is_qualified_feedback(feedback):
        curator_user = accounts.user_for_curator(submission["curator_id"])
        if curator_user is not None:
            accounts.accrue_earning(curator_user["id"], submission_id)

    updated = db.get_submission(submission_id)
    assert updated is not None
    return updated


def expire_and_refund() -> dict:
    """SLA'si dolan gonderimleri expired isaretle + kredileri OTOMATIK iade et.

    Idempotent: refund_credit ayni gonderime ikinci iadeyi yazmaz. Kurator
    inbox'i her cekildiginde ve /maintenance/expire ile cagrilir.
    """
    expired_count = db.expire_overdue()
    refunded = 0
    for sub in db.list_submissions(status="expired"):
        if sub.get("artist_user_id"):
            if accounts.refund_credit(sub["artist_user_id"], sub["id"]):
                refunded += 1
    return {"expired": expired_count, "refunded": refunded}


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

    tracks = _playlist_tracks(curator["deezer_playlist_id"])
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
