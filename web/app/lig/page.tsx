"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getLeaderboard, type LeaderboardEntry } from "@/lib/api";
import styles from "./page.module.css";

const MONTHS_TR = [
  "Oca", "Şub", "Mar", "Nis", "May", "Haz",
  "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
];

function formatDate(iso: string): string {
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return iso;
  const [, y, m, d] = match;
  const month = MONTHS_TR[parseInt(m, 10) - 1] ?? m;
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
        <Link href="/" className={styles.logo}>MuzikSEO</Link>
        <Link href="/karne" className={`nb-btn ${styles.shareBtn}`}>
          Karneni Paylaş
        </Link>
      </div>

      <main className={styles.main}>
        <h1 className={`nb-h ${styles.pageTitle}`}>Karne Ligi</h1>

        <div className={`nb-card ${styles.infoBanner}`}>
          <span className={styles.infoIcon}>ℹ️</span>
          <div>
            <div className={styles.infoTitle}>Bu lig tamamen opt-in&apos;dir</div>
            <div className={styles.infoText}>
              Karneni burada göstermek senin seçimin — gizlilik varsayılan
              olarak <b>kapalı</b>. Sadece paylaşmayı seçtiğin karneler
              listelenir. İstediğin an ligden çıkabilirsin.
            </div>
          </div>
        </div>

        {loading && <div className={styles.loading}>Lig yükleniyor…</div>}

        {isEmpty && (
          <div className={`nb-card ${styles.emptyCard}`}>
            <div className={styles.emptyTitle}>Lig boş</div>
            <p className={styles.emptyText}>
              Karneni paylaş, ligde yerini al.
            </p>
            <Link href="/karne" className="nb-btn nb-btn--purple">
              Karneni Çıkar
            </Link>
          </div>
        )}

        {!loading && entries && entries.length > 0 && (
          <div className={styles.tableWrap}>
            <div className={`${styles.tableHead}`}>
              <span className={styles.colRank}>Sıra</span>
              <span className={styles.colTrack}>Sanatçı — Şarkı</span>
              <span className={styles.colScore}>Skor</span>
              <span className={styles.colDate}>Tarih</span>
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
                  <span className={styles.dateCell}>{formatDate(entry.created_at)}</span>
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
