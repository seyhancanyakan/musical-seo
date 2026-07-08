"""Top sanatci seed motoru testleri: azalan oncelik korunumu, uzun listede
MIN_PRIORITY tabani, idempotent yeniden seed, STARTER listesinin bos
olmamasi + essiz olmasi, build_next_batch'in en yuksek oncelikten baslamasi,
queue_stats sayimlari. Network YOK — audit.run_audit monkeypatch'lenir.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from marketplace import catalog_scout, seo_pages


@pytest.fixture()
def seo_db(tmp_path, monkeypatch):
    monkeypatch.setattr(seo_pages, "_DB_PATH", tmp_path / "seo_pages.db")


def _fake_result(artist: str, score: float = 80, found_sources: int = 2):
    sources = [SimpleNamespace(found=True) for _ in range(found_sources)]
    sources += [SimpleNamespace(found=False) for _ in range(3 - found_sources)]
    return SimpleNamespace(
        resolved_artist=artist,
        score=score,
        sources=sources,
        findings=[],
        to_dict=lambda: {"resolved_artist": artist, "score": score},
    )


def _pending_rows(order_by: str = "priority DESC, id ASC") -> list[dict]:
    conn = seo_pages._connect()
    try:
        rows = conn.execute(
            f"SELECT * FROM build_queue WHERE status = 'pending' ORDER BY {order_by}"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# --- seed_from_list: oncelik korunumu ----------------------------------------

def test_seed_from_list_preserves_descending_priority(seo_db):
    names = ["Birinci Sanatci", "Ikinci Sanatci", "Ucuncu Sanatci"]
    result = catalog_scout.seed_from_list(names, base_priority=100)
    assert result == {"queued": 3, "skipped": 0}

    rows = _pending_rows()
    assert [r["ref"] for r in rows] == names
    assert [r["priority"] for r in rows] == [100, 99, 98]


def test_seed_from_list_floors_priority_for_long_lists(seo_db):
    names = [f"Sanatci {i}" for i in range(10)]
    catalog_scout.seed_from_list(names, base_priority=5)

    rows = _pending_rows()
    priorities = {r["ref"]: r["priority"] for r in rows}
    # base_priority=5 ile index arttikca priority dusuyor, MIN_PRIORITY (1)
    # altina hicbir zaman inmemeli.
    assert min(priorities.values()) == catalog_scout.MIN_PRIORITY
    assert all(p >= catalog_scout.MIN_PRIORITY for p in priorities.values())


def test_seed_from_list_empty_raises(seo_db):
    with pytest.raises(ValueError):
        catalog_scout.seed_from_list([])


def test_seed_from_list_skips_blank_names(seo_db):
    result = catalog_scout.seed_from_list(["Gercek Isim", "   ", ""], base_priority=10)
    assert result == {"queued": 1, "skipped": 2}


# --- idempotent yeniden seed --------------------------------------------------

def test_seed_from_list_idempotent_reseed(seo_db):
    names = ["Tekrar Sanatci A", "Tekrar Sanatci B"]
    first = catalog_scout.seed_from_list(names, base_priority=50)
    second = catalog_scout.seed_from_list(names, base_priority=50)

    assert first == {"queued": 2, "skipped": 0}
    assert second == {"queued": 2, "skipped": 0}  # enqueue_artist yine "basarili" sayar

    conn = seo_pages._connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM build_queue WHERE status = 'pending'"
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 2  # ikinci seed yeni satir ACMADI


# --- STARTER_TOP_ARTISTS -------------------------------------------------------

def test_starter_top_artists_non_empty():
    assert len(catalog_scout.STARTER_TOP_ARTISTS) >= 100


def test_starter_top_artists_unique():
    names = catalog_scout.STARTER_TOP_ARTISTS
    assert len(names) == len(set(names))


def test_starter_top_artists_no_blank_entries():
    assert all(name and name.strip() for name in catalog_scout.STARTER_TOP_ARTISTS)


def test_seed_starter_queues_all(seo_db):
    result = catalog_scout.seed_starter()
    assert result["queued"] == len(catalog_scout.STARTER_TOP_ARTISTS)
    assert result["skipped"] == 0

    rows = _pending_rows()
    assert len(rows) == len(catalog_scout.STARTER_TOP_ARTISTS)
    # Ilk sanatci en yuksek onceligi almali.
    assert rows[0]["ref"] == catalog_scout.STARTER_TOP_ARTISTS[0]


# --- build_next_batch: en yuksek oncelikten baslama ---------------------------

def test_build_next_batch_consumes_highest_priority_first(seo_db, monkeypatch):
    # Karisik sirayla ekle: dusuk, yuksek, orta oncelik.
    seo_pages.enqueue_artist("Dusuk Oncelik", priority=1)
    seo_pages.enqueue_artist("Yuksek Oncelik", priority=1000)
    seo_pages.enqueue_artist("Orta Oncelik", priority=500)

    call_order: list[str] = []

    def _stub_audit(artist_name: str):
        call_order.append(artist_name)
        return _fake_result(artist_name)

    monkeypatch.setattr(seo_pages.audit, "run_audit", _stub_audit)

    result = seo_pages.build_next_batch(limit=3)

    assert result == {"processed": 3, "built": 3, "thin": 0, "failed": 0}
    assert call_order == ["Yuksek Oncelik", "Orta Oncelik", "Dusuk Oncelik"]


def test_build_next_batch_respects_starter_seed_order(seo_db, monkeypatch):
    catalog_scout.seed_from_list(["Ilk Sira", "Ikinci Sira", "Ucuncu Sira"], base_priority=100)

    call_order: list[str] = []

    def _stub_audit(artist_name: str):
        call_order.append(artist_name)
        return _fake_result(artist_name)

    monkeypatch.setattr(seo_pages.audit, "run_audit", _stub_audit)
    seo_pages.build_next_batch(limit=10)

    assert call_order == ["Ilk Sira", "Ikinci Sira", "Ucuncu Sira"]


# --- queue_stats ---------------------------------------------------------------

def test_queue_stats_counts(seo_db, monkeypatch):
    seo_pages.enqueue_artist("Basarili Sanatci", priority=10)
    seo_pages.enqueue_artist("Ince Icerik", priority=5)
    seo_pages.enqueue_artist("Patlayan Sorgu", priority=1)
    seo_pages.enqueue_artist("Bekleyen Sanatci", priority=1)

    def _stub_audit(artist_name: str):
        if artist_name == "Basarili Sanatci":
            return _fake_result(artist_name, score=80, found_sources=2)
        if artist_name == "Ince Icerik":
            return _fake_result(artist_name, score=None, found_sources=0)
        raise RuntimeError("network down")

    monkeypatch.setattr(seo_pages.audit, "run_audit", _stub_audit)
    seo_pages.build_next_batch(limit=3)  # "Bekleyen Sanatci" kuyrukta kalir

    stats = seo_pages.queue_stats()
    assert stats == {"pending": 1, "done": 1, "thin": 1, "failed": 1}


def test_queue_stats_empty_queue(seo_db):
    stats = seo_pages.queue_stats()
    assert stats == {"pending": 0, "done": 0, "thin": 0, "failed": 0}
