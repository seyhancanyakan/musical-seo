"""Email enrichment — Deezer playlist aciklamasindan iletisim ayikla.

Yasal katman: SADECE curator'in playlist metadata'sinda (baslik + aciklama)
GONDERIM ICIN yayinladigi iletisimi toplar. Ozel/rizasiz veri toplamaz.

Lead'lerde email='' olanlar icin Deezer playlist aciklamasini ceker, metinden
email + instagram handle + submit-link ayiklar, bulursa curators.email gunceller
ve kaynak isaretler (contact_source kolonu, idempotent ALTER ile eklenir).

Kullanim:
    python -m marketplace.enrich_contacts [limit]
"""
from __future__ import annotations

import re
import sqlite3
import sys
import time

import requests

from marketplace import db

API = "https://api.deezer.com"
HEADERS = {"User-Agent": "muzikseo-enrich/0.1"}
SLEEP = 0.25  # Deezer kota nezaketi

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
IG_RE = re.compile(r"(?:instagram\.com/|(?:^|\s)@)([A-Za-z0-9._]{2,30})")
SUBMIT_RE = re.compile(r"https?://(?:linktr\.ee|submithub\.com|groover\.co|beacons\.ai)/\S+", re.I)


def ensure_contact_source_column() -> None:
    conn = sqlite3.connect(db._DB_PATH)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(curators)").fetchall()}
        if "contact_source" not in cols:
            conn.execute("ALTER TABLE curators ADD COLUMN contact_source TEXT")
            conn.commit()
    finally:
        conn.close()


def fetch_playlist(playlist_id: str) -> dict:
    for _ in range(3):
        try:
            r = requests.get(f"{API}/playlist/{playlist_id}", headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and not data.get("error"):
                    return data
            if r.status_code == 429:
                time.sleep(3)
                continue
            return {}
        except Exception:
            time.sleep(2)
    return {}


def extract_contact(text: str) -> tuple[str, str] | None:
    """(contact, source) doner; email > submit-link > instagram onceligi."""
    if not text:
        return None
    email = EMAIL_RE.search(text)
    if email:
        return email.group(0).lower(), "deezer_desc_email"
    submit = SUBMIT_RE.search(text)
    if submit:
        return submit.group(0), "deezer_desc_link"
    ig = IG_RE.search(text)
    if ig:
        return f"@{ig.group(1)}", "deezer_desc_instagram"
    return None


def update_contact(curator_id: int, contact: str, source: str) -> None:
    conn = sqlite3.connect(db._DB_PATH)
    try:
        conn.execute(
            "UPDATE curators SET email = ?, contact_source = ? WHERE id = ?",
            (contact, source, curator_id),
        )
        conn.commit()
    finally:
        conn.close()


def leads_missing_contact(limit: int | None) -> list[dict]:
    conn = sqlite3.connect(db._DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT id, deezer_playlist_id, name FROM curators WHERE COALESCE(email,'') = ''"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


def run(limit: int | None = None) -> dict:
    ensure_contact_source_column()
    leads = leads_missing_contact(limit)
    found = 0
    by_source: dict[str, int] = {}
    for lead in leads:
        data = fetch_playlist(lead["deezer_playlist_id"])
        text = " ".join(str(data.get(k, "")) for k in ("title", "description"))
        hit = extract_contact(text)
        if hit:
            contact, source = hit
            update_contact(lead["id"], contact, source)
            found += 1
            by_source[source] = by_source.get(source, 0) + 1
        time.sleep(SLEEP)
    return {"scanned": len(leads), "found": found, "by_source": by_source}


def main(argv: list[str]) -> int:
    limit = int(argv[1]) if len(argv) > 1 else None
    result = run(limit)
    print(f"enrichment bitti — taranan:{result['scanned']} bulunan:{result['found']}")
    print(f"kaynak dagilimi: {result['by_source']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
