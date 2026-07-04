"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { getAudit, type AuditResult } from "@/lib/api";
import styles from "./page.module.css";

const DEMO_QUERY = "Duman - Senden Daha Güzel";

const DEMO_AUDIT: AuditResult = {
  query: DEMO_QUERY,
  resolved_artist: "Duman",
  resolved_title: "Senden Daha Güzel",
  created_at: "2026-07-04T09:14:00",
  sources: [
    {
      source: "Spotify",
      found: true,
      title: "Senden Daha Güzel",
      artist: "Duman",
      isrc: "TRX932500147",
      release_date: "2026-06-12",
      popularity: 41,
      url: null,
      note: null,
    },
    {
      source: "Deezer",
      found: true,
      title: "Senden Daha Güzel",
      artist: "Duman",
      isrc: "TRX932500147",
      release_date: "2026-06-12",
      popularity: 38,
      url: null,
      note: null,
    },
    {
      source: "iTunes",
      found: true,
      title: "Senden Daha Güzel",
      artist: "Duman",
      isrc: "TRX932500147",
      release_date: "2026-06-12",
      popularity: null,
      url: null,
      note: null,
    },
    {
      source: "YouTube",
      found: false,
      title: null,
      artist: null,
      isrc: null,
      release_date: null,
      popularity: null,
      url: null,
      note: null,
    },
  ],
  keywords: [],
  findings: [
    {
      severity: "info",
      category: "presence",
      message: "YouTube'da bulunamadı (API anahtarı yok).",
      action:
        "YouTube Data API anahtarını bağla, kanal senkronizasyonunu tekrar tetikle.",
    },
    {
      severity: "ok",
      category: "keywords",
      message: "Sözleri aramasında görünüyor.",
      action: "Yok — bu alan sağlıklı, izlemeye devam et.",
    },
  ],
  subscores: {
    metadata: 100,
    presence: 95,
    consistency: 100,
    keywords: 100,
  },
  score: 99,
};

const SUBSCORE_LABELS: Record<string, string> = {
  metadata: "Metadata",
  presence: "Varlık",
  consistency: "Tutarlılık",
  keywords: "Anahtar Kelime",
};

const SUBSCORE_ORDER = ["metadata", "presence", "consistency", "keywords"];

const SEVERITY_LABELS: Record<AuditResult["findings"][number]["severity"], string> = {
  critical: "Kritik",
  warn: "Uyarı",
  info: "Bilgi",
  ok: "OK",
};

const SEVERITY_TAG_CLASS: Record<AuditResult["findings"][number]["severity"], string> = {
  critical: styles.findingTagCritical,
  warn: styles.findingTagWarn,
  info: styles.findingTagInfo,
  ok: styles.findingTagOk,
};

const MONTHS_TR = [
  "Oca",
  "Şub",
  "Mar",
  "Nis",
  "May",
  "Haz",
  "Tem",
  "Ağu",
  "Eyl",
  "Eki",
  "Kas",
  "Ara",
];

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return iso;
  const [, y, m, d] = match;
  const month = MONTHS_TR[parseInt(m, 10) - 1] ?? m;
  return `${parseInt(d, 10)} ${month} ${y}`;
}

function formatDateTime(iso: string): string {
  const datePart = formatDate(iso);
  const match = iso.match(/T(\d{2}):(\d{2})/);
  if (!match) return datePart;
  return `${datePart}, ${match[1]}:${match[2]}`;
}

function formatPopularity(popularity: number | null): string {
  return popularity != null ? `${popularity} / 100` : "—";
}

function getOverallLabel(score: number): string {
  if (score >= 90) return "Güçlü";
  if (score >= 70) return "İyi";
  if (score >= 50) return "Orta";
  return "Zayıf";
}

function getOrderedSubscoreEntries(
  subscores: Record<string, number>
): [string, number][] {
  const known = SUBSCORE_ORDER.filter((key) => key in subscores).map(
    (key) => [key, subscores[key]] as [string, number]
  );
  const rest = Object.keys(subscores)
    .filter((key) => !SUBSCORE_ORDER.includes(key))
    .map((key) => [key, subscores[key]] as [string, number]);
  return [...known, ...rest];
}

function subscoreBarClass(index: number): string {
  if (index === 0) return styles.barFillGreen;
  if (index === 3) return styles.barFillBlue;
  return "";
}

const NAV_LINKS = [
  { href: "/karne", label: "Karne", icon: "📊" },
  { href: "/playlistler", label: "Playlistler", icon: "🎧" },
  { href: "/kanit", label: "Kanıt", icon: "✅" },
  { href: "/curator/inbox", label: "Küratör Gelen Kutusu", icon: "📥" },
];

export default function KarnePage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<AuditResult | null>(null);
  const [loading, setLoading] = useState(false);

  const isDemo = result === null;
  const data = result ?? DEMO_AUDIT;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    try {
      const audit = await getAudit(trimmed);
      setResult(audit);
    } finally {
      setLoading(false);
    }
  }

  const orderedSubscores = getOrderedSubscoreEntries(data.subscores);

  return (
    <div className={styles.shell}>
      <div className={styles.topbar}>
        <div className={styles.logo}>MuzikSEO</div>
        <div className={styles.userChip}>
          👤 {data.resolved_artist} — Sanatçı Paneli
        </div>
      </div>

      <div className={styles.sidebar}>
        {NAV_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`${styles.navLink} ${
              link.href === "/karne" ? styles.navLinkActive : ""
            }`}
          >
            {link.icon} {link.label}
          </Link>
        ))}
      </div>

      <main className={styles.main}>
        <div className={`${styles.hard} ${styles.searchCard}`}>
          <form className={styles.searchForm} onSubmit={handleSubmit}>
            <div className={styles.searchInputWrap}>
              <input
                className="nb-input"
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Duman - Senden Daha Güzel"
                aria-label="Sanatçı - Şarkı"
              />
            </div>
            <button
              type="submit"
              className={`nb-btn ${styles.searchButton}`}
              disabled={loading}
            >
              {loading ? "Analiz Ediliyor..." : "Karne Çıkar"}
            </button>
          </form>
          {isDemo && (
            <div className={styles.demoBanner}>
              API&apos;ye ulaşılamadı — demo veri gösteriliyor
            </div>
          )}
        </div>

        <div className={styles.trackHead}>
          <div>
            <h1 className={styles.headline}>
              {data.resolved_artist} — {data.resolved_title}
            </h1>
            <div className={styles.trackSub}>
              Son analiz: {formatDateTime(data.created_at)} · Kaynak sayısı:{" "}
              {data.sources.length}
            </div>
          </div>
          <span className={styles.pill}>
            Genel Durum: {getOverallLabel(data.score)}
          </span>
        </div>

        <div className={styles.topGrid}>
          <div className={`${styles.hard} ${styles.scoreCard}`}>
            <div
              className={styles.scoreRing}
              style={{
                background: `conic-gradient(var(--blue) 0 ${data.score}%, #eee ${data.score}% 100%)`,
              }}
            >
              <div className={styles.num}>{data.score}</div>
              <div className={styles.lbl}>/ 100</div>
            </div>
            <div className={styles.trackName}>SEO KARNESİ</div>
          </div>

          <div className={`${styles.hard} ${styles.subscores}`}>
            {orderedSubscores.map(([key, value], index) => (
              <div key={key} className={styles.subscoreRow}>
                <div className={styles.subscoreLbl}>
                  {SUBSCORE_LABELS[key] ?? key}
                </div>
                <div className={styles.barTrack}>
                  <div
                    className={`${styles.barFill} ${subscoreBarClass(index)}`}
                    style={{ width: `${value}%` }}
                  />
                </div>
                <div className={styles.subscoreVal}>{value}</div>
              </div>
            ))}
          </div>
        </div>

        <span className={styles.sectionTag}>Bulgular</span>
        <div className={styles.findings}>
          {data.findings.map((finding, index) => (
            <div key={index} className={`${styles.hard} ${styles.finding}`}>
              <span
                className={`${styles.findingTag} ${SEVERITY_TAG_CLASS[finding.severity]}`}
              >
                {SEVERITY_LABELS[finding.severity]}
              </span>
              <div className={styles.findingText}>{finding.message}</div>
              {finding.action && (
                <div className={styles.findingTodo}>
                  <b>Yapılacak:</b> {finding.action}
                </div>
              )}
            </div>
          ))}
        </div>

        <span className={styles.sectionTag}>Kaynak Tablosu</span>
        <table className={`${styles.hard} ${styles.table}`}>
          <thead>
            <tr>
              <th>Kaynak</th>
              <th>Bulundu</th>
              <th>ISRC</th>
              <th>Yayın Tarihi</th>
              <th>Popülerlik</th>
            </tr>
          </thead>
          <tbody>
            {data.sources.map((source) => (
              <tr key={source.source}>
                <td>{source.source}</td>
                <td>
                  {source.found ? (
                    <span className={styles.badgeFound}>Evet</span>
                  ) : (
                    <span className={styles.badgeMissing}>Hayır</span>
                  )}
                </td>
                <td>{source.isrc ?? "—"}</td>
                <td>{formatDate(source.release_date)}</td>
                <td>{formatPopularity(source.popularity)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}
