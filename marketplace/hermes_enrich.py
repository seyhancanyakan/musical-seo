"""Hermes AI web-research enrichment — curator iletisimini internetten bul.

Sunucudaki Hermes agent'ini (hermes -z --yolo, headless) surerek, lead'ler icin
SADECE halka acik gonderim iletisimi arar (public submit email/linktr.ee/submithub).
Sonucu marketplace.db'ye yazar + kaynak URL isaretler (manuel dogrulama icin).

YASAL SINIR: prompt agent'a ozel/rizasiz veri toplamamasini, login-duvarli site
kazimamasini soyler. Sadece curator'in gonderim icin yayinladigi iletisim.

Config (ENV — sifre KODA GOMULMEZ):
    HERMES_SSH_HOST, HERMES_SSH_USER, HERMES_SSH_PASSWORD

Kullanim:
    HERMES_SSH_PASSWORD=... python -m marketplace.hermes_enrich [batch_size]
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import time

try:
    import paramiko
except ImportError:  # pragma: no cover
    paramiko = None

from marketplace import db

HERMES_DIR = "/usr/local/lib/hermes-agent"
PROMPT_PATH = "/root/hermes_enrich_prompt.txt"
OUT_PATH = "/root/hermes_enrich_out.txt"
DONE_PATH = "/root/hermes_enrich.done"
RESULT_RE = re.compile(r"^(\d+)\|(.+?)\|(.+?)\|([0-9.]+)\s*$")
NONE_RE = re.compile(r"^(\d+)\|NONE\s*$")

PROMPT_HEAD = (
    "You are a B2B music-curator contact researcher. For EACH curator below, use web "
    "search to find ONLY the contact they have PUBLICLY PUBLISHED for receiving music "
    "submissions (public submission email, linktr.ee, submithub/groover page, or an "
    "official 'submit your music' page). Do NOT guess. Do NOT use private/personal data "
    "or scrape login-walled sites. If no public submission contact exists, output NONE.\n\n"
    "Output STRICT, one line per curator, nothing else:\n"
    "ID|CONTACT|SOURCE_URL|CONFIDENCE(0-1)\n"
    "or\n"
    "ID|NONE\n\n"
    "Curators:\n"
)


def _ssh():
    if paramiko is None:
        raise RuntimeError("paramiko yuklu degil: pip install paramiko")
    host = os.environ.get("HERMES_SSH_HOST")
    user = os.environ.get("HERMES_SSH_USER", "root")
    password = os.environ.get("HERMES_SSH_PASSWORD")
    if not host or not password:
        raise RuntimeError("HERMES_SSH_HOST ve HERMES_SSH_PASSWORD ENV gerekli")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, username=user, password=password,
              look_for_keys=False, allow_agent=False, timeout=25)
    return c


def _ensure_columns() -> None:
    conn = sqlite3.connect(db._DB_PATH)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(curators)")}
        for col, typ in (("contact_source", "TEXT"), ("source_url", "TEXT"),
                         ("contact_confidence", "REAL")):
            if col not in cols:
                conn.execute(f"ALTER TABLE curators ADD COLUMN {col} {typ}")
        conn.commit()
    finally:
        conn.close()


def _pending_leads(limit: int) -> list[dict]:
    conn = sqlite3.connect(db._DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, name, playlist_title, playlist_url FROM curators "
            "WHERE COALESCE(email,'') = '' AND COALESCE(contact_source,'') = '' "
            f"LIMIT {int(limit)}"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _apply(curator_id: int, contact: str, source_url: str, confidence: float) -> None:
    conn = sqlite3.connect(db._DB_PATH)
    try:
        conn.execute(
            "UPDATE curators SET email=?, source_url=?, contact_source='hermes_web', "
            "contact_confidence=? WHERE id=?",
            (contact, source_url, confidence, curator_id),
        )
        conn.commit()
    finally:
        conn.close()


def _mark_none(curator_id: int) -> None:
    conn = sqlite3.connect(db._DB_PATH)
    try:
        conn.execute(
            "UPDATE curators SET contact_source='hermes_web_none' WHERE id=?",
            (curator_id,),
        )
        conn.commit()
    finally:
        conn.close()


def run(batch_size: int = 10, poll_timeout: int = 360) -> dict:
    _ensure_columns()
    leads = _pending_leads(batch_size)
    if not leads:
        return {"scanned": 0, "found": 0, "none": 0}

    prompt = PROMPT_HEAD + "\n".join(
        f'{d["id"]}: name="{d["name"]}" playlist="{d["playlist_title"]}" {d["playlist_url"]}'
        for d in leads
    )

    c = _ssh()
    try:
        sftp = c.open_sftp()
        with sftp.open(PROMPT_PATH, "w") as f:
            f.write(prompt)
        sftp.close()

        inner = (
            f'./venv/bin/python -m hermes_cli.main -z "$(cat {PROMPT_PATH})" '
            f"--yolo > {OUT_PATH} 2>&1; touch {DONE_PATH}"
        )
        launch = (
            f"cd {HERMES_DIR} && rm -f {OUT_PATH} {DONE_PATH} && "
            f"setsid bash -c '{inner}' </dev/null >/dev/null 2>&1 &"
        )
        c.exec_command(launch, timeout=20)

        deadline = time.time() + poll_timeout
        done = False
        while time.time() < deadline:
            _, o, _ = c.exec_command(f"test -f {DONE_PATH} && echo YES || echo NO", timeout=20)
            if "YES" in o.read().decode("utf-8", "replace"):
                done = True
                break
            time.sleep(15)

        _, o, _ = c.exec_command(f"cat {OUT_PATH} 2>/dev/null", timeout=25)
        output = o.read().decode("utf-8", "replace")
    finally:
        c.close()

    found = none = 0
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if (m := RESULT_RE.match(line)):
            cid, contact, url, conf = m.groups()
            try:
                _apply(int(cid), contact.strip(), url.strip(), float(conf))
                found += 1
            except (ValueError, sqlite3.Error):
                pass
        elif (m := NONE_RE.match(line)):
            _mark_none(int(m.group(1)))
            none += 1

    return {"scanned": len(leads), "found": found, "none": none, "done": done}


def main(argv: list[str]) -> int:
    batch = int(argv[1]) if len(argv) > 1 else 10
    result = run(batch)
    print(f"hermes enrichment — taranan:{result['scanned']} "
          f"bulunan:{result['found']} iletisim-yok:{result.get('none', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
