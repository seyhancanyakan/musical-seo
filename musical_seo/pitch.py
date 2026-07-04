"""Pitch mesaji uretimi — playlist curator'ina kisisellestirilmis Turkce mesaj.

build_message SAF fonksiyondur (network yok, test edilir). Kisisellestirme:
playlist adi + listede zaten yer alan benzer sanatcilar (en fazla 3'u anilir).
"""
from __future__ import annotations

from musical_seo.models import PlaylistMatch

_MAX_NAMED_ARTISTS = 3


def build_message(
    artist: str,
    title: str,
    match: PlaylistMatch,
    track_url: str | None = None,
) -> str:
    """Tek playlist icin gonderime hazir pitch metni doner."""
    named = match.matched_artists[:_MAX_NAMED_ARTISTS]
    if named:
        overlap = ", ".join(named)
        hook = (
            f'"{match.title}" listende {overlap} gibi isimlere yer veriyorsun; '
            "gercekten tutarli bir secki olmus."
        )
        fit = (
            f'Yeni sarkim "{title}" ayni damardan — listendeki '
            f"{len(match.matched_artists)} sanatciyla ayni rafta durdugunu dusunuyorum."
        )
    else:
        hook = f'"{match.title}" listeni dinledim, seckini cok begendim.'
        fit = f'Yeni sarkim "{title}" listenin havasina iyi oturur diye dusunuyorum.'

    link_line = f"Dinlemek icin: {track_url}\n\n" if track_url else ""

    return (
        "Merhaba,\n\n"
        f"{hook}\n\n"
        f"Ben {artist}. {fit}\n\n"
        f"{link_line}"
        "Uygun gorursen listene eklemen beni cok mutlu eder. "
        "Geri bildirimin olursa da her zaman acigim.\n\n"
        f"Iyi calismalar,\n{artist}"
    )
