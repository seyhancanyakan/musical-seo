"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getReleaseReport, type ReleaseTimingReport } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import SiteHeader from "@/components/SiteHeader";
import styles from "./page.module.css";

const DEMO_REPORT: ReleaseTimingReport = {
  report_token: "TIME-51B9",
  track_query: "Deniz Ada - Kıyı",
  target_date: "2026-07-20",
  readiness: {
    score: 38,
    findings: [
      { severity: "critical", category: "metadata", message: "ISRC kodu eksik", action: "Dağıtıcı panelinden ekle" },
      { severity: "warn", category: "video", message: "Resmi 'Official Audio' videosu yok", action: "YouTube'a yükle" },
    ],
    fixable_issues: ["ISRC kodunu ekle (dağıtıcı panelinden)", "YouTube'da resmi 'Official Audio' videosu aç"],
  },
  competition: {
    competition: "medium",
    score: 0.5,
    alternatives: ["Kıyı (Deniz Ada)", "Kıyı Akustik"],
  },
  competitors: {
    competitor_count: 2,
    competitors: [
      { title: "Yaz Rüzgarı", artist: "Efe Kaan", date: "2026-07-18" },
      { title: "Mavi", artist: "Selin Aksu", date: "2026-07-21" },
    ],
    risk: "high",
  },
  day: {
    recommended_day: "Friday",
    reason: "Hedef tarih Pazartesi - global standart Cuma yayın için en yakın Cuma 2026-07-24 (4 gün fark)",
    score: 0.4,
    nearest_friday: "2026-07-24",
  },
  overall_verdict: "ertele",
  recommended_date: "2026-08-04",
  action_plan: [
    "ISRC kodunu ekle (dağıtıcı panelinden)",
    "YouTube'da resmi 'Official Audio' videosu aç",
    "Anahtar kelime rekabeti yüksek - alternatif başlıklandırma/marka araması büyütmeyi düşün",
    "2 rakip yayın hedef haftada - tarihi 2026-08-04 olarak kaydırmayı düşün",
  ],
  projected_score: 64,
};

const VERDICT_MAP: Record<
  string,
  { tr: { title: string }; en: { title: string }; color: string; emoji: string; bg: string; border: string }
> = {
  hazir: {
    tr: { title: "Yayınla — tarih uygun" },
    en: { title: "Release — date is good" },
    color: "#0a8f3c",
    emoji: "✅",
    bg: "#f0fff5",
    border: "var(--green)",
  },
  hazirlan: {
    tr: { title: "Önce hazırlan" },
    en: { title: "Prepare first" },
    color: "#b06f00",
    emoji: "⚠️",
    bg: "#fff7ea",
    border: "var(--amber, #ffb020)",
  },
  ertele: {
    tr: { title: "Ertele" },
    en: { title: "Delay" },
    color: "#b06f00",
    emoji: "⏳",
    bg: "#fff7ea",
    border: "var(--amber, #ffb020)",
  },
};

const VERDICT_DEFAULT = {
  tr: { title: "Sonuç belirsiz" },
  en: { title: "Verdict unclear" },
  color: "#888",
  emoji: "❓",
  bg: "#f4f4f0",
  border: "#ccc",
};

const LEVEL_LABELS: Record<string, { tr: string; en: string }> = {
  low: { tr: "Düşük", en: "Low" },
  medium: { tr: "Orta", en: "Medium" },
  high: { tr: "Yüksek", en: "High" },
};

function levelLabel(level: string | undefined | null, locale: "tr" | "en"): string {
  if (!level) return "—";
  const known = LEVEL_LABELS[level];
  return known ? pick(known, locale) : level;
}

function levelPillClass(level: string | undefined | null): string {
  if (level === "high") return "nb-pill--red";
  if (level === "low") return "nb-pill--green";
  return "nb-pill--blue"; // medium / bilinmeyen -> notr
}

const T = {
  tr: {
    loading: "Rapor yükleniyor…",
    recommended: "Önerilen",
    projection: "Aksiyon Planı — skor projeksiyonu",
    cardReadiness: "1 · Hazırlık",
    cardCompetition: "2 · Keyword Rekabeti",
    cardCompetitors: "3 · Rakip Release",
    cardDay: "4 · Gün",
    noFindings: "Belirgin eksiklik bulunamadı.",
    fixableCount: (n: number) => `${n} düzeltilebilir madde`,
    noAlternatives: "Alternatif anahtar kelime verisi yok.",
    noCompetitors: "Hedef hafta için rakip yayın verisi yok.",
    monthShort: (iso: string) => formatShortDate(iso, "tr"),
  },
  en: {
    loading: "Loading report…",
    recommended: "Recommended",
    projection: "Action Plan — score projection",
    cardReadiness: "1 · Readiness",
    cardCompetition: "2 · Keyword Competition",
    cardCompetitors: "3 · Competitor Releases",
    cardDay: "4 · Day",
    noFindings: "No notable issues found.",
    fixableCount: (n: number) => `${n} fixable item(s)`,
    noAlternatives: "No alternative keyword data.",
    noCompetitors: "No competitor release data for the target week.",
    monthShort: (iso: string) => formatShortDate(iso, "en"),
  },
};

const MONTHS_TR = ["OCA", "ŞUB", "MAR", "NİS", "MAY", "HAZ", "TEM", "AĞU", "EYL", "EKİ", "KAS", "ARA"];
const MONTHS_EN = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

function formatShortDate(iso: string | undefined | null, locale: "tr" | "en"): string {
  if (!iso) return "—";
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return iso;
  const [, , m, d] = match;
  const months = locale === "tr" ? MONTHS_TR : MONTHS_EN;
  return `${d} ${months[parseInt(m, 10) - 1] ?? m}`;
}

export default function ReleaseReportPage() {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [report, setReport] = useState<ReleaseTimingReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    (async () => {
      const result = await getReleaseReport(token);
      setReport(result);
      setLoading(false);
    })();
  }, [token]);

  const data = report ?? { ...DEMO_REPORT, report_token: token || DEMO_REPORT.report_token };
  const verdictInfo = VERDICT_MAP[data.overall_verdict ?? ""] ?? VERDICT_DEFAULT;
  const verdictText = pick(verdictInfo, locale);
  const readinessScore = Math.max(0, Math.min(100, Math.round(data.readiness?.score ?? 0)));
  const findings = data.readiness?.findings ?? [];
  const fixableIssues = data.readiness?.fixable_issues ?? [];
  const competitors = data.competitors?.competitors ?? [];
  const actionPlan = data.action_plan ?? [];

  return (
    <div className={styles.page}>
      <SiteHeader />

      <main className={styles.body}>
        {loading ? (
          <div className={styles.loading}>{t.loading}</div>
        ) : (
          <>
            <div
              className={styles.verdict}
              style={{ background: verdictInfo.bg, borderColor: verdictInfo.border }}
            >
              <span className={styles.verdictEmoji}>{verdictInfo.emoji}</span>
              <div>
                <div className={styles.verdictTitle} style={{ color: verdictInfo.color }}>
                  {verdictText.title}
                </div>
                <p className={styles.verdictText}>
                  {data.track_query || "—"} · {t.recommended}: {t.monthShort(data.recommended_date)}
                </p>
              </div>
              <div className={styles.verdictDate}>
                <div className={`nb-h ${styles.verdictDateLabel}`}>{t.recommended}</div>
                <div className={`nb-h ${styles.verdictDateVal}`}>
                  {t.monthShort(data.recommended_date)}
                </div>
              </div>
            </div>

            <div className={styles.signalGrid}>
              <div className={`nb-card ${styles.signal}`}>
                <h4>{t.cardReadiness}</h4>
                <div
                  className={styles.signalVal}
                  style={{
                    fontFamily: '"Arial Black", Arial, sans-serif',
                    color: readinessScore <= 40 ? "var(--red)" : undefined,
                  }}
                >
                  {readinessScore}
                  <small className={styles.signalValSuffix}>/100</small>
                </div>
                <p>{findings[0]?.message ?? t.noFindings}</p>
                <div className={styles.meter}>
                  <span
                    className={styles.meterFill}
                    style={{ width: `${readinessScore}%`, background: "var(--red)" }}
                  />
                </div>
                {fixableIssues.length > 0 && (
                  <div className={styles.evidence}>{t.fixableCount(fixableIssues.length)}</div>
                )}
              </div>

              <div className={`nb-card ${styles.signal}`}>
                <h4>{t.cardCompetition}</h4>
                <span
                  className={`nb-pill ${levelPillClass(data.competition?.competition)}`}
                  style={{ alignSelf: "flex-start" }}
                >
                  {levelLabel(data.competition?.competition, locale)}
                </span>
                <p>
                  {data.competition?.alternatives?.length
                    ? data.competition.alternatives.join(", ")
                    : t.noAlternatives}
                </p>
              </div>

              <div className={`nb-card ${styles.signal}`}>
                <h4>{t.cardCompetitors}</h4>
                <div className={styles.signalVal}>{data.competitors?.competitor_count ?? 0}</div>
                <span
                  className={`nb-pill ${levelPillClass(data.competitors?.risk)}`}
                  style={{ alignSelf: "flex-start" }}
                >
                  {levelLabel(data.competitors?.risk, locale)}
                </span>
                <p>
                  {competitors.length > 0
                    ? competitors
                        .slice(0, 2)
                        .map((c) => `${c?.title ?? "—"}${c?.artist ? ` (${c.artist})` : ""}`)
                        .join(" · ")
                    : t.noCompetitors}
                </p>
              </div>

              <div className={`nb-card ${styles.signal}`}>
                <h4>{t.cardDay}</h4>
                <span
                  className={`nb-pill ${(data.day?.score ?? 0) >= 0.85 ? "nb-pill--green" : "nb-pill--blue"}`}
                  style={{ alignSelf: "flex-start" }}
                >
                  {data.day?.recommended_day ?? "—"}
                </span>
                <p>{data.day?.reason ?? "—"}</p>
                {data.day?.nearest_friday && (
                  <div className={styles.evidence}>
                    {t.recommended}: {data.day.nearest_friday}
                  </div>
                )}
              </div>
            </div>

            <label className={styles.lbl}>
              {t.projection} {readinessScore} → {data.projected_score ?? 0}
            </label>
            <ol className={styles.steps}>
              {actionPlan.map((step, index) => (
                <li key={index} className={styles.step}>
                  <span className={styles.stepNum}>{index + 1}</span>
                  <span className={styles.stepTxt}>{step}</span>
                </li>
              ))}
            </ol>
          </>
        )}
      </main>
    </div>
  );
}
