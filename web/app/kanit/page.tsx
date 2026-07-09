"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { getHistory } from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type HistoryRow = {
  created_at: string;
  score: number;
  spotify_popularity: number | null;
};

const T = {
  tr: {
    nav: [
      { href: "/karne", label: "Karne" },
      { href: "/playlistler", label: "Playlistler" },
      { href: "/kanit", label: "Kanıt" },
      { href: "/curator/inbox", label: "Küratör Kutusu" },
    ],
    dayFallback: (index: number) => `Gün ${index + 1}`,
    dateLocale: "tr-TR",
    pageTitle: "Kanıt Paneli",
    subLiveData: "canlı veri",
    subNoData: "veri yok",
    subIdle: "Şarkını ara — popülerlik trendini canlı göster",
    searchPlaceholder: "Sanatçı — Şarkı adı",
    searchAria: "Şarkı ara",
    loading: "Yükleniyor…",
    submit: "Kanıtı Göster",
    noDataBannerSuffix:
      "için henüz zaman serisi yok. Kanıt grafiği, gecelik denetimler biriktikçe (birden çok gün) dolar. En az bir denetim kaydı gerekir.",
    chartTitle: "Popülerlik Trendi",
    chartEmptySubmitted: "Bu şarkı için veri noktası yok.",
    chartEmptyIdle: "Şarkını ara → popülerlik trendi burada çıksın.",
    before: "Öncesi",
    after: "Sonrası",
    dataPoints: "Veri Noktası",
    verifiedTag: "Doğrulanmış Yerleşimler",
    badgeMainHasData:
      "Yerleşim doğrulaması küratör kutusu üzerinden işlenir; onaylananlar burada listelenir.",
    badgeMainNoData: "Bu arama için doğrulanmış yerleşim kaydı yok.",
    badgeSub: "Kaynak: Deezer Public API · Yöntem: bağımsız çapraz kontrol",
    caption:
      "Her yerleşim Deezer API'sinden bağımsız doğrulanır — söz değil, kanıt.",
  },
  en: {
    nav: [
      { href: "/karne", label: "Scorecard" },
      { href: "/playlistler", label: "Playlists" },
      { href: "/kanit", label: "Proof" },
      { href: "/curator/inbox", label: "Curator Inbox" },
    ],
    dayFallback: (index: number) => `Day ${index + 1}`,
    dateLocale: "en-US",
    pageTitle: "Proof Panel",
    subLiveData: "live data",
    subNoData: "no data",
    subIdle: "Search your song — see the popularity trend live",
    searchPlaceholder: "Artist — Song title",
    searchAria: "Search song",
    loading: "Loading…",
    submit: "Show Proof",
    noDataBannerSuffix:
      "has no time series yet. The proof chart fills in as nightly audits accumulate (multiple days). At least one audit record is required.",
    chartTitle: "Popularity Trend",
    chartEmptySubmitted: "No data points for this song.",
    chartEmptyIdle: "Search your song → the popularity trend shows up here.",
    before: "Before",
    after: "After",
    dataPoints: "Data Points",
    verifiedTag: "Verified Placements",
    badgeMainHasData:
      "Placement verification runs through the curator inbox; approved placements are listed here.",
    badgeMainNoData: "No verified placement record for this search yet.",
    badgeSub: "Source: Deezer Public API · Method: independent cross-check",
    caption:
      "Every placement is independently verified via the Deezer API — proof, not promises.",
  },
};

function metric(row: HistoryRow): number {
  return row.spotify_popularity ?? row.score;
}

function formatDay(
  dateStr: string,
  index: number,
  dayFallback: (index: number) => string,
  dateLocale: string
): string {
  if (!dateStr) return dayFallback(index);
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dayFallback(index);
  return d.toLocaleDateString(dateLocale, { day: "2-digit", month: "short" });
}

/** Gercek gecmis satirlarindan SVG polyline noktalari uretir (viewBox 0 0 1200 340). */
function buildLivePoints(rows: HistoryRow[]): {
  points: string;
  minVal: number;
  maxVal: number;
} {
  const values = rows.map(metric);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const spread = maxVal - minVal || 1;

  const xLeft = 40;
  const xRight = 1180;
  const yTop = 20;
  const yBottom = 300;

  const points = values
    .map((v, i) => {
      const x =
        values.length === 1
          ? xLeft
          : xLeft + (i / (values.length - 1)) * (xRight - xLeft);
      const y = yBottom - ((v - minVal) / spread) * (yBottom - yTop);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return { points, minVal, maxVal };
}

export default function KanitPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [history, setHistory] = useState<HistoryRow[] | null>(null);
  const [activeQuery, setActiveQuery] = useState("");

  const hasData = !!(history && history.length > 0);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    setLoading(true);
    setSubmitted(true);
    setActiveQuery(trimmed);
    const result = await getHistory(trimmed);
    setHistory(result && result.length > 0 ? result : []);
    setLoading(false);
  }

  const live = hasData && history ? buildLivePoints(history) : null;
  const first = hasData && history ? metric(history[0]) : null;
  const last = hasData && history ? metric(history[history.length - 1]) : null;
  const liveDiff = first !== null && last !== null ? Math.round(last - first) : 0;

  return (
    <>
      <nav className={styles.topbar}>
        <div className={styles.topbarInner}>
          <Link href="/" className={styles.logo}>Sozy Echo</Link>
          <div className={styles.navLinks}>
            {t.nav.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={
                  link.href === "/kanit"
                    ? `${styles.navLink} ${styles.navLinkActive}`
                    : styles.navLink
                }
              >
                {link.label}
              </Link>
            ))}
          </div>
          <LangToggle />
        </div>
      </nav>

      <div className={styles.wrap}>
        <h1 className={`${styles.pageTitle} nb-h`}>{t.pageTitle}</h1>
        <div className={styles.trackSub}>
          {submitted && activeQuery
            ? `${activeQuery} · ${hasData ? t.subLiveData : t.subNoData}`
            : t.subIdle}
        </div>

        <form className={styles.searchRow} onSubmit={handleSubmit}>
          <input
            className={`${styles.searchInput} nb-input`}
            type="text"
            placeholder={t.searchPlaceholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label={t.searchAria}
          />
          <button
            type="submit"
            className={`${styles.searchBtn} nb-btn`}
            disabled={loading}
          >
            {loading ? t.loading : t.submit}
          </button>
        </form>

        {submitted && !loading && !hasData && (
          <div className={styles.banner}>
            <strong>{activeQuery}</strong> {t.noDataBannerSuffix}
          </div>
        )}

        <div className={`${styles.chartCard} nb-card`}>
          <div className={styles.chartTitle}>{t.chartTitle}</div>
          <div className={styles.chartWrap}>
            {live && history ? (
              <svg viewBox="0 0 1200 340" preserveAspectRatio="none">
                <line x1="40" y1="300" x2="1180" y2="300" stroke="#000" strokeWidth="3" />
                <line x1="40" y1="0" x2="40" y2="300" stroke="#000" strokeWidth="3" />
                <text x="10" y="260" fontSize="14" fontWeight="700" fill="#555">
                  {Math.round(live.minVal)}
                </text>
                <text x="10" y="70" fontSize="14" fontWeight="700" fill="#555">
                  {Math.round(live.maxVal)}
                </text>
                <polyline
                  points={live.points}
                  fill="none"
                  stroke="#000"
                  strokeWidth="5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {liveDiff !== 0 && (
                  <g transform="translate(1160,40)">
                    <rect
                      x="-70"
                      y="-46"
                      width="150"
                      height="34"
                      fill={liveDiff > 0 ? "#3DDC84" : "#FF4D4D"}
                      stroke="#000"
                      strokeWidth="3"
                    />
                    <text
                      x="5"
                      y="-23"
                      fontSize="15"
                      fontWeight="900"
                      fill="#000"
                      textAnchor="middle"
                      fontFamily="Arial"
                    >
                      {liveDiff > 0 ? `+${liveDiff}` : liveDiff} POPULARITY
                    </text>
                  </g>
                )}
                <text x="30" y="320" fontSize="13" fontWeight="700" fill="#555">
                  {formatDay(history[0]?.created_at, 0, t.dayFallback, t.dateLocale)}
                </text>
                <text x="1100" y="320" fontSize="13" fontWeight="700" fill="#555">
                  {formatDay(
                    history[history.length - 1]?.created_at,
                    history.length - 1,
                    t.dayFallback,
                    t.dateLocale
                  )}
                </text>
              </svg>
            ) : (
              <div className={styles.chartEmpty}>
                {submitted ? t.chartEmptySubmitted : t.chartEmptyIdle}
              </div>
            )}
          </div>
        </div>

        <div className={styles.tiles}>
          <div className={`${styles.tile} nb-card`}>
            <div className={styles.tval}>{first !== null ? Math.round(first) : "—"}</div>
            <div className={styles.tlbl}>{t.before}</div>
          </div>
          <div className={`${styles.tile} ${styles.tileAlt} nb-card`}>
            <div className={styles.tval}>{last !== null ? Math.round(last) : "—"}</div>
            <div className={styles.tlbl}>{t.after}</div>
          </div>
          <div className={`${styles.tile} nb-card`}>
            <div className={styles.tval}>{hasData ? history!.length : "—"}</div>
            <div className={styles.tlbl}>{t.dataPoints}</div>
          </div>
        </div>

        <span className={styles.sectionTag}>{t.verifiedTag}</span>
        <div className={styles.badges}>
          <div className={`${styles.badgeRow} nb-card`}>
            <div className={styles.badgeText}>
              <div className={styles.badgeMain}>
                {hasData ? t.badgeMainHasData : t.badgeMainNoData}
              </div>
              <div className={styles.badgeSub}>{t.badgeSub}</div>
            </div>
          </div>
        </div>

        <div className={styles.caption}>{t.caption}</div>
      </div>
    </>
  );
}
