"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getFraudReport, type FraudReport, type FraudSignalDetail } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";

/** Backend'in sabit 5 sinyal anahtari — sirali gosterim + bilinmeyen anahtar
 *  icin guvenli varsayilan (asla index'siz patlamaz). */
const SIGNAL_ORDER = [
  "follower_anomaly",
  "track_churn",
  "geo_cluster",
  "audio_label_mismatch",
  "track_seo_poverty",
] as const;

const SIGNAL_LABELS: Record<string, { tr: string; en: string }> = {
  follower_anomaly: { tr: "Takipçi Anomalisi", en: "Follower Anomaly" },
  track_churn: { tr: "Parça Değişim Oranı", en: "Track Churn" },
  geo_cluster: { tr: "Coğrafi Kümelenme", en: "Geo Clustering" },
  audio_label_mismatch: { tr: "Ses–Etiket Uyumsuzluğu", en: "Audio–Label Mismatch" },
  track_seo_poverty: { tr: "Parça SEO Yoksulluğu", en: "Track SEO Poverty" },
};

const DEMO_REPORT: FraudReport = {
  report_token: "FRAUD-8F2A",
  playlist_url: "https://open.spotify.com/playlist/37i9dQZF1DX...",
  playlist_title: "Chill Vibes 2026 🌙",
  total_risk_score: 87,
  verdict: "cok_riskli",
  signals: {
    follower_anomaly: {
      score: 0.94,
      detail: "En büyük ardışık takipçi sıçraması: %94",
      evidence: { max_jump_ratio: 0.94, snapshot_count: 5 },
    },
    track_churn: {
      score: 0.61,
      detail: "Ortalama parça değişim oranı: %61",
      evidence: { avg_churn_rate: 0.61, samples: 6 },
    },
    geo_cluster: {
      score: 0.88,
      detail: "En yoğun ülke: TR (%81)",
      evidence: { top_country: "TR", top_share: 0.81 },
    },
    audio_label_mismatch: {
      score: 0.55,
      detail: "Playlist 'sakin' iddia ediyor ama ortalama enerji 0.68",
      evidence: { avg_energy: 0.68, claims_calm: true },
    },
    track_seo_poverty: {
      score: 0.79,
      detail: "31/40 parça düşük SEO skoruna sahip (<40)",
      evidence: { poor_count: 31, track_count: 40 },
    },
  },
  recommendation:
    "Güçlü sahtecilik izleri: bu playliste yerleşim önerilmiyor. Riskli sinyaller: follower_anomaly, geo_cluster, track_seo_poverty.",
};

const VERDICT_MAP: Record<
  string,
  { tr: { pill: string; title: string }; en: { pill: string; title: string }; color: string; emoji: string }
> = {
  guvenli: {
    tr: { pill: "◆ Temiz — Güvenli", title: "Güvenli görünüyor" },
    en: { pill: "◆ Clean — Safe", title: "Looks safe" },
    color: "var(--green)",
    emoji: "✅",
  },
  riskli: {
    tr: { pill: "◆ Şüpheli — Riskli", title: "Dikkatli ol" },
    en: { pill: "◆ Suspicious — Risky", title: "Be careful" },
    color: "#ffb020",
    emoji: "⚠️",
  },
  cok_riskli: {
    tr: { pill: "◆ Yüksek Risk", title: "Para ödeme" },
    en: { pill: "◆ High Risk", title: "Don't pay" },
    color: "var(--red)",
    emoji: "🚫",
  },
  sahte: {
    tr: { pill: "◆ SAHTE", title: "Para ödeme" },
    en: { pill: "◆ FAKE", title: "Don't pay" },
    color: "var(--red)",
    emoji: "🚫",
  },
  veri_yetersiz: {
    tr: { pill: "◆ Veri Yetersiz", title: "Güvenilir analiz için veri gerekli" },
    en: { pill: "◆ Insufficient Data", title: "Needs data for a reliable verdict" },
    color: "var(--blue)",
    emoji: "ℹ️",
  },
};

const VERDICT_DEFAULT = {
  tr: { pill: "◆ Bilinmiyor", title: "Sonuç belirsiz" },
  en: { pill: "◆ Unknown", title: "Verdict unclear" },
  color: "#888",
  emoji: "❓",
};

const T = {
  tr: {
    loading: "Rapor yükleniyor…",
    share: "↗ Raporu paylaş",
    pdf: "⬇ Kanıt PDF",
    insure: "🛡 Sigorta ekle — 5 kredi",
  },
  en: {
    loading: "Loading report…",
    share: "↗ Share report",
    pdf: "⬇ Evidence PDF",
    insure: "🛡 Add insurance — 5 credits",
  },
};

/** evidence objesini kisa "k: v · k2: v2" satirina cevirir — bilinmeyen/bos
 *  yapida asla patlamaz. */
function formatEvidence(evidence: Record<string, unknown> | undefined): string {
  if (!evidence || typeof evidence !== "object") return "";
  return Object.entries(evidence)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(",") : String(v ?? "—")}`)
    .join(" · ");
}

function signalColor(score: number): string {
  if (score >= 0.6) return "var(--red)";
  if (score >= 0.35) return "#ffb020";
  return "var(--green)";
}

export default function FraudReportPage() {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [report, setReport] = useState<FraudReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    (async () => {
      const result = await getFraudReport(token);
      setReport(result);
      setLoading(false);
    })();
  }, [token]);

  const data = report ?? { ...DEMO_REPORT, report_token: token || DEMO_REPORT.report_token };
  const verdictInfo = VERDICT_MAP[data.verdict ?? ""] ?? VERDICT_DEFAULT;
  const verdictText = pick(verdictInfo, locale);
  const riskScore = Math.max(0, Math.min(100, Math.round(data.total_risk_score ?? 0)));

  const signalEntries = SIGNAL_ORDER.filter((key) => data.signals?.[key]).map((key) => [
    key,
    data.signals[key],
  ]) as [string, FraudSignalDetail][];
  // Bilinmeyen/ek sinyal anahtarlari varsa da kaybolmasin — sona ekle.
  const extraEntries = Object.entries(data.signals ?? {}).filter(
    ([key]) => !SIGNAL_ORDER.includes(key as (typeof SIGNAL_ORDER)[number])
  );
  const allSignals = [...signalEntries, ...extraEntries];

  return (
    <div className={styles.page}>

      <main className={styles.body}>
        {loading ? (
          <div className={styles.loading}>{t.loading}</div>
        ) : (
          <>
            <div className={styles.head}>
              <div
                className={styles.gauge}
                style={{
                  background: `conic-gradient(var(--red) 0 ${riskScore}%, #e6e6e0 ${riskScore}% 100%)`,
                }}
              >
                <div className={styles.gaugeInner}>
                  <div>
                    <div className={styles.gaugeScore} style={{ color: "var(--red)" }}>
                      {riskScore}
                    </div>
                    <div className={styles.gaugeOf}>/100 risk</div>
                  </div>
                </div>
              </div>
              <div className={styles.headMeta}>
                <span className="nb-pill nb-pill--red">{verdictText.pill}</span>
                <h1 className={`nb-h ${styles.trackName}`}>
                  {data.playlist_title || "—"}
                </h1>
                <div className={styles.trackSub}>{data.playlist_url || "—"}</div>
                <div className={styles.verdict}>
                  <span className={styles.verdictEmoji}>{verdictInfo.emoji}</span>
                  <div>
                    <div className={styles.verdictTitle} style={{ color: verdictInfo.color }}>
                      {verdictText.title}
                    </div>
                    <p className={styles.verdictText}>{data.recommendation || "—"}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className={styles.signalGrid}>
              {allSignals.map(([key, signal]) => {
                const label = SIGNAL_LABELS[key]
                  ? pick(SIGNAL_LABELS[key], locale)
                  : key.replace(/_/g, " ");
                const score = signal?.score ?? 0;
                const color = signalColor(score);
                const evidenceLine = formatEvidence(signal?.evidence);
                return (
                  <div key={key} className={`nb-card ${styles.signal}`}>
                    <div className={styles.signalTop}>
                      <h4>{label}</h4>
                      <span className={styles.signalVal} style={{ color }}>
                        {score.toFixed(2)}
                      </span>
                    </div>
                    <div className={styles.meter}>
                      <span
                        className={styles.meterFill}
                        style={{ width: `${Math.max(0, Math.min(1, score)) * 100}%`, background: color }}
                      />
                    </div>
                    <p>{signal?.detail || "—"}</p>
                    {evidenceLine && <div className={styles.evidence}>{evidenceLine}</div>}
                  </div>
                );
              })}
            </div>

            <div className={styles.actionsRow}>
              <button type="button" className="nb-btn nb-btn--outline">
                {t.share}
              </button>
              <button type="button" className="nb-btn nb-btn--outline">
                {t.pdf}
              </button>
              <button type="button" className="nb-btn nb-btn--purple">
                {t.insure}
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
