"""Scout CSV → marketplace.db import (curator lead'leri).

muzikseo-scout botunun Deezer public API ciktisini (curators.csv) marketplace
curators tablosuna 'lead' olarak aktarir. Iletisim (email) henuz YOK — enrichment
ayri adim (bkz. enrich_contacts.py). Sadece halka acik playlist/sahip kimligi.

Kullanim:
    python -m marketplace.import_scout data/scout_curators.csv
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

from marketplace import db

# Scout'ta olmayan alanlar icin turetme.
DIVERSITY_UNKNOWN = 0.0


def quality_from(fans: int, track_count: int) -> float:
    """Kaba kalite skoru: fan (log) + parca sayisi. Deezer fan cogu zaman 0 doner,
    o yuzden parca sayisi da agirlikli. 0-100 araligi."""
    fan_part = math.log10(fans + 1) * 22.0
    track_part = min(track_count, 120) * 0.35
    return round(min(100.0, fan_part + track_part), 1)


def to_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def import_csv(csv_path: Path) -> dict:
    inserted = 0
    skipped = 0
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            playlist_id = (row.get("playlist_id") or "").strip()
            if not playlist_id:
                skipped += 1
                continue
            fans = to_int(row.get("fans", "0"))
            tracks = to_int(row.get("nb_tracks", "0"))
            name = (row.get("owner_name") or "Bilinmeyen").strip() or "Bilinmeyen"
            title = (row.get("title") or "").strip() or f"Playlist {playlist_id}"
            url = (row.get("url") or "").strip()
            cid = db.add_curator(
                name=name,
                email="",  # iletisim henuz yok — enrichment dolduracak
                playlist_id=playlist_id,
                playlist_title=title,
                playlist_url=url,
                fans=fans,
                track_count=tracks,
                diversity=DIVERSITY_UNKNOWN,
                quality_score=quality_from(fans, tracks),
                status="lead",
            )
            if cid:
                inserted += 1
            else:
                skipped += 1
    return {"inserted": inserted, "skipped": skipped}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("kullanim: python -m marketplace.import_scout <csv-yolu>")
        return 2
    csv_path = Path(argv[1])
    if not csv_path.exists():
        print(f"CSV bulunamadi: {csv_path}")
        return 1
    result = import_csv(csv_path)
    total = len(db.list_curators(status=None))
    print(f"import bitti — eklenen/guncellenen:{result['inserted']} atlanan:{result['skipped']}")
    print(f"marketplace.db toplam curator: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
