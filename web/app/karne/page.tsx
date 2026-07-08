"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { getAudit, type AuditResult } from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

const DEMO_QUERY = "Duman - Senden Daha Güzel";

/** Demo bulgularin sabit (locale-bagimsiz) kismi — severity/category. Metin T sozlugunden gelir. */
const DEMO_FINDINGS_META: {
  severity: AuditResult["findings"][number]["severity"];
  category: string;
}[] = [
  { severity: "info", category: "presence" },
  { severity: "ok", category: "keywords" },
];

const DEMO_AUDIT_BASE: Omit<AuditResult, "findings"> = {
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
  subscores: {
    metadata: 100,
    presence: 95,
    consistency: 100,
    keywords: 100,
  },
  score: 99,
};

const SUBSCORE_ORDER = ["metadata", "presence", "consistency", "keywords"];

const SEVERITY_TAG_CLASS: Record<AuditResult["findings"][number]["severity"], string> = {
  critical: styles.findingTagCritical,
  warn: styles.findingTagWarn,
  info: styles.findingTagInfo,
  ok: styles.findingTagOk,
};

const T = {
  tr: {
    months: [
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
    ],
    subscoreLabels: {
      metadata: "Metadata",
      presence: "Varlık",
      consistency: "Tutarlılık",
      keywords: "Anahtar Kelime",
    } as Record<string, string>,
    severityLabels: {
      critical: "Kritik",
      warn: "Uyarı",
      info: "Bilgi",
      ok: "OK",
    },
    overallLabels: { strong: "Güçlü", good: "İyi", medium: "Orta", weak: "Zayıf" },
    nav: [
      { href: "/karne", label: "Karne", icon: "📊" },
      { href: "/playlistler", label: "Playlistler", icon: "🎧" },
      { href: "/kanit", label: "Kanıt", icon: "✅" },
      { href: "/curator/inbox", label: "Küratör Gelen Kutusu", icon: "📥" },
    ],
    userChipSuffix: "— Sanatçı Paneli",
    searchPlaceholder: DEMO_QUERY,
    searchAria: "Sanatçı - Şarkı",
    analyzing: "Analiz Ediliyor...",
    submit: "Karne Çıkar",
    demoBanner: "API'ye ulaşılamadı — demo veri gösteriliyor",
    lastAnalysis: "Son analiz:",
    sourceCount: "Kaynak sayısı:",
    overallStatus: "Genel Durum:",
    scoreCardLabel: "SEO KARNESİ",
    findingsTag: "Bulgular",
    todoLabel: "Yapılacak:",
    sourceTableTag: "Kaynak Tablosu",
    th: {
      source: "Kaynak",
      found: "Bulundu",
      isrc: "ISRC",
      releaseDate: "Yayın Tarihi",
      popularity: "Popülerlik",
    },
    yes: "Evet",
    no: "Hayır",
    demoFindingMessages: [
      {
        message: "YouTube'da bulunamadı (API anahtarı yok).",
        action:
          "YouTube Data API anahtarını bağla, kanal senkronizasyonunu tekrar tetikle.",
      },
      {
        message: "Sözleri aramasında görünüyor.",
        action: "Yok — bu alan sağlıklı, izlemeye devam et.",
      },
    ],
  },
  en: {
    months: [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "May",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
      "Dec",
    ],
    subscoreLabels: {
      metadata: "Metadata",
      presence: "Presence",
      consistency: "Consistency",
      keywords: "Keywords",
    } as Record<string, string>,
    severityLabels: {
      critical: "Critical",
      warn: "Warning",
      info: "Info",
      ok: "OK",
    },
    overallLabels: { strong: "Strong", good: "Good", medium: "Fair", weak: "Weak" },
    nav: [
      { href: "/karne", label: "Scorecard", icon: "📊" },
      { href: "/playlistler", label: "Playlists", icon: "🎧" },
      { href: "/kanit", label: "Proof", icon: "✅" },
      { href: "/curator/inbox", label: "Curator Inbox", icon: "📥" },
    ],
    userChipSuffix: "— Artist Panel",
    searchPlaceholder: DEMO_QUERY,
    searchAria: "Artist - Song",
    analyzing: "Analyzing...",
    submit: "Run Scorecard",
    demoBanner: "API unreachable — showing demo data",
    lastAnalysis: "Last analysis:",
    sourceCount: "Source count:",
    overallStatus: "Overall Status:",
    scoreCardLabel: "SEO SCORECARD",
    findingsTag: "Findings",
    todoLabel: "To do:",
    sourceTableTag: "Source Table",
    th: {
      source: "Source",
      found: "Found",
      isrc: "ISRC",
      releaseDate: "Release Date",
      popularity: "Popularity",
    },
    yes: "Yes",
    no: "No",
    demoFindingMessages: [
      {
        message: "Not found on YouTube (no API key).",
        action: "Connect a YouTube Data API key, retrigger channel sync.",
      },
      {
        message: "Appears in lyrics search.",
        action: "None — this field is healthy, keep monitoring.",
      },
    ],
  },
};

function formatDate(iso: string | null, months: string[]): string {
  if (!iso) return "—";
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return iso;
  const [, y, m, d] = match;
  const month = months[parseInt(m, 10) - 1] ?? m;
  return `${parseInt(d, 10)} ${month} ${y}`;
}

function formatDateTime(iso: string, months: string[]): string {
  const datePart = formatDate(iso, months);
  const match = iso.match(/T(\d{2}):(\d{2})/);
  if (!match) return datePart;
  return `${datePart}, ${match[1]}:${match[2]}`;
}

function formatPopularity(popularity: number | null): string {
  return popularity != null ? `${popularity} / 100` : "—";
}

function getOverallLabel(
  score: number,
  labels: { strong: string; good: string; medium: string; weak: string }
): string {
  if (score >= 90) return labels.strong;
  if (score >= 70) return labels.good;
  if (score >= 50) return labels.medium;
  return labels.weak;
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

export default function KarnePage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [query, setQuery] = useState("");
  const [result, setResult] = useState<AuditResult | null>(null);
  const [loading, setLoading] = useState(false);

  const demoFindings = DEMO_FINDINGS_META.map((meta, i) => ({
    ...meta,
    ...t.demoFindingMessages[i],
  }));
  const demoAudit: AuditResult = { ...DEMO_AUDIT_BASE, findings: demoFindings };

  const isDemo = result === null;
  const data = result ?? demoAudit;

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
        <Link href="/" className={styles.logo}>Songdeck</Link>
        <div className={styles.userChip}>
          👤 {data.resolved_artist} {t.userChipSuffix}
        </div>
        <LangToggle />
      </div>

      <div className={styles.sidebar}>
        {t.nav.map((link) => (
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
                placeholder={t.searchPlaceholder}
                aria-label={t.searchAria}
              />
            </div>
            <button
              type="submit"
              className={`nb-btn ${styles.searchButton}`}
              disabled={loading}
            >
              {loading ? t.analyzing : t.submit}
            </button>
          </form>
          {isDemo && (
            <div className={styles.demoBanner}>{t.demoBanner}</div>
          )}
        </div>

        <div className={styles.trackHead}>
          <div>
            <h1 className={styles.headline}>
              {data.resolved_artist} — {data.resolved_title}
            </h1>
            <div className={styles.trackSub}>
              {t.lastAnalysis} {formatDateTime(data.created_at, t.months)} ·{" "}
              {t.sourceCount} {data.sources.length}
            </div>
          </div>
          <span className={styles.pill}>
            {t.overallStatus} {getOverallLabel(data.score, t.overallLabels)}
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
            <div className={styles.trackName}>{t.scoreCardLabel}</div>
          </div>

          <div className={`${styles.hard} ${styles.subscores}`}>
            {orderedSubscores.map(([key, value], index) => (
              <div key={key} className={styles.subscoreRow}>
                <div className={styles.subscoreLbl}>
                  {t.subscoreLabels[key] ?? key}
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

        <span className={styles.sectionTag}>{t.findingsTag}</span>
        <div className={styles.findings}>
          {data.findings.map((finding, index) => (
            <div key={index} className={`${styles.hard} ${styles.finding}`}>
              <span
                className={`${styles.findingTag} ${SEVERITY_TAG_CLASS[finding.severity]}`}
              >
                {t.severityLabels[finding.severity]}
              </span>
              <div className={styles.findingText}>{finding.message}</div>
              {finding.action && (
                <div className={styles.findingTodo}>
                  <b>{t.todoLabel}</b> {finding.action}
                </div>
              )}
            </div>
          ))}
        </div>

        <span className={styles.sectionTag}>{t.sourceTableTag}</span>
        <table className={`${styles.hard} ${styles.table}`}>
          <thead>
            <tr>
              <th>{t.th.source}</th>
              <th>{t.th.found}</th>
              <th>{t.th.isrc}</th>
              <th>{t.th.releaseDate}</th>
              <th>{t.th.popularity}</th>
            </tr>
          </thead>
          <tbody>
            {data.sources.map((source) => (
              <tr key={source.source}>
                <td>{source.source}</td>
                <td>
                  {source.found ? (
                    <span className={styles.badgeFound}>{t.yes}</span>
                  ) : (
                    <span className={styles.badgeMissing}>{t.no}</span>
                  )}
                </td>
                <td>{source.isrc ?? "—"}</td>
                <td>{formatDate(source.release_date, t.months)}</td>
                <td>{formatPopularity(source.popularity)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}
