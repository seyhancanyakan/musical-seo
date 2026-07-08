"""IndexNow modulu testleri: submit (basarili/bos/ag hatasi/batch sinirlamasi),
get_key kararliligi (dosyaya bir kere yazilir, sonra hep aynisi okunur),
submit_slugs URL uretimi, ve build_next_batch'in yeni yazilan sanatci
sayfalarinin slug'larini submit_slugs'a ilettigini (ag olmadan, monkeypatch
ile) dogrulayan entegrasyon testi.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from marketplace import indexnow, seo_pages


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "ok"):
        self.status_code = status_code
        self.text = text


@pytest.fixture()
def key_file(tmp_path, monkeypatch):
    """indexnow._KEY_PATH'i gecici bir dosyaya yonlendirir; INDEXNOW_KEY ortam
    degiskenini de temizler ki gercek .env/ortam degeri testleri etkilemesin."""
    monkeypatch.delenv("INDEXNOW_KEY", raising=False)
    monkeypatch.setattr(indexnow, "_KEY_PATH", tmp_path / "indexnow_key.txt")
    return tmp_path / "indexnow_key.txt"


# --- submit ------------------------------------------------------------------

def test_submit_success_returns_ok_and_count(key_file, monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(200)

    monkeypatch.setattr(indexnow.requests, "post", fake_post)

    result = indexnow.submit(["http://localhost:3100/artist/drake"])

    assert result == {"ok": True, "submitted": 1}
    assert captured["url"] == indexnow.INDEXNOW_URL
    assert captured["json"]["urlList"] == ["http://localhost:3100/artist/drake"]
    assert captured["json"]["key"] == indexnow.get_key()
    assert captured["json"]["keyLocation"].endswith(f"{indexnow.get_key()}.txt")


def test_submit_empty_list_no_network_call(key_file, monkeypatch):
    def fake_post(*args, **kwargs):
        raise AssertionError("submit() bos liste icin ag istegi atmamali")

    monkeypatch.setattr(indexnow.requests, "post", fake_post)

    result = indexnow.submit([])

    assert result == {"ok": True, "submitted": 0}


def test_submit_network_error_returns_ok_false_no_crash(key_file, monkeypatch):
    def fake_post(*args, **kwargs):
        raise indexnow.requests.RequestException("baglanti koptu")

    monkeypatch.setattr(indexnow.requests, "post", fake_post)

    result = indexnow.submit(["http://localhost:3100/artist/drake"])

    assert result["ok"] is False
    assert result["submitted"] == 0
    assert "baglanti koptu" in result["error"]


def test_submit_non_success_status_returns_ok_false(key_file, monkeypatch):
    monkeypatch.setattr(
        indexnow.requests, "post", lambda *a, **k: _FakeResponse(500, "server error")
    )

    result = indexnow.submit(["http://localhost:3100/artist/drake"])

    assert result["ok"] is False
    assert result["submitted"] == 0
    assert "500" in result["error"]


def test_submit_batch_cap_sends_only_first_10000(key_file, monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["urlList"] = json["urlList"]
        return _FakeResponse(200)

    monkeypatch.setattr(indexnow.requests, "post", fake_post)

    urls = [f"http://localhost:3100/artist/artist-{i}" for i in range(10050)]
    result = indexnow.submit(urls)

    assert len(captured["urlList"]) == 10000
    assert result["submitted"] == 10000


# --- get_key -------------------------------------------------------------

def test_get_key_stable_across_calls(key_file):
    first = indexnow.get_key()
    second = indexnow.get_key()

    assert first == second
    assert key_file.read_text(encoding="utf-8").strip() == first


def test_get_key_env_var_takes_precedence(key_file, monkeypatch):
    monkeypatch.setenv("INDEXNOW_KEY", "sabit-test-anahtari")

    assert indexnow.get_key() == "sabit-test-anahtari"
    # Ortam degiskeni varken dosyaya yazilmaz.
    assert not key_file.exists()


# --- submit_slugs ----------------------------------------------------------

def test_submit_slugs_builds_correct_urls(key_file, monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["urlList"] = json["urlList"]
        return _FakeResponse(200)

    monkeypatch.setattr(indexnow.requests, "post", fake_post)

    result = indexnow.submit_slugs(["drake", "the-weeknd"])

    assert result == {"ok": True, "submitted": 2}
    assert captured["urlList"] == [
        f"{indexnow.SITE_URL}/artist/drake",
        f"{indexnow.SITE_URL}/artist/the-weeknd",
    ]


def test_submit_slugs_custom_prefix(key_file, monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["urlList"] = json["urlList"]
        return _FakeResponse(200)

    monkeypatch.setattr(indexnow.requests, "post", fake_post)

    indexnow.submit_slugs(["some-song"], path_prefix="/song/")

    assert captured["urlList"] == [f"{indexnow.SITE_URL}/song/some-song"]


def test_submit_slugs_empty_no_network_call(key_file, monkeypatch):
    def fake_post(*args, **kwargs):
        raise AssertionError("submit_slugs() bos liste icin ag istegi atmamali")

    monkeypatch.setattr(indexnow.requests, "post", fake_post)

    result = indexnow.submit_slugs([])

    assert result == {"ok": True, "submitted": 0}


# --- ping_google_sitemap ---------------------------------------------------

def test_ping_google_sitemap_network_error_no_crash(key_file, monkeypatch):
    def fake_get(*args, **kwargs):
        raise indexnow.requests.RequestException("timeout")

    monkeypatch.setattr(indexnow.requests, "get", fake_get)

    result = indexnow.ping_google_sitemap()

    assert result["ok"] is False
    assert "timeout" in result["error"]


def test_ping_google_sitemap_success(key_file, monkeypatch):
    monkeypatch.setattr(indexnow.requests, "get", lambda *a, **k: _FakeResponse(200))

    result = indexnow.ping_google_sitemap()

    assert result == {"ok": True}


# --- build_next_batch entegrasyonu (DB-izole, agsiz) -----------------------

def _fake_result(artist="Test Sanatci", score=80, found_sources=2):
    sources = [SimpleNamespace(found=True) for _ in range(found_sources)]
    sources += [SimpleNamespace(found=False) for _ in range(3 - found_sources)]
    return SimpleNamespace(
        resolved_artist=artist,
        score=score,
        sources=sources,
        findings=[],
        to_dict=lambda: {"resolved_artist": artist, "score": score},
    )


@pytest.fixture()
def seo_db(tmp_path, monkeypatch):
    monkeypatch.setattr(seo_pages, "_DB_PATH", tmp_path / "seo_pages.db")


def test_build_next_batch_calls_indexnow_submit_slugs_with_built_slugs(
    seo_db, monkeypatch
):
    seo_pages.enqueue_artist("Drake")
    monkeypatch.setattr(seo_pages.audit, "run_audit", lambda q: _fake_result())

    calls = []
    monkeypatch.setattr(
        indexnow, "submit_slugs", lambda slugs, **kw: calls.append(list(slugs))
    )

    result = seo_pages.build_next_batch()

    assert result == {"processed": 1, "built": 1, "thin": 0, "failed": 0}
    assert calls == [["test-sanatci"]]


def test_build_next_batch_indexnow_failure_does_not_affect_result(
    seo_db, monkeypatch
):
    """indexnow.submit_slugs beklenmedik bir istisna firlatsa bile
    build_next_batch'in donus degeri etkilenmemeli (guarded hook)."""
    seo_pages.enqueue_artist("Drake")
    monkeypatch.setattr(seo_pages.audit, "run_audit", lambda q: _fake_result())

    def _boom(slugs, **kw):
        raise RuntimeError("indexnow coktu")

    monkeypatch.setattr(indexnow, "submit_slugs", _boom)

    result = seo_pages.build_next_batch()

    assert result == {"processed": 1, "built": 1, "thin": 0, "failed": 0}


def test_build_next_batch_no_thin_no_indexnow_call(seo_db, monkeypatch):
    """Hicbir sayfa 'built' olmazsa (hepsi thin/failed) indexnow.submit_slugs
    hic cagrilmamali."""
    seo_pages.enqueue_artist("Bilinmeyen Sanatci")
    monkeypatch.setattr(
        seo_pages.audit, "run_audit",
        lambda q: _fake_result(score=None, found_sources=0),
    )

    calls = []
    monkeypatch.setattr(
        indexnow, "submit_slugs", lambda slugs, **kw: calls.append(list(slugs))
    )

    result = seo_pages.build_next_batch()

    assert result["built"] == 0
    assert calls == []
