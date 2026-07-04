"""HTML rapor uretimi -- "Muzik SEO Karnesi".

Bu modul musical_seo.models.AuditResult nesnesini tek, kendi kendine yeten
(harici asset yok, inline CSS) Turkce bir HTML dokumanina donusturur.
Kutuphane modulu: print yok, dosya yazmaz -- sadece string doner.
"""
from __future__ import annotations

import html as _html

from musical_seo.models import AuditResult, Finding, KeywordHit, TrackInfo

_SEVERITY_ORDER = ["critical", "warn", "info", "ok"]

_SEVERITY_LABELS = {
    "critical": "Kritik",
    "warn": "Uyari",
    "info": "Bilgi",
    "ok": "Tamam",
}

_SEVERITY_COLORS = {
    "critical": "#dc2626",
    "warn": "#d97706",
    "info": "#2563eb",
    "ok": "#16a34a",
}

_CATEGORY_LABELS = {
    "metadata": "Metadata",
    "presence": "Varlik",
    "consistency": "Tutarlilik",
    "keywords": "Anahtar Kelime",
}

_SOURCE_LABELS = {
    "spotify": "Spotify",
    "deezer": "Deezer",
    "itunes": "iTunes",
    "youtube": "YouTube",
}


def _esc(value: object) -> str:
    """None -> bos string, digerleri str() + html.escape."""
    if value is None:
        return ""
    return _html.escape(str(value))


def _score_color(score: int) -> str:
    if score >= 80:
        return "#16a34a"
    if score >= 50:
        return "#d97706"
    return "#dc2626"


def _score_ring(score: int) -> str:
    score = max(0, min(100, score))
    color = _score_color(score)
    deg = round(score * 3.6, 1)
    return (
        '<div class="score-ring" style="'
        f'background: conic-gradient({color} 0deg {deg}deg, #e5e7eb {deg}deg 360deg);">'
        '<div class="score-ring-inner">'
        f'<span class="score-number" style="color:{color}">{score}</span>'
        '<span class="score-max">/100</span>'
        '</div></div>'
    )


def _subscore_bars(subscores: dict[str, int]) -> str:
    if not subscores:
        return '<p class="empty-note">Alt skor verisi yok.</p>'
    rows = []
    for category, value in subscores.items():
        value = max(0, min(100, value))
        color = _score_color(value)
        label = _esc(_CATEGORY_LABELS.get(category, category))
        rows.append(
            '<div class="bar-row">'
            f'<div class="bar-label">{label}</div>'
            '<div class="bar-track">'
            f'<div class="bar-fill" style="width:{value}%; background:{color}"></div>'
            '</div>'
            f'<div class="bar-value" style="color:{color}">{value}</div>'
            '</div>'
        )
    return "".join(rows)


def _findings_section(findings: list[Finding]) -> str:
    if not findings:
        return '<p class="empty-note">Bulgu yok.</p>'

    grouped: dict[str, list[Finding]] = {sev: [] for sev in _SEVERITY_ORDER}
    for finding in findings:
        grouped.setdefault(finding.severity, [])
        grouped[finding.severity].append(finding)

    blocks = []
    for severity in _SEVERITY_ORDER:
        items = grouped.get(severity, [])
        if not items:
            continue
        color = _SEVERITY_COLORS.get(severity, "#6b7280")
        label = _esc(_SEVERITY_LABELS.get(severity, severity))
        cards = []
        for finding in items:
            action_html = ""
            if finding.action:
                action_html = (
                    f'<div class="finding-action">Yapilacak: {_esc(finding.action)}</div>'
                )
            category_label = _esc(_CATEGORY_LABELS.get(finding.category, finding.category))
            cards.append(
                '<div class="finding-card" style="border-left-color:{color}">'
                '<div class="finding-head">'
                f'<span class="finding-category">{category_label}</span>'
                '</div>'
                f'<div class="finding-message">{_esc(finding.message)}</div>'
                f'{action_html}'
                '</div>'.format(color=color)
            )
        blocks.append(
            '<div class="finding-group">'
            f'<h3 class="finding-group-title" style="color:{color}">'
            f'<span class="dot" style="background:{color}"></span>{label} '
            f'<span class="count">({len(items)})</span></h3>'
            f'<div class="finding-cards">{"".join(cards)}</div>'
            '</div>'
        )
    return "".join(blocks)


def _source_row(track: TrackInfo) -> str:
    source_label = _esc(_SOURCE_LABELS.get(track.source, track.source))
    if track.found:
        found_html = '<span class="badge badge-ok">Evet</span>'
    else:
        found_html = '<span class="badge badge-no">Hayir</span>'
        note = f'<div class="note">{_esc(track.note)}</div>' if track.note else ""
        return (
            "<tr>"
            f"<td>{source_label}</td>"
            f"<td>{found_html}</td>"
            f'<td colspan="6" class="muted">{note or "-"}</td>'
            "</tr>"
        )

    if track.url:
        link_html = f'<a href="{_esc(track.url)}" target="_blank" rel="noopener">Ac</a>'
    else:
        link_html = '<span class="muted">-</span>'

    popularity = "-" if track.popularity is None else _esc(track.popularity)
    duration = "-"
    if track.duration_ms is not None:
        total_seconds = track.duration_ms // 1000
        minutes, seconds = divmod(total_seconds, 60)
        duration = f"{minutes}:{seconds:02d}"

    return (
        "<tr>"
        f"<td>{source_label}</td>"
        f"<td>{found_html}</td>"
        f'<td>{_esc(track.title) or "-"}</td>'
        f'<td>{_esc(track.artist) or "-"}</td>'
        f'<td>{_esc(track.isrc) or "-"}</td>'
        f'<td>{_esc(track.release_date) or "-"}</td>'
        f'<td>{popularity} <span class="muted">({duration})</span></td>'
        f"<td>{link_html}</td>"
        "</tr>"
    )


def _sources_table(sources: list[TrackInfo]) -> str:
    if not sources:
        return '<p class="empty-note">Kaynak verisi yok.</p>'
    rows = "".join(_source_row(track) for track in sources)
    return (
        '<div class="table-wrap"><table class="sources-table">'
        "<thead><tr>"
        "<th>Kaynak</th><th>Bulundu</th><th>Baslik</th><th>Sanatci</th>"
        "<th>ISRC</th><th>Yayin Tarihi</th><th>Populerlik</th><th>Link</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table></div>"
    )


def _keyword_hit_card(hit: KeywordHit) -> str:
    if hit.suggestions:
        chips = "".join(
            f'<span class="chip">{_esc(suggestion)}</span>' for suggestion in hit.suggestions
        )
    else:
        chips = '<span class="muted">Oneri yok</span>'

    artist_badge = (
        '<span class="badge badge-ok">Sanatci var</span>'
        if hit.artist_present
        else '<span class="badge badge-no">Sanatci yok</span>'
    )
    track_badge = (
        '<span class="badge badge-ok">Sarki var</span>'
        if hit.track_present
        else '<span class="badge badge-no">Sarki yok</span>'
    )

    return (
        '<div class="keyword-card">'
        '<div class="keyword-head">'
        f'<span class="keyword-query">"{_esc(hit.query)}"</span>'
        f'<span class="keyword-engine">{_esc(hit.engine)}</span>'
        "</div>"
        f'<div class="keyword-chips">{chips}</div>'
        f'<div class="keyword-badges">{artist_badge}{track_badge}</div>'
        "</div>"
    )


def _keywords_section(keywords: list[KeywordHit]) -> str:
    if not keywords:
        return '<p class="empty-note">Anahtar kelime verisi yok.</p>'
    return "".join(_keyword_hit_card(hit) for hit in keywords)


_CSS = """
:root {
  color-scheme: light;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 0;
  background: #f3f4f6;
  color: #111827;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
    Arial, sans-serif;
}
.page {
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 20px 60px;
}
header.report-header {
  text-align: center;
  margin-bottom: 28px;
}
header.report-header h1 {
  font-size: 26px;
  margin: 0 0 6px;
  font-weight: 700;
  color: #111827;
}
header.report-header .subtitle {
  color: #6b7280;
  font-size: 14px;
  margin: 0;
}
.card {
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
  padding: 24px;
  margin-bottom: 20px;
}
.card h2 {
  font-size: 15px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
  margin: 0 0 18px;
  font-weight: 600;
}
.score-section {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.score-ring {
  width: 180px;
  height: 180px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.score-ring-inner {
  width: 144px;
  height: 144px;
  border-radius: 50%;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.score-number {
  font-size: 46px;
  font-weight: 800;
  line-height: 1;
}
.score-max {
  font-size: 13px;
  color: #9ca3af;
  margin-top: 4px;
}
.bar-row {
  display: grid;
  grid-template-columns: 140px 1fr 40px;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.bar-label {
  font-size: 13px;
  color: #374151;
  font-weight: 600;
}
.bar-track {
  background: #e5e7eb;
  border-radius: 999px;
  height: 10px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 999px;
}
.bar-value {
  font-size: 13px;
  font-weight: 700;
  text-align: right;
}
.finding-group {
  margin-bottom: 18px;
}
.finding-group:last-child { margin-bottom: 0; }
.finding-group-title {
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 10px;
}
.finding-group-title .dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
}
.finding-group-title .count {
  color: #9ca3af;
  font-weight: 500;
}
.finding-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.finding-card {
  background: #f9fafb;
  border-left: 4px solid #9ca3af;
  border-radius: 8px;
  padding: 10px 14px;
}
.finding-category {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6b7280;
  font-weight: 700;
}
.finding-message {
  font-size: 14px;
  color: #1f2937;
  margin-top: 2px;
}
.finding-action {
  font-size: 13px;
  color: #4b5563;
  margin-top: 4px;
  font-style: italic;
}
.table-wrap {
  overflow-x: auto;
}
table.sources-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
table.sources-table th {
  text-align: left;
  color: #6b7280;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 2px solid #e5e7eb;
  padding: 8px 10px;
  white-space: nowrap;
}
table.sources-table td {
  padding: 10px;
  border-bottom: 1px solid #f0f1f3;
  vertical-align: middle;
  white-space: nowrap;
}
table.sources-table a {
  color: #2563eb;
  text-decoration: none;
  font-weight: 600;
}
table.sources-table a:hover { text-decoration: underline; }
.badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.badge-ok { background: #dcfce7; color: #15803d; }
.badge-no { background: #fee2e2; color: #b91c1c; }
.muted { color: #9ca3af; }
.empty-note { color: #9ca3af; font-size: 13px; margin: 0; }
.keyword-card {
  background: #f9fafb;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 12px;
}
.keyword-card:last-child { margin-bottom: 0; }
.keyword-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}
.keyword-query {
  font-weight: 700;
  font-size: 14px;
  color: #111827;
}
.keyword-engine {
  font-size: 11px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: #e5e7eb;
  padding: 2px 8px;
  border-radius: 999px;
}
.keyword-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.chip {
  background: #eef2ff;
  color: #3730a3;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  font-weight: 600;
}
.keyword-badges {
  display: flex;
  gap: 6px;
}
footer.report-footer {
  text-align: center;
  color: #9ca3af;
  font-size: 12px;
  margin-top: 24px;
}
"""


def render_html(result: AuditResult) -> str:
    """AuditResult icin tek, kendi kendine yeten Turkce HTML raporu uretir."""
    artist = _esc(result.resolved_artist) or "Bilinmeyen Sanatci"
    title = _esc(result.resolved_title) or "Bilinmeyen Sarki"
    created_at = _esc(result.created_at)
    query = _esc(result.query)

    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{artist} — {title} | Muzik SEO Karnesi</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">
  <header class="report-header">
    <h1>{artist} — {title} | Muzik SEO Karnesi</h1>
    <p class="subtitle">Sorgu: "{query}" &middot; Olusturulma: {created_at}</p>
  </header>

  <section class="card score-section">
    <h2 style="align-self:flex-start">Genel Skor</h2>
    {_score_ring(result.score)}
  </section>

  <section class="card">
    <h2>Kategori Alt Skorlari</h2>
    {_subscore_bars(result.subscores)}
  </section>

  <section class="card">
    <h2>Bulgular</h2>
    {_findings_section(result.findings)}
  </section>

  <section class="card">
    <h2>Kaynak Tablosu</h2>
    {_sources_table(result.sources)}
  </section>

  <section class="card">
    <h2>Anahtar Kelime Analizi</h2>
    {_keywords_section(result.keywords)}
  </section>

  <footer class="report-footer">musical-seo v0.1 — {created_at}</footer>
</div>
</body>
</html>
"""
