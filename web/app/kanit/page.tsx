"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { getHistory } from "@/lib/api";
import styles from "./page.module.css";

type HistoryRow = {
  created_at: string;
  score: number;
  spotify_popularity: number | null;
};

const NAV_LINKS: { href: string; label: string }[] = [
  { href: "/karne", label: "Karne" },
  { href: "/playlistler", label: "Playlistler" },
  { href: "/kanit", label: "Kanıt" },
  { href: "/curator/inbox", label: "Küratör Kutusu" },
];

function metric(row: HistoryRow): number {
  return row.spotify_popularity ?? row.score;
}

function formatDay(dateStr: string, index: number): string {
  if (!dateStr) return `Gün ${index + 1}`;
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return `Gün ${index + 1}`;
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
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
          <div className={styles.logo}>MuzikSEO</div>
          <div className={styles.navLinks}>
            {NAV_LINKS.map((link) => (
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
        </div>
      </nav>

      <div className={styles.wrap}>
        <h1 className={`${styles.pageTitle} nb-h`}>Kanıt Paneli</h1>
        <div className={styles.trackSub}>
          {submitted && activeQuery
            ? `${activeQuery} · ${hasData ? "canlı veri" : "veri yok"}`
            : "Şarkını ara — popülerlik trendini canlı göster"}
        </div>

        <form className={styles.searchRow} onSubmit={handleSubmit}>
          <input
            className={`${styles.searchInput} nb-input`}
            type="text"
            placeholder="Sanatçı — Şarkı adı"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Şarkı ara"
          />
          <button
            type="submit"
            className={`${styles.searchBtn} nb-btn`}
            disabled={loading}
          >
            {loading ? "Yükleniyor…" : "Kanıtı Göster"}
          </button>
        </form>

        {submitted && !loading && !hasData && (
          <div className={styles.banner}>
            <strong>{activeQuery}</strong> için henüz zaman serisi yok. Kanıt grafiği,
            gecelik denetimler biriktikçe (birden çok gün) dolar. En az bir denetim
            kaydı gerekir.
          </div>
        )}

        <div className={`${styles.chartCard} nb-card`}>
          <div className={styles.chartTitle}>Popülerlik Trendi</div>
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
                  {formatDay(history[0]?.created_at, 0)}
                </text>
                <text x="1100" y="320" fontSize="13" fontWeight="700" fill="#555">
                  {formatDay(history[history.length - 1]?.created_at, history.length - 1)}
                </text>
              </svg>
            ) : (
              <div className={styles.chartEmpty}>
                {submitted
                  ? "Bu şarkı için veri noktası yok."
                  : "Şarkını ara → popülerlik trendi burada çıksın."}
              </div>
            )}
          </div>
        </div>

        <div className={styles.tiles}>
          <div className={`${styles.tile} nb-card`}>
            <div className={styles.tval}>{first !== null ? Math.round(first) : "—"}</div>
            <div className={styles.tlbl}>Öncesi</div>
          </div>
          <div className={`${styles.tile} ${styles.tileAlt} nb-card`}>
            <div className={styles.tval}>{last !== null ? Math.round(last) : "—"}</div>
            <div className={styles.tlbl}>Sonrası</div>
          </div>
          <div className={`${styles.tile} nb-card`}>
            <div className={styles.tval}>{hasData ? history!.length : "—"}</div>
            <div className={styles.tlbl}>Veri Noktası</div>
          </div>
        </div>

        <span className={styles.sectionTag}>Doğrulanmış Yerleşimler</span>
        <div className={styles.badges}>
          <div className={`${styles.badgeRow} nb-card`}>
            <div className={styles.badgeText}>
              <div className={styles.badgeMain}>
                {hasData
                  ? "Yerleşim doğrulaması küratör kutusu üzerinden işlenir; onaylananlar burada listelenir."
                  : "Bu arama için doğrulanmış yerleşim kaydı yok."}
              </div>
              <div className={styles.badgeSub}>
                Kaynak: Deezer Public API · Yöntem: bağımsız çapraz kontrol
              </div>
            </div>
          </div>
        </div>

        <div className={styles.caption}>
          Her yerleşim Deezer API&apos;sinden bağımsız doğrulanır — söz değil, kanıt.
        </div>
      </div>
    </>
  );
}
