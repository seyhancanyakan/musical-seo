"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getCuratorProfile,
  type CuratorProfile,
  type CuratorType,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

const T = {
  tr: {
    typeLabels: {
      playlist: "🎧 Playlist Küratörü",
      radyo: "📻 Radyo",
      medya: "📰 Medya / Blog",
      label: "💿 Label",
      menajer: "🧑‍💼 Menajer",
      booker: "🎪 Booker",
      dj: "🎛️ DJ",
      mentor: "🎓 Mentor",
      sync: "🎬 Sync Uzmanı",
    } as Record<CuratorType, string>,
    loading: "Profil yükleniyor…",
    notFoundTitle: "Küratör bulunamadı",
    notFoundText: "Bu küratör profili artık mevcut değil ya da onaylı değil.",
    backHome: "Ana Sayfaya Dön",
    sponsored: "⭐ Sponsorlu",
    verified: "Sahiplik doğrulandı ✓",
    fans: "Fan",
    tracks: "Parça",
    qualityScore: "Kalite Skoru",
    verifiedTitle: "Doğrulanmış Yerleşim",
    verifiedCaption:
      "API kanıtlı — beyan değil. Her yerleşim Deezer/Spotify public API üzerinden bağımsız doğrulanır.",
    sectionTag: "Performans",
    responseRate: "Yanıt Oranı",
    successRate: "Kabul Oranı",
    sendTrack: "Bu Küratöre Şarkı Gönder",
  },
  en: {
    typeLabels: {
      playlist: "🎧 Playlist Curator",
      radyo: "📻 Radio",
      medya: "📰 Media / Blog",
      label: "💿 Label",
      menajer: "🧑‍💼 Manager",
      booker: "🎪 Booker",
      dj: "🎛️ DJ",
      mentor: "🎓 Mentor",
      sync: "🎬 Sync Specialist",
    } as Record<CuratorType, string>,
    loading: "Loading profile…",
    notFoundTitle: "Curator not found",
    notFoundText: "This curator profile no longer exists or isn't approved.",
    backHome: "Back to Home",
    sponsored: "⭐ Sponsored",
    verified: "Ownership verified ✓",
    fans: "Fans",
    tracks: "Tracks",
    qualityScore: "Quality Score",
    verifiedTitle: "Verified Placements",
    verifiedCaption:
      "API-proven — not self-reported. Every placement is independently verified via the Deezer/Spotify public API.",
    sectionTag: "Performance",
    responseRate: "Response Rate",
    successRate: "Acceptance Rate",
    sendTrack: "Send a Track to This Curator",
  },
} as const;

function statBarClass(index: number): string {
  if (index === 0) return styles.barFillBlue;
  return styles.barFillGreen;
}

export default function CuratorProfilePage() {
  const params = useParams<{ id: string }>();
  const idParam = params?.id ?? "";
  const curatorId = Number(idParam);
  const { locale } = useLocale();
  const t = pick(T, locale);

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
        { label: t.responseRate, value: profile.stats.response_rate },
        { label: t.successRate, value: profile.stats.success_rate },
      ]
    : [];

  return (
    <div className={styles.wrap}>
      <div className={styles.topbar}>
        <Link href="/" className={styles.logo}>Songdeck</Link>
        <LangToggle />
      </div>

      <main className={styles.main}>
        {loading && <div className={styles.loading}>{t.loading}</div>}

        {!loading && !profile && (
          <div className={`nb-card ${styles.notFound}`}>
            <div className={styles.notFoundTitle}>{t.notFoundTitle}</div>
            <p className={styles.notFoundText}>{t.notFoundText}</p>
            <Link href="/" className="nb-btn">{t.backHome}</Link>
          </div>
        )}

        {!loading && profile && (
          <>
            <div className={styles.head}>
              <div>
                <div className={styles.badgeRow}>
                  <span className={styles.typePill}>
                    {t.typeLabels[profile.curator_type] ?? profile.curator_type}
                  </span>
                  {profile.sponsored && (
                    <span className={styles.sponsoredPill}>{t.sponsored}</span>
                  )}
                  {profile.ownership_verified === 1 && (
                    <span className={styles.verifiedPill}>{t.verified}</span>
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
                  {profile.fans.toLocaleString(locale === "tr" ? "tr-TR" : "en-US")}
                </div>
                <div className={styles.metaLbl}>{t.fans}</div>
              </div>
              <div className={`nb-card ${styles.metaTile}`}>
                <div className={styles.metaVal}>{profile.track_count}</div>
                <div className={styles.metaLbl}>{t.tracks}</div>
              </div>
              <div className={`nb-card ${styles.metaTile}`}>
                <div className={styles.metaVal}>{profile.quality_score}</div>
                <div className={styles.metaLbl}>{t.qualityScore}</div>
              </div>
            </div>

            <div className={`${styles.verifiedCard}`}>
              <div className={styles.verifiedNum}>
                {profile.verified_placements}
              </div>
              <div className={styles.verifiedText}>
                <div className={styles.verifiedTitle}>{t.verifiedTitle}</div>
                <div className={styles.verifiedCaption}>{t.verifiedCaption}</div>
              </div>
            </div>

            {statRows.length > 0 && (
              <>
                <span className={styles.sectionTag}>{t.sectionTag}</span>
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
                {t.sendTrack}
              </Link>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
