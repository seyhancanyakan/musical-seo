"use client";

import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { analyzeFraudStream, type FraudStreamEvent } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";

const DEMO_URL = "https://open.spotify.com/playlist/37i9dQZF1DX...";
const DEMO_TOKEN = "FRAUD-8F2A";

/** Sunucudaki analyze_playlist(progress=...) asama sirasiyla BIREBIR ayni
 *  (bkz. marketplace/fraud_forensics.py _emit cagrilari). */
const STAGE_ORDER = ["resolve", "snapshot", "audio", "seo", "signals"] as const;
type Stage = (typeof STAGE_ORDER)[number];

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
    stageLabels: {
      resolve: "Playlist Çözümleniyor",
      snapshot: "Spotify Anlık Görüntüsü",
      audio: "Ses Profili Analizi",
      seo: "Parça SEO Analizi",
      signals: "Sinyal Değerlendirme",
    } as Record<Stage, string>,
    stagePanelTitle: "Analiz sürüyor…",
    stagePanelNote: "Bu genelde 1-3 dakika sürer — sayfayı kapatma.",
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
    stageLabels: {
      resolve: "Resolving Playlist",
      snapshot: "Spotify Snapshot",
      audio: "Audio Profile Analysis",
      seo: "Track SEO Analysis",
      signals: "Signal Evaluation",
    } as Record<Stage, string>,
    stagePanelTitle: "Analysis in progress…",
    stagePanelNote: "This usually takes 1-3 minutes — don't close the page.",
  },
};

export default function SahtePlaylistPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);
  const router = useRouter();

  const [url, setUrl] = useState(DEMO_URL);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Canli analiz VFX durumu — asama sirasiyla isik yakiyor, biten checkmark aliyor.
  const [activeStageIdx, setActiveStageIdx] = useState(-1);
  const [doneStages, setDoneStages] = useState<Stage[]>([]);
  const [stageMsgs, setStageMsgs] = useState<Partial<Record<Stage, string>>>({});
  const navigatedRef = useRef(false);

  function handleStreamEvent(ev: FraudStreamEvent) {
    if (ev.stage === "error") {
      setLoading(false);
      setError(ev.msg || "—");
      return;
    }
    if (ev.stage === "done") {
      setDoneStages([...STAGE_ORDER]);
      const token = ev.data?.report_token;
      setLoading(false);
      if (typeof token === "string" && token && !navigatedRef.current) {
        navigatedRef.current = true;
        router.push(`/sahte-playlist/rapor/${encodeURIComponent(token)}`);
      } else if (!token) {
        setError("—");
      }
      return;
    }
    const idx = STAGE_ORDER.indexOf(ev.stage as Stage);
    if (idx === -1) return;
    setActiveStageIdx(idx);
    setDoneStages((prev) => {
      const completed = STAGE_ORDER.slice(0, idx);
      const next = new Set([...prev, ...completed]);
      return STAGE_ORDER.filter((s) => next.has(s));
    });
    setStageMsgs((prev) => ({ ...prev, [ev.stage]: ev.msg }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError(null);
    setActiveStageIdx(-1);
    setDoneStages([]);
    setStageMsgs({});
    navigatedRef.current = false;
    try {
      await analyzeFraudStream(trimmed, handleStreamEvent);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.page}>

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
            {loading && (
              <div className={styles.stagePanel} aria-live="polite">
                <div className={styles.stagePanelHead}>
                  <span className={styles.stagePanelTitle}>{t.stagePanelTitle}</span>
                  <span className={styles.stagePanelNote}>{t.stagePanelNote}</span>
                </div>
                <ul className={styles.stageList}>
                  {STAGE_ORDER.map((stage, i) => {
                    const isDone = doneStages.includes(stage);
                    const isActive = i === activeStageIdx && !isDone;
                    return (
                      <li
                        key={stage}
                        className={`${styles.stageItem} ${
                          isActive ? styles.stageItemActive : ""
                        } ${isDone ? styles.stageItemDone : ""}`}
                      >
                        <span className={styles.stageBullet}>
                          {isDone ? "✓" : i + 1}
                        </span>
                        <span className={styles.stageBody}>
                          <span className={styles.stageLabel}>
                            {t.stageLabels[stage]}
                          </span>
                          {stageMsgs[stage] && (
                            <span className={styles.stageMsg}>{stageMsgs[stage]}</span>
                          )}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
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
