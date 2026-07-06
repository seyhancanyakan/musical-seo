"""Sanatci sarki kutuphanesi ("Sarkilarim").

Sanatci sarkisini BIR KEZ kaydeder (Deezer/Spotify'da cozumlenir ve
dogrulanir); gonderim/otopilot/takvim/radyo akislari kayitli sarkidan secer —
her seferinde elle yazip yazim hatasiyla bulunamama derdi biter.
Is kurali ihlalleri ValueError (Turkce); API katmani 400'e cevirir.
"""
from __future__ import annotations

from marketplace import accounts, db
from marketplace.service import fold
from musical_seo.sources import deezer
from musical_seo.sources import spotify as spotify_source

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS artist_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        artist TEXT NOT NULL,
        title TEXT NOT NULL,
        track_url TEXT,
        source TEXT NOT NULL DEFAULT 'deezer',
        UNIQUE(user_id, artist, title)
    );
    """,
]


def _connect():
    conn = accounts._connect()  # marketplace.db + users semasi hazir
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


def add_track(user_id: int, artist: str, title: str) -> dict:
    """Sarkiyi cozumle (once Deezer, sonra Spotify) ve kutuphaneye kaydet.

    Bulunamazsa ValueError — sanatci once dagitima cikmis olmali; UI bu
    mesaji AYNEN gosterir.
    """
    artist, title = artist.strip(), title.strip()
    if not artist or not title:
        raise ValueError("Sanatci ve sarki adi bos olamaz")
    track = deezer.lookup(artist, title)
    source = "deezer"
    if not track.found:
        track = spotify_source.lookup(artist, title)
        source = "spotify"
    if not track.found:
        raise ValueError(
            f"Sarki Deezer/Spotify'da bulunamadi: {artist} - {title}. "
            "Yazimi kontrol et; sarki henuz yayinlanmadiysa once dagitima cik "
            "(dagitim ortaklari icin /linkler sayfasindaki Ortaklar bolumune bak)."
        )
    # SANATCI ESLESME KAPISI: arama motoru serbest-metin fallback'inde
    # ilk sonucu doner — yanlis sanatcinin sarkisi sessizce kaydedilmesin.
    # Aksan-duyarsiz karsilastirma; kisaltma/uzun-ad tolerans icin icerme
    # iki yonlu kontrol edilir ("Duman" ~ "Duman Band").
    resolved_artist = (track.artist or "").strip()

    def _norm(s: str) -> str:
        # fold() aksanlari soker ama Turkce noktasiz 'ı' base karakter oldugu
        # icin kalir — ASCII yazan kullanici ("kisaparmak") eslessin diye.
        return fold(s).replace("ı", "i")

    req_f, res_f = _norm(artist), _norm(resolved_artist)
    if resolved_artist and req_f not in res_f and res_f not in req_f:
        raise ValueError(
            f"Bulunan sarki farkli sanatciya ait: {resolved_artist} - "
            f"{track.title or title}. '{artist}' adina kayitli bu isimde sarki "
            "bulunamadi — yazimi kontrol et ya da sarkinin dagitimda yayinda "
            "oldugundan emin ol."
        )
    # Cozumlenen resmi ad/baslik yazilir (yazim varyasyonlari tekillesir).
    artist_r = resolved_artist or artist
    title_r = track.title or title
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO artist_tracks "
                "(created_at, user_id, artist, title, track_url, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (db.now_iso(), user_id, artist_r, title_r, track.url, source),
            )
        row = conn.execute(
            "SELECT * FROM artist_tracks WHERE user_id = ? AND artist = ? AND title = ?",
            (user_id, artist_r, title_r),
        ).fetchone()
        assert row is not None
        return dict(row)
    finally:
        conn.close()


def list_tracks(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM artist_tracks WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_track(user_id: int, track_id: int) -> bool:
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "DELETE FROM artist_tracks WHERE id = ? AND user_id = ?",
                (track_id, user_id),
            )
            return cur.rowcount > 0
    finally:
        conn.close()
