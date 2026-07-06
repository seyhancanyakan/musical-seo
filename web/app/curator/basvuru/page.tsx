"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { applyCurator, type Curator } from "@/lib/api";
import { LangToggle, pick, useLocale } from "@/lib/locale";
import styles from "./page.module.css";

const T = {
  tr: {
    heroTitle: "LİSTENLE PARA KAZAN",
    heroSub: "Deezer playlist'ini bağla, otomatik doğrulama sonucunu 30 saniyede gör.",
    namePlaceholder: "Adın Soyadın",
    emailPlaceholder: "E-posta adresin",
    urlPlaceholder: "Deezer playlist URL'ini yapıştır",
    verifying: "Doğrulanıyor…",
    verifyBtn: "Doğrula",
    note: "Not: Listeni botlara karşı otomatik doğruluyoruz.",
    demoBanner: "API'ye ulaşılamadı — demo sonuç gösteriliyor.",
    stampApprovedLine1: "Otomatik",
    stampApprovedLine2: "Onaylandı",
    stampPending: "İncelemede",
    resultMeta: (tracks: number, diversity: string, quality: string) =>
      `${tracks} parça · Çeşitlilik ${diversity} · Kalite ${quality} / 100`,
    checklistItems: [
      "Playlist herkese açık ve aktif olarak güncelleniyor",
      "Takipçi/fan oranı bot davranışı sınırının altında",
      "Sanatçı çeşitliliği minimum eşiği karşılıyor",
    ],
    footnote:
      "Doğrulama sonrası listenle eşleşen pitch'ler gelen kutuna düşmeye başlar. Her kabul ettiğin yerleşim için kazanç panelinden ödeme takip edebilirsin.",
  },
  en: {
    heroTitle: "EARN WITH YOUR PLAYLIST",
    heroSub: "Link your Deezer playlist and see the automatic verification result in 30 seconds.",
    namePlaceholder: "Your name",
    emailPlaceholder: "Your email address",
    urlPlaceholder: "Paste your Deezer playlist URL",
    verifying: "Verifying…",
    verifyBtn: "Verify",
    note: "Note: We automatically verify your playlist against bot behavior.",
    demoBanner: "Couldn't reach the API — showing a demo result.",
    stampApprovedLine1: "Automatically",
    stampApprovedLine2: "Approved",
    stampPending: "Under Review",
    resultMeta: (tracks: number, diversity: string, quality: string) =>
      `${tracks} tracks · Diversity ${diversity} · Quality ${quality} / 100`,
    checklistItems: [
      "Playlist is public and actively updated",
      "Follower/fan ratio is below the bot-behavior threshold",
      "Artist diversity meets the minimum threshold",
    ],
    footnote:
      "Once verified, pitches matching your playlist start landing in your inbox. Track payouts for every placement you accept from the earnings panel.",
  },
} as const;

/** Mockup'taki demo sonucu birebir yansitir (API'ye ulasilamadiginda gosterilir). */
const DEMO_RESULT: Curator = {
  id: 0,
  created_at: "2026-07-04T10:30:00+00:00",
  name: "Demo Küratör",
  email: "demo@curator.example",
  deezer_playlist_id: "7841203955",
  playlist_title: "Türk",
  playlist_url: "https://deezer.com/playlist/7841203955",
  fans: 0,
  track_count: 47,
  diversity: 0.28,
  quality_score: 25.6,
  status: "approved",
};

export default function CuratorBasvuruPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [playlistUrl, setPlaylistUrl] = useState(
    "https://deezer.com/playlist/7841203955"
  );
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Curator | null>(null);
  const [isDemo, setIsDemo] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);

    const response = await applyCurator({
      name,
      email,
      playlist_url: playlistUrl,
    });

    if (response) {
      setResult(response);
      setIsDemo(false);
    } else {
      setResult(DEMO_RESULT);
      setIsDemo(true);
    }

    setLoading(false);
  }

  const stampClass =
    result?.status === "approved"
      ? `${styles.stamp} ${styles.stampApproved}`
      : result?.status === "pending"
        ? `${styles.stamp} ${styles.stampPending}`
        : `${styles.stamp} ${styles.stampNeutral}`;

  return (
    <>
      <nav className={styles.topbar}>
        <div className={styles.topbarInner}>
          <Link href="/" className={styles.logo}>MuzikSEO</Link>
          <LangToggle />
        </div>
      </nav>

      <div className={styles.centerWrap}>
        <h1 className={styles.pageTitle}>{t.heroTitle}</h1>
        <p className={styles.sub}>{t.heroSub}</p>

        <form className={styles.form} onSubmit={handleSubmit}>
          <input
            className={styles.input}
            type="text"
            required
            placeholder={t.namePlaceholder}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <input
            className={styles.input}
            type="email"
            required
            placeholder={t.emailPlaceholder}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <div className={styles.urlRow}>
            <input
              className={styles.input}
              type="text"
              required
              placeholder={t.urlPlaceholder}
              value={playlistUrl}
              onChange={(event) => setPlaylistUrl(event.target.value)}
            />
            <button className={styles.btn} type="submit" disabled={loading}>
              {loading ? t.verifying : t.verifyBtn}
            </button>
          </div>
        </form>
        <div className={styles.note}>{t.note}</div>

        {isDemo && (
          <div className={styles.demoBanner}>{t.demoBanner}</div>
        )}

        {result && (
          <div className={styles.resultCard}>
            <div className={stampClass}>
              {result.status === "approved" ? (
                <>
                  {t.stampApprovedLine1}
                  <br />
                  {t.stampApprovedLine2}
                </>
              ) : result.status === "pending" ? (
                t.stampPending
              ) : (
                result.status
              )}
            </div>
            <div className={styles.resultTop}>
              <div>
                <div className={styles.resultName}>
                  &ldquo;{result.playlist_title}&rdquo;
                </div>
                <div className={styles.resultMeta}>
                  {t.resultMeta(
                    result.track_count,
                    result.diversity.toFixed(2),
                    result.quality_score.toFixed(1)
                  )}
                </div>
              </div>
            </div>
            <div className={styles.checklist}>
              {t.checklistItems.map((item, index) => (
                <div className={styles.checkItem} key={item}>
                  <div className={styles.checkBox}>{index + 1}</div> {item}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className={styles.footnote}>{t.footnote}</div>
      </div>
    </>
  );
}
