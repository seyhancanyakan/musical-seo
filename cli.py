"""musical-seo CLI.

Alt komutlar: audit, snapshot, history. Konsol ciktisi ASCII-guvenli
(emoji yok), Windows konsolunda sorunsuz calisir.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from musical_seo import audit, db, pitch, playlists, report
from musical_seo.sources import deezer

_SEVERITY_LABELS = {
    "critical": "[KRITIK]",
    "warn": "[UYARI]",
    "info": "[BILGI]",
    "ok": "[OK]",
}


def _slugify(text: str) -> str:
    chars = [ch if ch.isalnum() else "-" for ch in text.casefold()]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "track"


def _fmt(value) -> str:
    return "-" if value is None else str(value)


def _print_summary(result) -> None:
    print(f"Sanatci: {result.resolved_artist}")
    print(f"Sarki: {result.resolved_title}")
    print(f"Genel skor: {result.score}/100")
    print("Alt skorlar:")
    for category, value in result.subscores.items():
        print(f"  {category}: {value}/100")
    print("Bulgular:")
    if not result.findings:
        print("  (bulgu yok)")
    for finding in result.findings:
        label = _SEVERITY_LABELS.get(finding.severity, f"[{finding.severity.upper()}]")
        print(f"  {label} {finding.message}")
        if finding.action:
            print(f"      Yapilacak: {finding.action}")


def _parse_artist_title(query: str) -> tuple[str, str] | None:
    if " - " not in query:
        return None
    artist, _, title = query.partition(" - ")
    artist = artist.strip()
    title = title.strip()
    if not artist or not title:
        return None
    return artist, title


def _cmd_audit(args: argparse.Namespace) -> int:
    try:
        result = audit.run_audit(args.query)
    except ValueError as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_summary(result)

    if args.out:
        out_path = Path(args.out)
    else:
        slug = _slugify(f"{result.resolved_artist}-{result.resolved_title}")
        out_path = Path("reports") / f"{slug}.html"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.render_html(result), encoding="utf-8")

    if not args.no_save:
        db.save(result)

    return 0


def _cmd_snapshot(args: argparse.Namespace) -> int:
    list_path = Path(args.list)
    if not list_path.is_file():
        print(f"Hata: liste dosyasi bulunamadi: {list_path}", file=sys.stderr)
        return 1

    ok_count = 0
    err_count = 0
    for raw_line in list_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            result = audit.run_audit(line)
            db.save(result)
            ok_count += 1
        except Exception:
            err_count += 1

    print(f"{ok_count} ok / {err_count} hata")
    return 0


def _cmd_history(args: argparse.Namespace) -> int:
    parsed = _parse_artist_title(args.query)
    if parsed is None:
        print(
            f"Hata: sorgu 'Sanatci - Sarki' formatinda olmali: {args.query}",
            file=sys.stderr,
        )
        return 1

    artist, title = parsed
    rows = db.history(artist, title)
    if not rows:
        print("Kayit bulunamadi.")
        return 0

    header = f"{'Tarih':<26} {'Skor':>5} {'Spotify':>8} {'Deezer':>7} {'YT views':>9}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['created_at']:<26} {row['score']:>5} "
            f"{_fmt(row['spotify_popularity']):>8} {_fmt(row['deezer_rank']):>7} "
            f"{_fmt(row['youtube_views']):>9}"
        )
    return 0


def _cmd_playlists(args: argparse.Namespace) -> int:
    parsed = _parse_artist_title(args.query)
    if parsed is None:
        info = deezer.search(args.query)
        if not info.found or not info.artist or not info.title:
            print(f"Hata: sarki bulunamadi: {args.query}", file=sys.stderr)
            return 1
        artist, title = info.artist, info.title
    else:
        artist, title = parsed

    results = playlists.find_playlists(artist, title, limit=args.limit)

    if args.json:
        print(json.dumps([asdict(m) for m in results], ensure_ascii=False, indent=2))
        return 0

    if not results:
        print("Uygun playlist bulunamadi.")
        return 0

    print(f"Pitch aday listesi: {artist} - {title} ({len(results)} playlist)\n")
    for i, m in enumerate(results, start=1):
        inside = "  [SARKI ZATEN ICINDE]" if m.contains_track else ""
        print(f"{i:>2}. [skor {m.score:5.1f}] {m.title}  "
              f"({m.fans} fan, {m.track_count} parca){inside}")
        if m.matched_artists:
            print(f"      Eslesen sanatcilar: {', '.join(m.matched_artists)}")
        print(f"      {m.url}")
    return 0


def _resolve_artist_title(query: str) -> tuple[str, str] | None:
    parsed = _parse_artist_title(query)
    if parsed is not None:
        return parsed
    info = deezer.search(query)
    if not info.found or not info.artist or not info.title:
        return None
    return info.artist, info.title


def _cmd_pitch(args: argparse.Namespace) -> int:
    if args.list:
        rows = db.list_pitches()
        if not rows:
            print("Pitch kaydi yok.")
            return 0
        header = f"{'ID':>4} {'Tarih':<10} {'Durum':<9} {'Sanatci - Sarki':<35} Playlist"
        print(header)
        print("-" * len(header))
        for row in rows:
            pair = f"{row['artist']} - {row['title']}"
            print(
                f"{row['id']:>4} {row['created_at'][:10]:<10} {row['status']:<9} "
                f"{pair:<35.35} {row['playlist_title']}"
            )
        return 0

    if args.set:
        pitch_id_raw, status = args.set
        try:
            pitch_id = int(pitch_id_raw)
        except ValueError:
            print(f"Hata: ID sayi olmali: {pitch_id_raw}", file=sys.stderr)
            return 1
        try:
            updated = db.update_pitch_status(pitch_id, status)
        except ValueError as exc:
            print(f"Hata: {exc}", file=sys.stderr)
            return 1
        if not updated:
            print(f"Hata: pitch kaydi bulunamadi: {pitch_id}", file=sys.stderr)
            return 1
        print(f"Pitch {pitch_id} -> {status}")
        return 0

    if not args.query:
        print("Hata: sorgu ver ('Sanatci - Sarki') ya da --list / --set kullan.",
              file=sys.stderr)
        return 1

    resolved = _resolve_artist_title(args.query)
    if resolved is None:
        print(f"Hata: sarki bulunamadi: {args.query}", file=sys.stderr)
        return 1
    artist, title = resolved

    track = deezer.lookup(artist, title)
    track_url = track.url if track.found else None

    matches = playlists.find_playlists(artist, title, limit=args.limit)
    if not matches:
        print("Uygun playlist bulunamadi.")
        return 0

    blocks: list[str] = []
    for i, m in enumerate(matches, start=1):
        message = pitch.build_message(artist, title, m, track_url=track_url)
        head = (f"=== {i}. {m.title} ({m.fans} fan, {m.track_count} parca) ===\n"
                f"{m.url}\n")
        blocks.append(head + "\n" + message + "\n")
        if args.save:
            db.save_pitch(artist, title, m.playlist_id, m.title, m.url)

    output = "\n".join(blocks)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"{len(matches)} pitch mesaji yazildi: {out_path}")
    else:
        print(output)
    if args.save:
        print(f"{len(matches)} pitch kaydi eklendi (takip: python cli.py pitch --list)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="musical-seo", description="musical-seo CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit", help="Tek sarki denetimi")
    audit_parser.add_argument("query", help="Spotify URL veya 'Sanatci - Sarki'")
    audit_parser.add_argument("--out", help="HTML raporu icin hedef dosya")
    audit_parser.add_argument("--json", action="store_true", help="Ozet yerine JSON bas")
    audit_parser.add_argument("--no-save", action="store_true", help="Veritabanina kaydetme")
    audit_parser.set_defaults(func=_cmd_audit)

    snapshot_parser = subparsers.add_parser("snapshot", help="Toplu anlik goruntu")
    snapshot_parser.add_argument(
        "--list", default="tracks.txt", help="Her satirda bir 'Sanatci - Sarki' sorgusu"
    )
    snapshot_parser.set_defaults(func=_cmd_snapshot)

    playlists_parser = subparsers.add_parser(
        "playlists", help="Benzer-sanatci playlist eslestirme (pitch listesi)"
    )
    playlists_parser.add_argument("query", help="'Sanatci - Sarki' veya serbest metin")
    playlists_parser.add_argument("--limit", type=int, default=15, help="En fazla sonuc")
    playlists_parser.add_argument("--json", action="store_true", help="JSON cikti")
    playlists_parser.set_defaults(func=_cmd_playlists)

    pitch_parser = subparsers.add_parser(
        "pitch", help="Curator pitch mesaji uret + takip et"
    )
    pitch_parser.add_argument("query", nargs="?", help="'Sanatci - Sarki' veya serbest metin")
    pitch_parser.add_argument("--limit", type=int, default=5, help="En fazla playlist")
    pitch_parser.add_argument("--save", action="store_true", help="Pitch kayitlarini DB'ye ekle")
    pitch_parser.add_argument("--out", help="Mesajlari dosyaya yaz")
    pitch_parser.add_argument("--list", action="store_true", help="Kayitli pitch'leri goster")
    pitch_parser.add_argument(
        "--set", nargs=2, metavar=("ID", "DURUM"),
        help="Pitch durumunu guncelle (pitched|accepted|rejected)"
    )
    pitch_parser.set_defaults(func=_cmd_pitch)

    history_parser = subparsers.add_parser("history", help="Zaman serisi gecmisi")
    history_parser.add_argument("query", help="'Sanatci - Sarki' formatinda sorgu")
    history_parser.set_defaults(func=_cmd_history)

    args = parser.parse_args()
    exit_code = args.func(args)
    sys.exit(0 if exit_code is None else exit_code)


if __name__ == "__main__":
    main()
