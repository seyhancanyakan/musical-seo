"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { buildAttribution } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";

const DEMO_QUERY = "Mira — Gece Yarısı";
const DEMO_START = "2026-05-01";
const DEMO_END = "2026-07-01";
const DEMO_TOKEN = "ATTR-3C7D";

const T = {
  tr: {
    pill: "ROI Atıf Motoru",
    title: (
      <>
        Hangi yatırım
        <br />skoru getirdi?
      </>
    ),
    lede:
      "Küratör yerleşimi, radyo reklamı, spot — her tanıtımın SEO skoruna kaç puan kattığını zaman serisi kırılma noktalarıyla ölçer. \"Radyoyu %40 artır, playlist'i azalt\" gibi net karar üretir.",
    songLabel: "Şarkı / Sorgu",
    startLabel: "Başlangıç",
    endLabel: "Bitiş",
    submit: "📈 Rapor Oluştur — 1 kredi",
    working: "Oluşturuluyor...",
    demoCta: "Son raporlarım",
    priceKicker: "3 veri akışı",
    priceBig: "Skor + Yerleşim + Radyo",
    priceList: [
      <>
        <b>snapshots.db</b> — günlük SEO skoru
      </>,
      <>
        <b>submissions</b> — kanıtlı yerleşim
      </>,
      <>
        <b>fp_detections</b> — parmak izli radyo çalınma
      </>,
    ],
    errorPrefix: "Oluşturma başarısız:",
  },
  en: {
    pill: "ROI Attribution Engine",
    title: (
      <>
        Which investment
        <br />drove the score?
      </>
    ),
    lede:
      "Measures how many score points each promo — curator placement, radio ad, spot — contributed, using time-series changepoints. Produces clear calls like \"boost radio 40%, cut playlist spend.\"",
    songLabel: "Song / Query",
    startLabel: "Start",
    endLabel: "End",
    submit: "📈 Build Report — 1 credit",
    working: "Building...",
    demoCta: "My recent reports",
    priceKicker: "3 data feeds",
    priceBig: "Score + Placement + Radio",
    priceList: [
      <>
        <b>snapshots.db</b> — daily SEO score
      </>,
      <>
        <b>submissions</b> — verified placements
      </>,
      <>
        <b>fp_detections</b> — fingerprinted radio airplay
      </>,
    ],
    errorPrefix: "Build failed:",
  },
};

export default function AttributionPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);
  const router = useRouter();

  const [query, setQuery] = useState(DEMO_QUERY);
  const [start, setStart] = useState(DEMO_START);
  const [end, setEnd] = useState(DEMO_END);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim() || loading) return;

    setLoading(true);
    setError(null);
    try {
      const { data, error: apiError } = await buildAttribution({
        track_query: query.trim(),
        period_start: start,
        period_end: end,
      });
      if (data?.report_token) {
        router.push(`/attribution/rapor/${encodeURIComponent(data.report_token)}`);
        return;
      }
      setError(apiError ?? "—");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.page}>

      <main className={styles.body}>
        <span className="nb-pill nb-pill--purple">{t.pill}</span>
        <h1 className={`nb-h ${styles.title}`}>{t.title}</h1>
        <p className={styles.lede}>{t.lede}</p>

        <div className={styles.heroInput}>
          <form className={`nb-card ${styles.formCard}`} onSubmit={handleSubmit}>
            <div>
              <label className={styles.lbl} htmlFor="attr-query">
                {t.songLabel}
              </label>
              <input
                id="attr-query"
                className="nb-input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
            <div className={styles.grid2}>
              <div>
                <label className={styles.lbl} htmlFor="attr-start">
                  {t.startLabel}
                </label>
                <input
                  id="attr-start"
                  type="date"
                  className={`nb-input ${styles.mono}`}
                  value={start}
                  onChange={(event) => setStart(event.target.value)}
                />
              </div>
              <div>
                <label className={styles.lbl} htmlFor="attr-end">
                  {t.endLabel}
                </label>
                <input
                  id="attr-end"
                  type="date"
                  className={`nb-input ${styles.mono}`}
                  value={end}
                  onChange={(event) => setEnd(event.target.value)}
                />
              </div>
            </div>
            <div className={styles.actionsRow}>
              <button type="submit" className="nb-btn nb-btn--purple" disabled={loading}>
                {loading ? t.working : t.submit}
              </button>
              <Link href={`/attribution/rapor/${DEMO_TOKEN}`} className="nb-btn nb-btn--outline">
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
