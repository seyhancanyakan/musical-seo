"""Paylasilan pytest fixture'lari.

Guvenlik agi: `marketplace.seo_pages.build_next_batch` artik basarili
sanatci sayfalarini `marketplace.indexnow.submit_slugs` ile bildiriyor
(bkz. docs/PROGRAMATIK_SEO_WORKFLOW.md §10). indexnow'u hic
monkeypatch'lemeyen testler (orn. test_seo_pages.py'deki build_next_batch
testleri) yanlislikla GERCEK IndexNow API'sine istek atmasin ve gercek
`data/indexnow_key.txt` dosyasina yazmasin diye, her testte otomatik
(autouse) olarak anahtar dosyasi gecici bir yola yonlendirilir ve
requests.post/get engellenir. indexnow'un kendi davranisini test eden
testler (tests/test_indexnow.py) bu varsayilanin uzerine kendi
monkeypatch'lerini uygular (ayni `monkeypatch` fixture ornegi, son yazan
kazanir) — cakisma olmaz.
"""
from __future__ import annotations

import pytest

from marketplace import indexnow


@pytest.fixture(autouse=True)
def _no_real_indexnow_network(tmp_path, monkeypatch):
    monkeypatch.setattr(indexnow, "_KEY_PATH", tmp_path / "indexnow_key.txt")

    def _blocked_post(*args, **kwargs):
        raise indexnow.requests.RequestException(
            "test ortaminda gercek IndexNow istegi engellendi (conftest guard)"
        )

    def _blocked_get(*args, **kwargs):
        raise indexnow.requests.RequestException(
            "test ortaminda gercek Google ping istegi engellendi (conftest guard)"
        )

    monkeypatch.setattr(indexnow.requests, "post", _blocked_post)
    monkeypatch.setattr(indexnow.requests, "get", _blocked_get)
