"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getCuratorProfile,
  type CuratorProfile,
  type CuratorType,
} from "@/lib/api";
import styles from "./page.module.css";

const TYPE_LABELS: Record<CuratorType, string> = {
  playlist: "🎧 Playlist Küratörü",
  radyo: "📻 Radyo",
  medya: "📰 Medya / Blog",
  label: "💿 Label",
  menajer: "🧑‍💼 Menajer",
  booker: "🎪 Booker",
  dj: "🎛️ DJ",
  mentor: "🎓 Mentor",
  sync: "🎬 Sync Uzmanı",
};

function statBarClass(index: number): string {
  if (index === 0) return styles.barFillBlue;
  return styles.barFillGreen;
}

export default function CuratorProfilePage() {
  const params = useParams<{ id: string }>();
  const idParam = params?.id ?? "";
  const curatorId = Number(idParam);

  const [profile, setProfile] = useState<CuratorProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!idParam || Number.isNaN(curatorId)) {
      setLoading(false);
      return;
    }
    (async () => {
      const result = await getCuratorProfile(curatorId);
      setProfile(result);
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idParam]);

  const statRows: { label: string; value: number | null | undefined }[] = profile
    ? [
        { label: "Yanıt Oranı", value: profile.stats.response_rate },
        { label: "Kabul Oranı", value: profile.stats.success_rate },
      ]
    : [];

  return (
    <div className={styles.wrap}>
      <div className={styles.topbar}>
        <Link href="/" className={styles.logo}>MuzikSEO</Link>
      </div>

      <main className={styles.main}>
        {loading && <div className={styles.loading}>Profil yükleniyor…</div>}

        {!loading && !profile && (
          <div className={`nb-card ${styles.notFound}`}>
            <div className={styles.notFoundTitle}>Küratör bulunamadı</div>
            <p className={styles.notFoundText}>
              Bu küratör profili artık mevcut değil ya da onaylı değil.
            </p>
            <Link href="/" className="nb-btn">Ana Sayfaya Dön</Link>
          </div>
        )}

        {!loading && profile && (
          <>
            <div className={styles.head}>
              <div>
                <div className={styles.badgeRow}>
                  <span className={styles.typePill}>
                    {TYPE_LABELS[profile.curator_type] ?? profile.curator_type}
                  </span>
                  {profile.sponsored && (
                    <span className={styles.sponsoredPill}>⭐ Sponsorlu</span>
                  )}
                  {profile.ownership_verified === 1 && (
                    <span className={styles.verifiedPill}>
                      Sahiplik doğrulandı ✓
                    </span>
                  )}
                </div>
                <h1 className={styles.name}>{profile.name}</h1>
                <a
                  href={profile.playlist_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.playlistLink}
                >
                  🎧 {profile.playlist_title} ↗
                </a>
              </div>
            </div>

            <div className={styles.metaRow}>
              <div className={`nb-card ${styles.metaTile}`}>
                <div className={styles.metaVal}>
                  {profile.fans.toLocaleString("tr-TR")}
                </div>
                <div className={styles.metaLbl}>Fan</div>
              </div>
              <div className={`nb-card ${styles.metaTile}`}>
                <div className={styles.metaVal}>{profile.track_count}</div>
                <div className={styles.metaLbl}>Parça</div>
              </div>
              <div className={`nb-card ${styles.metaTile}`}>
                <div className={styles.metaVal}>{profile.quality_score}</div>
                <div className={styles.metaLbl}>Kalite Skoru</div>
              </div>
            </div>

            <div className={`${styles.verifiedCard}`}>
              <div className={styles.verifiedNum}>
                {profile.verified_placements}
              </div>
              <div className={styles.verifiedText}>
                <div className={styles.verifiedTitle}>Doğrulanmış Yerleşim</div>
                <div className={styles.verifiedCaption}>
                  API kanıtlı — beyan değil. Her yerleşim Deezer/Spotify
                  public API üzerinden bağımsız doğrulanır.
                </div>
              </div>
            </div>

            {statRows.length > 0 && (
              <>
                <span className={styles.sectionTag}>Performans</span>
                <div className={`nb-card ${styles.statsCard}`}>
                  {statRows.map((row, index) => (
                    <div key={row.label} className={styles.statRow}>
                      <div className={styles.statLbl}>{row.label}</div>
                      <div className={styles.barTrack}>
                        <div
                          className={`${styles.barFill} ${statBarClass(index)}`}
                          style={{ width: `${row.value ?? 0}%` }}
                        />
                      </div>
                      <div className={styles.statVal}>
                        {row.value != null ? `%${row.value}` : "—"}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            <div className={styles.ctaRow}>
              <Link
                href={`/gonder?curator=${profile.id}`}
                className="nb-btn nb-btn--purple"
              >
                Bu Küratöre Şarkı Gönder
              </Link>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
