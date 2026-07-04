"""Google / YouTube autocomplete scrape kaynagi — anahtar gerektirmez, print yok."""
from __future__ import annotations

import json

import requests

_URL = "https://suggestqueries.google.com/complete/search"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_TIMEOUT = 10


def suggest(query: str, engine: str = "google") -> list[str]:
    params = {"client": "firefox", "q": query, "hl": "tr"}
    if engine == "youtube":
        params["ds"] = "yt"

    try:
        resp = requests.get(
            _URL,
            params=params,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        try:
            data = json.loads(resp.content.decode("utf-8"))
        except UnicodeDecodeError:
            data = json.loads(resp.content.decode(resp.encoding or "iso-8859-1"))
        return list(data[1])
    except Exception:
        return []
