"""marketplace.mailer testleri: Resend entegrasyonu TAMAMEN agsiz test edilir.

RESEND_API_KEY olmadan sifir ag istegi (skipped_no_key, mevcut/varsayilan
durum — tum diger 457 test bunun uzerine kuruludur); API key varken
monkeypatch'li requests.post ile 'sent'; aylik/gunluk tavan kontrolleri
(tavan dolunca HTTP'ye HIC ugramaz); dedupe_key ile ayni gun ayni
(category, to) icin ikinci gonderim engellenir; mail_stats sayaclari;
sablon yardimcilarinin (subject, html) donup kullanici degerlerini escape
ettigi. DB tmp_path'e izole (data/marketplace.db'ye dokunulmaz).
"""
from __future__ import annotations

import pytest

from marketplace import db, mailer, templates_email


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None, text="ok"):
        self.status_code = status_code
        self._json_body = json_body if json_body is not None else {"id": "email_123"}
        self.text = text

    def json(self):
        return self._json_body


@pytest.fixture()
def mailer_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "marketplace.db")


@pytest.fixture()
def no_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)


@pytest.fixture()
def with_key(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key-123")


# --- RESEND_API_KEY yok: agsiz no-op (mevcut/varsayilan durum) ---------------

def test_send_email_no_key_is_noop_no_network(mailer_db, no_key, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("RESEND_API_KEY yokken ag istegi atilmamali")

    monkeypatch.setattr(mailer.requests, "post", _boom)

    result = mailer.send_email("user@example.com", "Konu", "<p>govde</p>")

    assert result == {"ok": False, "skipped": "no_key"}


def test_send_email_no_key_logs_skipped_no_key(mailer_db, no_key):
    mailer.send_email("user@example.com", "Konu", "<p>x</p>", category="welcome")

    conn = mailer._connect()
    try:
        row = conn.execute("SELECT * FROM email_log").fetchone()
    finally:
        conn.close()

    assert row["status"] == "skipped_no_key"
    assert row["to_email"] == "user@example.com"


def test_mail_stats_disabled_without_key(mailer_db, no_key):
    stats = mailer.mail_stats()
    assert stats == {
        "sent_this_month": 0,
        "sent_today": 0,
        "monthly_cap": mailer._DEFAULT_MONTHLY_CAP,
        "daily_cap": mailer._DEFAULT_DAILY_CAP,
        "enabled": False,
    }


# --- API key var: basarili gonderim ------------------------------------------

def test_send_email_with_key_sends_and_logs(mailer_db, with_key, monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(200, {"id": "email_abc"})

    monkeypatch.setattr(mailer.requests, "post", fake_post)

    result = mailer.send_email(
        "user@example.com", "Konu", "<p>x</p>", category="welcome",
    )

    assert result == {"ok": True, "id": "email_abc"}
    assert captured["url"] == mailer._RESEND_URL
    assert captured["headers"]["Authorization"] == "Bearer test-key-123"
    assert captured["json"]["to"] == "user@example.com"
    assert captured["json"]["subject"] == "Konu"
    assert captured["timeout"] == mailer._REQUEST_TIMEOUT_SECONDS

    stats = mailer.mail_stats()
    assert stats["sent_this_month"] == 1
    assert stats["sent_today"] == 1
    assert stats["enabled"] is True


def test_send_email_http_failure_logs_failed(mailer_db, with_key, monkeypatch):
    monkeypatch.setattr(
        mailer.requests, "post",
        lambda *a, **k: _FakeResponse(500, text="server error"),
    )

    result = mailer.send_email("user@example.com", "Konu", "<p>x</p>")

    assert result["ok"] is False
    assert "500" in result["error"]
    assert mailer.mail_stats()["sent_this_month"] == 0


def test_send_email_network_error_no_crash(mailer_db, with_key, monkeypatch):
    def _boom(*a, **k):
        raise mailer.requests.RequestException("baglanti koptu")

    monkeypatch.setattr(mailer.requests, "post", _boom)

    result = mailer.send_email("user@example.com", "Konu", "<p>x</p>")

    assert result["ok"] is False
    assert "baglanti koptu" in result["error"]


# --- Aylik/gunluk tavan (free-tier koruması) ---------------------------------

def test_send_email_monthly_cap_blocks_no_network(mailer_db, with_key, monkeypatch):
    monkeypatch.setenv("MAIL_MONTHLY_CAP", "1")
    calls = []
    monkeypatch.setattr(
        mailer.requests, "post",
        lambda *a, **k: (calls.append(1), _FakeResponse(200))[1],
    )

    first = mailer.send_email("a@example.com", "Konu", "<p>x</p>")
    assert first["ok"] is True
    assert len(calls) == 1

    second = mailer.send_email("b@example.com", "Konu", "<p>x</p>")
    assert second == {"ok": False, "skipped": "cap"}
    assert len(calls) == 1  # ikinci cagri HTTP'ye hic ugramadi


def test_send_email_daily_cap_blocks_no_network(mailer_db, with_key, monkeypatch):
    monkeypatch.setenv("MAIL_DAILY_CAP", "1")
    calls = []
    monkeypatch.setattr(
        mailer.requests, "post",
        lambda *a, **k: (calls.append(1), _FakeResponse(200))[1],
    )

    mailer.send_email("a@example.com", "Konu", "<p>x</p>")
    result = mailer.send_email("b@example.com", "Konu", "<p>x</p>")

    assert result == {"ok": False, "skipped": "cap"}
    assert len(calls) == 1


def test_send_email_cap_logs_skipped_cap_status(mailer_db, with_key, monkeypatch):
    monkeypatch.setenv("MAIL_MONTHLY_CAP", "0")
    monkeypatch.setattr(mailer.requests, "post", lambda *a, **k: _FakeResponse(200))

    mailer.send_email("a@example.com", "Konu", "<p>x</p>")

    conn = mailer._connect()
    try:
        row = conn.execute("SELECT * FROM email_log").fetchone()
    finally:
        conn.close()
    assert row["status"] == "skipped_cap"


# --- dedupe_key ----------------------------------------------------------------

def test_send_email_dedupe_key_blocks_second_same_day(mailer_db, with_key, monkeypatch):
    calls = []
    monkeypatch.setattr(
        mailer.requests, "post",
        lambda *a, **k: (calls.append(1), _FakeResponse(200))[1],
    )

    first = mailer.send_email(
        "user@example.com", "Konu", "<p>x</p>", category="score", dedupe_key="ref-1",
    )
    second = mailer.send_email(
        "user@example.com", "Konu2", "<p>y</p>", category="score", dedupe_key="ref-2",
    )

    assert first["ok"] is True
    assert second == {"ok": False, "skipped": "dupe"}
    assert len(calls) == 1


def test_send_email_dedupe_only_applies_within_same_category(
    mailer_db, with_key, monkeypatch,
):
    monkeypatch.setattr(mailer.requests, "post", lambda *a, **k: _FakeResponse(200))

    mailer.send_email(
        "user@example.com", "Konu", "<p>x</p>", category="score", dedupe_key="r1",
    )
    result = mailer.send_email(
        "user@example.com", "Konu", "<p>x</p>", category="cover", dedupe_key="r2",
    )

    assert result["ok"] is True  # farkli kategori -> dedupe tetiklenmez


def test_send_email_without_dedupe_key_not_blocked(mailer_db, with_key, monkeypatch):
    monkeypatch.setattr(mailer.requests, "post", lambda *a, **k: _FakeResponse(200))

    first = mailer.send_email("user@example.com", "Konu", "<p>x</p>", category="welcome")
    second = mailer.send_email("user@example.com", "Konu", "<p>x</p>", category="welcome")

    assert first["ok"] is True
    assert second["ok"] is True  # dedupe_key verilmedigi icin engellenmez


# --- mail_stats ------------------------------------------------------------------

def test_mail_stats_counts_only_sent_status(mailer_db, with_key, monkeypatch):
    monkeypatch.setattr(mailer.requests, "post", lambda *a, **k: _FakeResponse(200))
    mailer.send_email("a@example.com", "Konu", "<p>x</p>")

    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    mailer.send_email("b@example.com", "Konu", "<p>x</p>")  # no_key -> sayilmaz

    stats = mailer.mail_stats()
    assert stats["sent_this_month"] == 1
    assert stats["sent_today"] == 1


# --- sablon yardimcilari (network yok, saf fonksiyonlar) -------------------------

def test_welcome_email_shape_and_escaping():
    subject, html_body = templates_email.welcome_email("<script>alert(1)</script>")

    assert isinstance(subject, str) and isinstance(html_body, str)
    assert "<script>alert(1)</script>" not in html_body
    assert "&lt;script&gt;" in html_body


def test_welcome_email_handles_empty_name():
    subject, html_body = templates_email.welcome_email("")
    assert subject and html_body


def test_cover_alert_email_escapes_detail_and_has_subject():
    subject, html_body = templates_email.cover_alert_email("Ali", "<b>tehlike</b>")

    assert "cover" in subject.lower()
    assert "<b>tehlike</b>" not in html_body
    assert "&lt;b&gt;tehlike&lt;/b&gt;" in html_body


def test_fraud_alert_email_escapes_detail():
    subject, html_body = templates_email.fraud_alert_email("Ali", "<i>risk</i>")

    assert "playlist" in subject.lower()
    assert "<i>risk</i>" not in html_body
    assert "&lt;i&gt;risk&lt;/i&gt;" in html_body


def test_score_alert_email_contains_scores_and_track():
    subject, html_body = templates_email.score_alert_email(
        "Ali", "Artist - Song", 45.0, 52.0,
    )

    assert "45" in html_body and "52" in html_body
    assert "Artist - Song" in html_body
    assert "Song" in subject


def test_score_alert_email_escapes_track_name():
    subject, html_body = templates_email.score_alert_email(
        "Ali", "<b>Xss</b> - Song", 10.0, 20.0,
    )

    assert "<b>Xss</b>" not in html_body


# --- import sanity ---------------------------------------------------------------

def test_module_imports_without_network():
    import marketplace.mailer  # noqa: F401
    import marketplace.templates_email  # noqa: F401
