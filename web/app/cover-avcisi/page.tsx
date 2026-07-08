"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { enableWatchdog, startCoverHunt } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import SiteHeader from "@/components/SiteHeader";
import styles from "./page.module.css";

const DEMO_QUERY = "Selin Kaya — Yağmur Sonrası";
const DEMO_TOKEN = "HUNT-9K4E";

const T = {
  tr: {
    pill: "Cover / Derivative Avcısı",
    title: (
      <>
        Content ID kaçırıyor.
        <br />Cover'ları biz yakalarız.
      </>
    ),
    lede:
      "Content ID yalnız aynı kaydı bulur. Bu motor farklı kayıt–aynı melodi cover'larını audio profil + söz + başlık çapraz aramasıyla tespit eder, lisans teklifi ya da telif claim üretir.",
    songLabel: "Orijinal Şarkı",
    watchdogTitle: "Sürekli İzleme (Watchdog)",
    watchdogSub: "Her hafta yeni platform tarar · 5 kredi/ay",
    submit: "🎯 Avı Başlat — 2 kredi",
    working: "Başlatılıyor...",
    demoCta: "Geçmiş avlar",
    priceKicker: "3 katmanlı tespit",
    priceBig: "Audio · Söz · Başlık",
    priceList: [
      <>
        <b>BPM/tonalite/enerji</b> profil benzerliği
      </>,
      "Aynı söz — farklı kayıt taraması",
      <>
        Lisanslanırsa <b>%15 komisyon</b>
      </>,
    ],
    errorPrefix: "Başlatma başarısız:",
  },
  en: {
    pill: "Cover / Derivative Hunter",
    title: (
      <>
        Content ID misses it.
        <br />We catch the covers.
      </>
    ),
    lede:
      "Content ID only finds the same recording. This engine detects different-recording, same-melody covers via audio profile + lyric + title cross-search, and produces a license offer or copyright claim.",
    songLabel: "Original Song",
    watchdogTitle: "Continuous Monitoring (Watchdog)",
    watchdogSub: "Scans new platforms weekly · 5 credits/month",
    submit: "🎯 Start the Hunt — 2 credits",
    working: "Starting...",
    demoCta: "Past hunts",
    priceKicker: "3-layer detection",
    priceBig: "Audio · Lyrics · Title",
    priceList: [
      <>
        <b>BPM/key/energy</b> profile similarity
      </>,
      "Same lyrics — different recording scan",
      <>
        <b>15% commission</b> if licensed
      </>,
    ],
    errorPrefix: "Start failed:",
  },
};

export default function CoverAvcisiPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);
  const router = useRouter();

  const [query, setQuery] = useState(DEMO_QUERY);
  const [watchdog, setWatchdog] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError(null);
    try {
      const { data, error: apiError } = await startCoverHunt(trimmed);
      if (data?.report_token) {
        if (watchdog) await enableWatchdog(trimmed);
        router.push(`/cover-avcisi/rapor/${encodeURIComponent(data.report_token)}`);
        return;
      }
      setError(apiError ?? "—");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.page}>
      <SiteHeader />

      <main className={styles.body}>
        <span className="nb-pill nb-pill--green">{t.pill}</span>
        <h1 className={`nb-h ${styles.title}`}>{t.title}</h1>
        <p className={styles.lede}>{t.lede}</p>

        <div className={styles.heroInput}>
          <form className={`nb-card ${styles.formCard}`} onSubmit={handleSubmit}>
            <div>
              <label className={styles.lbl} htmlFor="cover-query">
                {t.songLabel}
              </label>
              <input
                id="cover-query"
                className="nb-input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
            <div className={styles.watchdogRow}>
              <span
                role="switch"
                aria-checked={watchdog}
                tabIndex={0}
                className={`${styles.toggleTrack} ${watchdog ? styles.toggleTrackOn : ""}`}
                onClick={() => setWatchdog((v) => !v)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setWatchdog((v) => !v);
                  }
                }}
              >
                <span
                  className={`${styles.toggleThumb} ${watchdog ? styles.toggleThumbOn : ""}`}
                />
              </span>
              <div>
                <b className={styles.watchdogTitle}>{t.watchdogTitle}</b>
                <div className={styles.watchdogSub}>{t.watchdogSub}</div>
              </div>
            </div>
            <div className={styles.actionsRow}>
              <button type="submit" className="nb-btn nb-btn--green" disabled={loading}>
                {loading ? t.working : t.submit}
              </button>
              <Link href={`/cover-avcisi/rapor/${DEMO_TOKEN}`} className="nb-btn nb-btn--outline">
                {t.demoCta}
              </Link>
            </div>
            {error && <div className={styles.errorBanner}>{t.errorPrefix} {error}</div>}
          </form>

          <div className={styles.priceCard}>
            <div className={styles.priceKicker}>{t.priceKicker}</div>
            <div className={styles.priceBig}>{t.priceBig}</div>
            <ul className={styles.priceList}>
              {t.priceList.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}
