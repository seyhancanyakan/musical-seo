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

const DEMO_TRACK_LABEL = "Duman — Senden Daha Güzel · Son 60 gün";
const DEMO_BEFORE = 34;
const DEMO_AFTER = 41;

function formatDay(dateStr: string, index: number, total: number): string {
  if (!dateStr) return `Gün ${index + 1}`;
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return `Gün ${index + 1}`;
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

/** Gercek gecmis satirlarindan SVG polyline noktalari uretir (viewBox 0 0 1200 340). */
function buildLivePoints(rows: HistoryRow[]): {
  points: string;
  values: number[];
  minVal: number;
  maxVal: number;
} {
  const values = rows.map((r) => r.spotify_popularity ?? r.score);
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

  return { points, values, minVal, maxVal };
}

export default function KanitPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [history, setHistory] = useState<HistoryRow[] | null>(null);
  const [activeQuery, setActiveQuery] = useState("");

  const isDemo = history === null || history.length === 0;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    setLoading(true);
    setSubmitted(true);
    setActiveQuery(trimmed);
    const result = await getHistory(trimmed);
    setHistory(result && result.length > 0 ? result : null);
    setLoading(false);
  }

  const live = !isDemo && history ? buildLivePoints(history) : null;
  const liveDiff =
    live && history
      ? Math.round(
          (history[history.length - 1].spotify_popularity ??
            history[history.length - 1].score) -
            (history[0].spotify_popularity ?? history[0].score)
        )
      : 0;

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
          {submitted && activeQuery ? (
            <>
              {activeQuery} · {isDemo ? "demo veri" : "canlı veri"}
            </>
          ) : (
            DEMO_TRACK_LABEL
          )}
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

        {isDemo && submitted && (
          <div className={styles.banner}>
            Henüz zaman serisi yok — demo veri gösteriliyor.
          </div>
        )}
        {isDemo && !submitted && (
          <div className={styles.banner}>
            Bir şarkı ara veya aşağıdaki demo veriyi incele.
          </div>
        )}

        <div className={`${styles.chartCard} nb-card`}>
          <div className={styles.chartTitle}>Popülerlik Trendi (60 Gün)</div>
          <div className={styles.chartWrap}>
            {isDemo ? (
              <svg viewBox="0 0 1200 340" preserveAspectRatio="none">
                <rect
                  x="680"
                  y="0"
                  width="520"
                  height="300"
                  fill="#D6E4FF"
                  opacity="0.6"
                />
                <line
                  x1="40"
                  y1="300"
                  x2="1180"
                  y2="300"
                  stroke="#000"
                  strokeWidth="3"
                />
                <line
                  x1="40"
                  y1="0"
                  x2="40"
                  y2="300"
                  stroke="#000"
                  strokeWidth="3"
                />
                <text x="10" y="260" fontSize="14" fontWeight="700" fill="#555">
                  {DEMO_BEFORE}
                </text>
                <text x="10" y="70" fontSize="14" fontWeight="700" fill="#555">
                  {DEMO_AFTER}
                </text>
                <polyline
                  points="40,255 120,258 200,250 280,254 360,246 440,250 520,244 600,248 680,240
                  740,215 800,190 860,170 920,150 980,135 1040,120 1100,105 1160,95"
                  fill="none"
                  stroke="#000"
                  strokeWidth="5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <line
                  x1="680"
                  y1="0"
                  x2="680"
                  y2="300"
                  stroke="#7C3AED"
                  strokeWidth="3"
                  strokeDasharray="8,6"
                />
                <circle cx="680" cy="240" r="9" fill="#7C3AED" stroke="#000" strokeWidth="3" />
                <g transform="translate(680,0)">
                  <rect x="-95" y="-4" width="190" height="34" fill="#7C3AED" stroke="#000" strokeWidth="3" />
                  <text x="0" y="19" fontSize="14" fontWeight="900" fill="#fff" textAnchor="middle" fontFamily="Arial">
                    PITCH GÖNDERİLDİ
                  </text>
                </g>
                <g transform="translate(1160,95)">
                  <rect x="-70" y="-46" width="150" height="34" fill="#3DDC84" stroke="#000" strokeWidth="3" />
                  <text x="5" y="-23" fontSize="15" fontWeight="900" fill="#000" textAnchor="middle" fontFamily="Arial">
                    +7 POPULARITY
                  </text>
                </g>
                <circle cx="40" cy="255" r="7" fill="#000" />
                <circle cx="1160" cy="95" r="7" fill="#000" />
                <text x="30" y="320" fontSize="13" fontWeight="700" fill="#555">
                  Gün 1
                </text>
                <text x="1140" y="320" fontSize="13" fontWeight="700" fill="#555">
                  Gün 60
                </text>
              </svg>
            ) : (
              live &&
              history && (
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
                    {formatDay(history[0]?.created_at, 0, history.length)}
                  </text>
                  <text x="1100" y="320" fontSize="13" fontWeight="700" fill="#555">
                    {formatDay(
                      history[history.length - 1]?.created_at,
                      history.length - 1,
                      history.length
                    )}
                  </text>
                </svg>
              )
            )}
          </div>
        </div>

        <div className={styles.tiles}>
          <div className={`${styles.tile} nb-card`}>
            <div className={styles.tval}>
              {isDemo
                ? DEMO_BEFORE
                : Math.round(
                    history?.[0]?.spotify_popularity ?? history?.[0]?.score ?? 0
                  )}
            </div>
            <div className={styles.tlbl}>Öncesi</div>
          </div>
          <div className={`${styles.tile} ${styles.tileAlt} nb-card`}>
            <div className={styles.tval}>
              {isDemo
                ? DEMO_AFTER
                : Math.round(
                    history?.[history.length - 1]?.spotify_popularity ??
                      history?.[history.length - 1]?.score ??
                      0
                  )}
            </div>
            <div className={styles.tlbl}>Sonrası</div>
          </div>
          <div className={`${styles.tile} nb-card`}>
            <div className={styles.tval}>{isDemo ? 3 : history?.length ?? 0}</div>
            <div className={styles.tlbl}>
              {isDemo ? "Doğrulanmış Yerleşim" : "Veri Noktası"}
            </div>
          </div>
        </div>

        <span className={styles.sectionTag}>Doğrulanmış Yerleşimler</span>
        <div className={styles.badges}>
          {isDemo ? (
            <>
              <div className={`${styles.badgeRow} nb-card`}>
                <div className={styles.stampMark}>✓</div>
                <div className={styles.badgeText}>
                  <div className={styles.badgeMain}>
                    &quot;Türk&quot; listesine eklendi — Deezer&apos;dan doğrulandı, 4 Tem 2026
                  </div>
                  <div className={styles.badgeSub}>
                    Kaynak: Deezer Public API · Yöntem: bağımsız çapraz kontrol
                  </div>
                </div>
              </div>
              <div className={`${styles.badgeRow} nb-card`}>
                <div className={styles.stampMark}>✓</div>
                <div className={styles.badgeText}>
                  <div className={styles.badgeMain}>
                    &quot;BRK - TR&quot; listesine eklendi — doğrulandı
                  </div>
                  <div className={styles.badgeSub}>
                    Kaynak: Deezer Public API · Yöntem: bağımsız çapraz kontrol
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className={`${styles.badgeRow} nb-card`}>
              <div className={styles.badgeText}>
                <div className={styles.badgeMain}>
                  Bu arama için doğrulanmış yerleşim kaydı yok.
                </div>
                <div className={styles.badgeSub}>
                  Yerleşim doğrulaması küratör kutusu üzerinden işlenir.
                </div>
              </div>
            </div>
          )}
        </div>

        <div className={styles.caption}>
          Her yerleşim Deezer API&apos;sinden bağımsız doğrulanır — söz değil, kanıt.
        </div>
      </div>
    </>
  );
}
