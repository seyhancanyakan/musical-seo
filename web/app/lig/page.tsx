"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getLeaderboard, type LeaderboardEntry } from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

const T = {
  tr: {
    shareCta: "Karneni Paylaş",
    title: "Karne Ligi",
    infoTitle: "Bu lig tamamen opt-in'dir",
    infoTextBefore:
      "Karneni burada göstermek senin seçimin — gizlilik varsayılan olarak ",
    infoTextBold: "kapalı",
    infoTextAfter:
      ". Sadece paylaşmayı seçtiğin karneler listelenir. İstediğin an ligden çıkabilirsin.",
    loading: "Lig yükleniyor…",
    emptyTitle: "Lig boş",
    emptyText: "Karneni paylaş, ligde yerini al.",
    emptyCta: "Karneni Çıkar",
    colRank: "Sıra",
    colTrack: "Sanatçı — Şarkı",
    colScore: "Skor",
    colDate: "Tarih",
    months: ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"],
  },
  en: {
    shareCta: "Share Your Report Card",
    title: "Report Card League",
    infoTitle: "This league is fully opt-in",
    infoTextBefore:
      "Showing your report card here is your choice — privacy defaults to ",
    infoTextBold: "off",
    infoTextAfter:
      ". Only report cards you choose to share are listed. You can leave the league anytime.",
    loading: "Loading league…",
    emptyTitle: "League is empty",
    emptyText: "Share your report card to claim your spot.",
    emptyCta: "Get Your Report Card",
    colRank: "Rank",
    colTrack: "Artist — Song",
    colScore: "Score",
    colDate: "Date",
    months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  },
} as const;

function formatDate(iso: string, months: readonly string[]): string {
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return iso;
  const [, y, m, d] = match;
  const month = months[parseInt(m, 10) - 1] ?? m;
  return `${parseInt(d, 10)} ${month} ${y}`;
}

function rankChipClass(rank: number): string {
  if (rank === 1) return styles.rankGold;
  if (rank === 2) return styles.rankSilver;
  if (rank === 3) return styles.rankBronze;
  return "";
}

function scoreBarClass(score: number): string {
  if (score >= 90) return styles.barFillGreen;
  if (score >= 70) return styles.barFillBlue;
  if (score >= 50) return styles.barFillPurple;
  return styles.barFillRed;
}

export default function LigPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [entries, setEntries] = useState<LeaderboardEntry[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const result = await getLeaderboard(20);
      setEntries(result ?? []);
      setLoading(false);
    })();
  }, []);

  const isEmpty = !loading && (!entries || entries.length === 0);

  return (
    <div className={styles.wrap}>
      <div className={styles.topbar}>
        <Link href="/" className={styles.logo}>Songdeck</Link>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/karne" className={`nb-btn ${styles.shareBtn}`}>
            {t.shareCta}
          </Link>
          <LangToggle />
        </div>
      </div>

      <main className={styles.main}>
        <h1 className={`nb-h ${styles.pageTitle}`}>{t.title}</h1>

        <div className={`nb-card ${styles.infoBanner}`}>
          <span className={styles.infoIcon}>ℹ️</span>
          <div>
            <div className={styles.infoTitle}>{t.infoTitle}</div>
            <div className={styles.infoText}>
              {t.infoTextBefore}
              <b>{t.infoTextBold}</b>
              {t.infoTextAfter}
            </div>
          </div>
        </div>

        {loading && <div className={styles.loading}>{t.loading}</div>}

        {isEmpty && (
          <div className={`nb-card ${styles.emptyCard}`}>
            <div className={styles.emptyTitle}>{t.emptyTitle}</div>
            <p className={styles.emptyText}>{t.emptyText}</p>
            <Link href="/karne" className="nb-btn nb-btn--purple">
              {t.emptyCta}
            </Link>
          </div>
        )}

        {!loading && entries && entries.length > 0 && (
          <div className={styles.tableWrap}>
            <div className={`${styles.tableHead}`}>
              <span className={styles.colRank}>{t.colRank}</span>
              <span className={styles.colTrack}>{t.colTrack}</span>
              <span className={styles.colScore}>{t.colScore}</span>
              <span className={styles.colDate}>{t.colDate}</span>
            </div>
            {entries.map((entry, index) => {
              const rank = index + 1;
              return (
                <Link
                  key={entry.token}
                  href={`/k/${entry.token}`}
                  className={`${styles.row} ${rank <= 3 ? styles.rowTop : ""}`}
                >
                  <span className={`${styles.rankChip} ${rankChipClass(rank)}`}>
                    {rank}
                  </span>
                  <span className={styles.trackCell}>
                    <span className={styles.artist}>{entry.artist}</span>
                    <span className={styles.dash}> — </span>
                    <span className={styles.title}>{entry.title}</span>
                  </span>
                  <span className={styles.scoreCell}>
                    <span className={styles.barTrack}>
                      <span
                        className={`${styles.barFill} ${scoreBarClass(entry.score)}`}
                        style={{ width: `${entry.score}%` }}
                      />
                    </span>
                    <span className={styles.scoreNum}>{entry.score}</span>
                  </span>
                  <span className={styles.dateCell}>{formatDate(entry.created_at, t.months)}</span>
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
