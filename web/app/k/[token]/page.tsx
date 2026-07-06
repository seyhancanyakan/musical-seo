"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getPublicKarne, type PublicReport } from "@/lib/api";
import styles from "./page.module.css";

const SUBSCORE_LABELS: Record<string, string> = {
  metadata: "Metadata",
  presence: "Varlık",
  consistency: "Tutarlılık",
  keywords: "Anahtar Kelime",
};

const SUBSCORE_ORDER = ["metadata", "presence", "consistency", "keywords"];

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Kritik",
  warn: "Uyarı",
  info: "Bilgi",
  ok: "OK",
};

const SEVERITY_ORDER = ["critical", "warn", "info", "ok"];

const MONTHS_TR = [
  "Oca", "Şub", "Mar", "Nis", "May", "Haz",
  "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
];

function formatDateTime(iso: string): string {
  const dateMatch = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  const timeMatch = iso.match(/T(\d{2}):(\d{2})/);
  if (!dateMatch) return iso;
  const [, y, m, d] = dateMatch;
  const month = MONTHS_TR[parseInt(m, 10) - 1] ?? m;
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
      </div>

      <main className={styles.main}>
        {loading && <div className={styles.loading}>Karne yükleniyor…</div>}

        {!loading && !report && (
          <div className={`nb-card ${styles.notFound}`}>
            <div className={styles.notFoundTitle}>Karne bulunamadı</div>
            <p className={styles.notFoundText}>
              Bu link geçersiz olabilir ya da karne artık paylaşılmıyor.
            </p>
            <Link href="/" className="nb-btn">Ana Sayfaya Dön</Link>
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
                  Paylaşım tarihi: {formatDateTime(report.created_at)}
                </div>
              </div>
              <span className={styles.pill}>Paylaşılan Karne</span>
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
                <div className={styles.trackName}>SEO KARNESİ</div>
              </div>

              <div className={`nb-card ${styles.subscores}`}>
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

            <span className={styles.sectionTag}>Bulgu Sayıları</span>
            <div className={styles.findingBadges}>
              {orderedFindings.length === 0 && (
                <span className={styles.noFindings}>Bulgu kaydı yok.</span>
              )}
              {orderedFindings.map(([severity, count]) => (
                <span
                  key={severity}
                  className={`${styles.badge} ${severityBadgeClass(severity)}`}
                >
                  {SEVERITY_LABELS[severity] ?? severity}: {count}
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
                  <div className={styles.lockTitle}>
                    Detaylı Bulgular Kilitli
                  </div>
                  <p className={styles.lockText}>
                    Bu şarkı için tam bulgu listesi ve aksiyon önerileri
                    yalnızca hesap sahiplerine açık.
                  </p>
                  <Link href="/giris" className="nb-btn nb-btn--purple">
                    Detaylı bulgular ve aksiyon önerileri için ücretsiz hesap aç
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
