"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { adviseRelease } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import SiteHeader from "@/components/SiteHeader";
import styles from "./page.module.css";

const DEMO_QUERY = "Deniz Ada — Kıyı";
const DEMO_DATE = "2026-07-20";
const DEMO_TOKEN = "TIME-51B9";

const T = {
  tr: {
    pill: "Yayın Zamanlaması",
    title: (
      <>
        Yanlış tarihte çıkma.
        <br />Algoritmaya gömülme.
      </>
    ),
    lede:
      "Hazırlık skoru, anahtar kelime rekabeti, aynı hafta rakip release'ler ve gün optimizasyonundan tavsiye üretir. \"20 Temmuz riskli — önce şunları yap, 4 Ağustos'ta çık.\"",
    songLabel: "Şarkı / Sanatçı",
    dateLabel: "Hedef Yayın Tarihi",
    submit: "🗓 Analiz Et — 1 kredi",
    working: "Analiz Ediliyor...",
    demoCta: "Takvimime ekle",
    priceKicker: "4 sinyal",
    priceBig: "Hazırlık · Rekabet · Rakip · Gün",
    priceList: [
      <>
        <b>audit.py</b> hazırlık skoru
      </>,
      <>
        <b>autocomplete</b> keyword rekabeti
      </>,
      <>
        <b>musicbrainz</b> rakip release taraması
      </>,
    ],
    errorPrefix: "Analiz başarısız:",
  },
  en: {
    pill: "Release Timing",
    title: (
      <>
        Release on the wrong date.
        <br />Vanish into the algorithm.
      </>
    ),
    lede:
      "Produces advice from readiness score, keyword competition, competing releases the same week, and day-of-week optimization. \"July 20 is risky — do this first, launch August 4 instead.\"",
    songLabel: "Song / Artist",
    dateLabel: "Target Release Date",
    submit: "🗓 Analyze — 1 credit",
    working: "Analyzing...",
    demoCta: "Add to my calendar",
    priceKicker: "4 signals",
    priceBig: "Readiness · Competition · Rivals · Day",
    priceList: [
      <>
        <b>audit.py</b> readiness score
      </>,
      <>
        <b>autocomplete</b> keyword competition
      </>,
      <>
        <b>musicbrainz</b> competing release scan
      </>,
    ],
    errorPrefix: "Analysis failed:",
  },
};

export default function ReleaseTimingPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);
  const router = useRouter();

  const [query, setQuery] = useState(DEMO_QUERY);
  const [date, setDate] = useState(DEMO_DATE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim() || loading) return;

    setLoading(true);
    setError(null);
    try {
      const { data, error: apiError } = await adviseRelease({
        track_query: query.trim(),
        target_date: date,
      });
      if (data?.report_token) {
        router.push(`/yayin-zamanlamasi/rapor/${encodeURIComponent(data.report_token)}`);
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
        <span className="nb-pill nb-pill--blue">{t.pill}</span>
        <h1 className={`nb-h ${styles.title}`}>{t.title}</h1>
        <p className={styles.lede}>{t.lede}</p>

        <div className={styles.heroInput}>
          <form className={`nb-card ${styles.formCard}`} onSubmit={handleSubmit}>
            <div>
              <label className={styles.lbl} htmlFor="rel-query">
                {t.songLabel}
              </label>
              <input
                id="rel-query"
                className="nb-input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
            <div>
              <label className={styles.lbl} htmlFor="rel-date">
                {t.dateLabel}
              </label>
              <input
                id="rel-date"
                type="date"
                className={`nb-input ${styles.mono}`}
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
            </div>
            <div className={styles.actionsRow}>
              <button type="submit" className="nb-btn" disabled={loading}>
                {loading ? t.working : t.submit}
              </button>
              <Link href={`/yayin-zamanlamasi/rapor/${DEMO_TOKEN}`} className="nb-btn nb-btn--outline">
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
