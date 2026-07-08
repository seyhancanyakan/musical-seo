"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { analyzeFraud } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import SiteHeader from "@/components/SiteHeader";
import styles from "./page.module.css";

const DEMO_URL = "https://open.spotify.com/playlist/37i9dQZF1DX...";
const DEMO_TOKEN = "FRAUD-8F2A";

const T = {
  tr: {
    pill: "Adli Analiz",
    title: (
      <>
        Para ödemeden önce
        <br />o playlist sahte mi?
      </>
    ),
    lede:
      "Follower anomalisi, track churn, coğrafi kümelenme, audio-etiket uyumu ve şarkı SEO skorundan 5 sinyalle risk hesaplar. Botla dolu bir listeye ödeme yapıp telifini kaybetme.",
    label: "Playlist Bağlantısı",
    submit: "⚖ Analiz Et — 2 kredi",
    analyzing: "Analiz Ediliyor...",
    demoCta: "Örnek raporu gör",
    chips: ["Spotify", "Deezer", "Apple Music", "~40 sn"],
    priceKicker: "Sigorta modeli",
    priceBig: "5",
    priceSmall: "kredi",
    priceNote: '"Güvenli" dedik, zarar gelirse telifini karşılarız.',
    priceList: [
      <>
        <b>5 sinyal</b> paralel adli tarama
      </>,
      "Kanıt paketi + paylaşılabilir token",
      <>
        <b>Pro üyelere</b> temel rapor ücretsiz
      </>,
    ],
    errorPrefix: "Analiz başarısız:",
  },
  en: {
    pill: "Forensic Analysis",
    title: (
      <>
        Before you pay,
        <br />is that playlist fake?
      </>
    ),
    lede:
      "Computes risk from 5 signals: follower anomaly, track churn, geographic clustering, audio-tag consistency, and song SEO score. Don't pay a bot-filled list and lose your royalties.",
    label: "Playlist Link",
    submit: "⚖ Analyze — 2 credits",
    analyzing: "Analyzing...",
    demoCta: "See sample report",
    chips: ["Spotify", "Deezer", "Apple Music", "~40 sec"],
    priceKicker: "Insurance model",
    priceBig: "5",
    priceSmall: "credits",
    priceNote: 'We said "safe" — if it isn\'t, we cover your loss.',
    priceList: [
      <>
        <b>5 signals</b> parallel forensic scan
      </>,
      "Evidence pack + shareable token",
      <>
        <b>Pro members</b> get the base report free
      </>,
    ],
    errorPrefix: "Analysis failed:",
  },
};

export default function SahtePlaylistPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);
  const router = useRouter();

  const [url, setUrl] = useState(DEMO_URL);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError(null);
    try {
      const { data, error: apiError } = await analyzeFraud(trimmed);
      if (data?.report_token) {
        router.push(`/sahte-playlist/rapor/${encodeURIComponent(data.report_token)}`);
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
        <span className="nb-pill nb-pill--red">{t.pill}</span>
        <h1 className={`nb-h ${styles.title}`}>{t.title}</h1>
        <p className={styles.lede}>{t.lede}</p>

        <div className={styles.heroInput}>
          <form className={`nb-card ${styles.formCard}`} onSubmit={handleSubmit}>
            <label className={styles.lbl} htmlFor="playlist-url">
              {t.label}
            </label>
            <input
              id="playlist-url"
              className={`nb-input ${styles.mono}`}
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder={DEMO_URL}
            />
            <div className={styles.actionsRow}>
              <button type="submit" className="nb-btn" disabled={loading}>
                {loading ? t.analyzing : t.submit}
              </button>
              <Link
                href={`/sahte-playlist/rapor/${DEMO_TOKEN}`}
                className="nb-btn nb-btn--outline"
              >
                {t.demoCta}
              </Link>
            </div>
            {error && (
              <div className={styles.errorBanner}>
                {t.errorPrefix} {error}
              </div>
            )}
            <div className={styles.chipsRow}>
              {t.chips.map((chip) => (
                <span key={chip} className="nb-chip">
                  {chip}
                </span>
              ))}
            </div>
          </form>

          <div className={styles.priceCard}>
            <div className={styles.priceKicker}>{t.priceKicker}</div>
            <div className={styles.priceBig}>
              {t.priceBig}
              <span className={styles.priceSmall}> {t.priceSmall}</span>
            </div>
            <div className={styles.priceNote}>{t.priceNote}</div>
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
