"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getPublicKarne, type PublicReport } from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

const T = {
  tr: {
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
    } as Record<string, string>,
    months: [
      "Oca", "Şub", "Mar", "Nis", "May", "Haz",
      "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
    ],
    loading: "Karne yükleniyor…",
    notFoundTitle: "Karne bulunamadı",
    notFoundText: "Bu link geçersiz olabilir ya da karne artık paylaşılmıyor.",
    backHome: "Ana Sayfaya Dön",
    sharedAt: "Paylaşım tarihi:",
    pill: "Paylaşılan Karne",
    trackName: "SEO KARNESİ",
    sectionTag: "Bulgu Sayıları",
    noFindings: "Bulgu kaydı yok.",
    lockTitle: "Detaylı Bulgular Kilitli",
    lockText:
      "Bu şarkı için tam bulgu listesi ve aksiyon önerileri yalnızca hesap sahiplerine açık.",
    lockCta: "Detaylı bulgular ve aksiyon önerileri için ücretsiz hesap aç",
  },
  en: {
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
    } as Record<string, string>,
    months: [
      "Jan", "Feb", "Mar", "Apr", "May", "Jun",
      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ],
    loading: "Loading report…",
    notFoundTitle: "Report not found",
    notFoundText: "This link may be invalid, or the report is no longer shared.",
    backHome: "Back to Home",
    sharedAt: "Shared on:",
    pill: "Shared Report",
    trackName: "SEO REPORT",
    sectionTag: "Finding Counts",
    noFindings: "No findings recorded.",
    lockTitle: "Detailed Findings Locked",
    lockText:
      "The full finding list and action recommendations for this track are only available to account holders.",
    lockCta: "Create a free account for detailed findings and action tips",
  },
} as const;

const SUBSCORE_ORDER = ["metadata", "presence", "consistency", "keywords"];
const SEVERITY_ORDER = ["critical", "warn", "info", "ok"];

function formatDateTime(iso: string, months: readonly string[]): string {
  const dateMatch = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  const timeMatch = iso.match(/T(\d{2}):(\d{2})/);
  if (!dateMatch) return iso;
  const [, y, m, d] = dateMatch;
  const month = months[parseInt(m, 10) - 1] ?? m;
  const datePart = `${parseInt(d, 10)} ${month} ${y}`;
  return timeMatch ? `${datePart}, ${timeMatch[1]}:${timeMatch[2]}` : datePart;
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

function severityBadgeClass(severity: string): string {
  if (severity === "critical") return styles.badgeCritical;
  if (severity === "warn") return styles.badgeWarn;
  if (severity === "info") return styles.badgeInfo;
  return styles.badgeOk;
}

function subscoreBarClass(index: number): string {
  if (index === 0) return styles.barFillGreen;
  if (index === 3) return styles.barFillBlue;
  return "";
}

export default function PublicKarnePage() {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [report, setReport] = useState<PublicReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    (async () => {
      const result = await getPublicKarne(token);
      setReport(result);
      setLoading(false);
    })();
  }, [token]);

  const orderedSubscores = report
    ? getOrderedSubscoreEntries(report.subscores)
    : [];
  const orderedFindings = report
    ? SEVERITY_ORDER.filter((key) => key in report.finding_counts).map(
        (key) => [key, report.finding_counts[key]] as [string, number]
      )
    : [];

  return (
    <div className={styles.wrap}>
      <div className={styles.topbar}>
        <Link href="/" className={styles.logo}>MuzikSEO</Link>
        <LangToggle />
      </div>

      <main className={styles.main}>
        {loading && <div className={styles.loading}>{t.loading}</div>}

        {!loading && !report && (
          <div className={`nb-card ${styles.notFound}`}>
            <div className={styles.notFoundTitle}>{t.notFoundTitle}</div>
            <p className={styles.notFoundText}>{t.notFoundText}</p>
            <Link href="/" className="nb-btn">{t.backHome}</Link>
          </div>
        )}

        {!loading && report && (
          <>
            <div className={styles.trackHead}>
              <div>
                <h1 className={styles.headline}>
                  {report.artist} — {report.title}
                </h1>
                <div className={styles.trackSub}>
                  {t.sharedAt} {formatDateTime(report.created_at, t.months)}
                </div>
              </div>
              <span className={styles.pill}>{t.pill}</span>
            </div>

            <div className={styles.topGrid}>
              <div className={`nb-card ${styles.scoreCard}`}>
                <div
                  className={styles.scoreRing}
                  style={{
                    background: `conic-gradient(var(--blue) 0 ${report.score}%, #eee ${report.score}% 100%)`,
                  }}
                >
                  <div className={styles.num}>{report.score}</div>
                  <div className={styles.lbl}>/ 100</div>
                </div>
                <div className={styles.trackName}>{t.trackName}</div>
              </div>

              <div className={`nb-card ${styles.subscores}`}>
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

            <span className={styles.sectionTag}>{t.sectionTag}</span>
            <div className={styles.findingBadges}>
              {orderedFindings.length === 0 && (
                <span className={styles.noFindings}>{t.noFindings}</span>
              )}
              {orderedFindings.map(([severity, count]) => (
                <span
                  key={severity}
                  className={`${styles.badge} ${severityBadgeClass(severity)}`}
                >
                  {t.severityLabels[severity] ?? severity}: {count}
                </span>
              ))}
            </div>

            {report.locked && (
              <div className={styles.lockedSection}>
                <div className={styles.lockedBlur} aria-hidden="true">
                  <div className={styles.fakeLine} style={{ width: "92%" }} />
                  <div className={styles.fakeLine} style={{ width: "78%" }} />
                  <div className={styles.fakeLine} style={{ width: "85%" }} />
                  <div className={styles.fakeLine} style={{ width: "60%" }} />
                  <div className={styles.fakeLine} style={{ width: "70%" }} />
                </div>
                <div className={styles.lockedOverlay}>
                  <div className={styles.lockIcon}>🔒</div>
                  <div className={styles.lockTitle}>{t.lockTitle}</div>
                  <p className={styles.lockText}>{t.lockText}</p>
                  <Link href="/giris" className="nb-btn nb-btn--purple">
                    {t.lockCta}
                  </Link>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
