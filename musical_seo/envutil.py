"""Basit .env yukleyici (stdlib-only, python-dotenv yok).

load_env() proje kokundeki .env dosyasini okur, KEY=VALUE satirlarini parse eder
ve os.environ'da henuz olmayan anahtarlari set eder. Idempotent; dosya yoksa
sessizce doner.
"""
from __future__ import annotations

import os
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env() -> None:
    if not _ENV_PATH.is_file():
        return

    try:
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]

        if key not in os.environ:
            os.environ[key] = value
