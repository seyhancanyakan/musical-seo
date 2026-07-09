"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  getAttributionReport,
  type AttributionBreakdownItem,
  type AttributionReport,
} from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";

/** Backend'in sabit kanal degerleri: "radyo" | "playlist" | "organik". */
const CHANNEL_COLOR: Record<string, string> = {
  radyo: "var(--red)",
  playlist: "var(--blue)",
  organik: "var(--green)",
};

const CHANNEL_LABELS: Record<string, { tr: string; en: string }> = {
  radyo: { tr: "📻 Radyo", en: "📻 Radio" },
  playlist: { tr: "🎧 Playlist", en: "🎧 Playlist" },
  organik: { tr: "🌱 Organik", en: "🌱 Organic" },
};

function channelLabel(channel: string, locale: "tr" | "en"): string {
  const known = CHANNEL_LABELS[channel];
  return known ? pick(known, locale) : channel || "—";
}

const DEMO_REPORT: AttributionReport = {
  report_token: "ATTR-3C7D",
  track_query: "Mira - Gece Yarısı",
  period_start: "2026-05-01",
  period_end: "2026-07-01",
  total_score_delta: 17,
  breakdown: [
    { channel: "radyo", events: 6, attributed_delta: 12.4, roi_per_credit: 2.1 },
    { channel: "playlist", events: 4, attributed_delta: 3.1, roi_per_credit: 0.8 },
    { channel: "organik", events: 0, attributed_delta: 1.5, roi_per_credit: 0 },
  ],
  recommendation:
    "En yüksek etkiyi radyo yayını yaratıyor (+12.4 puan); bu kanala yatırımı artırmanı öneririz.",
};

const T = {
  tr: {
    loading: "Rapor yükleniyor…",
    kpiDelta: "Toplam Δ skor",
    kpiEvents: "Tanıtım olayı",
    kpiRoi: "En iyi ROI ·",
    channelsLabel: "Kanal Bazlı Atıf (Δ skor)",
    recoTag: "Öneri",
    creditWord: "kredi",
    noBreakdown: "Henüz kanal verisi yok — daha fazla snapshot/yerleşim biriktikçe rapor isabetli olur.",
  },
  en: {
    loading: "Loading report…",
    kpiDelta: "Total Δ score",
    kpiEvents: "Promo events",
    kpiRoi: "Best ROI ·",
    channelsLabel: "Attribution by Channel (Δ score)",
    recoTag: "Recommendation",
    creditWord: "credit",
    noBreakdown: "No channel data yet — the report gets sharper as more snapshots/placements accumulate.",
  },
};

export default function AttributionReportPage() {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [report, setReport] = useState<AttributionReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    (async () => {
      const result = await getAttributionReport(token);
      setReport(result);
      setLoading(false);
    })();
  }, [token]);

  const data = report ?? { ...DEMO_REPORT, report_token: token || DEMO_REPORT.report_token };
  const breakdown: AttributionBreakdownItem[] = data.breakdown ?? [];
  const totalDelta = data.total_score_delta ?? 0;
  const totalEvents = breakdown.reduce((sum, item) => sum + (item.events ?? 0), 0);
  // breakdown backend'de attributed_delta'ya gore azalan sirali gelir -> ilk
  // eleman "en iyi kanal"; yine de savunmaci bul (bos/sirasiz olabilir).
  const bestChannel = breakdown.reduce<AttributionBreakdownItem | null>((best, item) => {
    if (!best) return item;
    return (item.attributed_delta ?? 0) > (best.attributed_delta ?? 0) ? item : best;
  }, null);
  const maxDelta = Math.max(...breakdown.map((c) => Math.abs(c.attributed_delta ?? 0)), 1);

  return (
    <div className={styles.page}>

      <main className={styles.body}>
        {loading ? (
          <div className={styles.loading}>{t.loading}</div>
        ) : (
          <>
            <div className={styles.head}>
              <div>
                <span className="nb-pill nb-pill--purple">{data.report_token ?? token}</span>
                <h1 className={`nb-h ${styles.trackName}`}>{data.track_query || "—"}</h1>
                <div className={styles.trackSub}>
                  {data.period?.start ?? data.period_start ?? "—"} →{" "}
                  {data.period?.end ?? data.period_end ?? "—"}
                </div>
              </div>
              <div className={styles.kpiRow}>
                <div className={`nb-card ${styles.kpi}`}>
                  <div className={styles.kpiVal} style={{ color: "var(--green)" }}>
                    {totalDelta >= 0 ? "+" : ""}
                    {totalDelta}
                  </div>
                  <div className={styles.kpiLabel}>{t.kpiDelta}</div>
                </div>
                <div className={`nb-card ${styles.kpi}`}>
                  <div className={styles.kpiVal}>{totalEvents}</div>
                  <div className={styles.kpiLabel}>{t.kpiEvents}</div>
                </div>
                <div className={`nb-card ${styles.kpi}`}>
                  <div className={styles.kpiVal} style={{ color: "var(--purple)" }}>
                    {(bestChannel?.roi_per_credit ?? 0).toFixed(1)}x
                  </div>
                  <div className={styles.kpiLabel}>
                    {t.kpiRoi} {bestChannel ? channelLabel(bestChannel.channel, locale) : "—"}
                  </div>
                </div>
              </div>
            </div>

            <div className={styles.grid2}>
              <div className={`nb-card ${styles.channelsCard}`}>
                <label className={styles.lbl}>{t.channelsLabel}</label>
                {breakdown.length === 0 && <p>{t.noBreakdown}</p>}
                {breakdown.map((channel, index) => (
                  <div key={`${channel.channel}-${index}`} className={styles.roibar}>
                    <span className={styles.roibarChannel}>
                      {channelLabel(channel.channel, locale)}
                    </span>
                    <div className={styles.roibarTrack}>
                      <span
                        className={styles.roibarFill}
                        style={{
                          width: `${(Math.abs(channel.attributed_delta ?? 0) / maxDelta) * 100}%`,
                          background: CHANNEL_COLOR[channel.channel] ?? "var(--blue)",
                        }}
                      />
                    </div>
                    <span className={styles.roibarAmt}>
                      {(channel.attributed_delta ?? 0) >= 0 ? "+" : ""}
                      {(channel.attributed_delta ?? 0).toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>
              <div className={`nb-card ${styles.recoCard}`}>
                <span className="nb-pill nb-pill--purple">{t.recoTag}</span>
                <p className={styles.recoText}>{data.recommendation || "—"}</p>
                <div className={styles.recoChips}>
                  {breakdown.map((channel, index) => (
                    <span key={`${channel.channel}-chip-${index}`} className="nb-chip">
                      {channelLabel(channel.channel, locale)}{" "}
                      {channel.roi_per_credit != null ? `${channel.roi_per_credit}/${t.creditWord}` : "—"}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
