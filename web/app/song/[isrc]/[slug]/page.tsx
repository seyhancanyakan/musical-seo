"use client";

/** Tier-4 programatik sarki sayfasi (bkz. docs/PROGRAMATIK_SEO_WORKFLOW.md §5).
 *  Backend uc noktasi (GET /seo/song/{isrc}) ZATEN VAR ama sarki build
 *  pipeline'i henuz baglanmadi -> tablo bos, backend HER ZAMAN 404 doner.
 *  Bu yuzden sayfa ASLA cokmemeli: page===null durumu "henuz hazir degil" +
 *  bildirim formu gosterir (artist sayfasindaki NotBuiltYet ile ayni desen).
 *
 *  Ucretsiz katman: skor/BPM/tonalite + sanatci — sarki basligi + MusicRecording
 *  schema. Derinlemesine icerik (playlist yerlesimleri, cover'lar, tam analiz)
 *  EmailGate arkasinda. data_json'un ic yapisi build pipeline'i henuz
 *  yazilmadigi icin BILINMIYOR — tum okumalar optional-chain + tip guard'li,
 *  alan yoksa bolum sessizce gizlenir (asla patlamaz). */

import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import {
  getSongPage,
  captureLead,
  type SongPage,
} from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import EmailGate from "@/components/EmailGate";
import styles from "./page.module.css";

const T = {
  tr: {
    loading: "Yükleniyor…",
    notBuiltTitle: "Bu şarkı sayfası henüz hazır değil",
    notBuiltLede:
      "Bu şarkı için henüz bir SEO analizi üretilmedi. Hazır olduğunda haber vermemizi ister misin?",
    notBuiltPlaceholder: "e-posta adresin",
    notBuiltSubmit: "Beni bilgilendir",
    notBuiltSending: "Gönderiliyor…",
    notBuiltSent: "Teşekkürler! Hazır olunca haber vereceğiz.",
    scoreOf: "/100 SEO skoru",
    bpm: "BPM",
    key: "Ton",
    unknown: "—",
    updated: "Son güncelleme",
    gateHeadline: "Tam analiz + playlist yerleşimleri + cover'lar için e-posta gir.",
    deepTitle: "Derinlemesine Analiz",
    playlistsTitle: "Bu Şarkının Bulunduğu Playlistler",
    coversTitle: "Bilinen Cover'lar",
    subscoresTitle: "Skor Kırılımı",
    noDeepData: "Bu şarkı için henüz ek veri işlenmedi.",
    fraudCta: "Bir playlist'in sahte olup olmadığını mı merak ediyorsun?",
    fraudLink: "Sahte Playlist Analizi →",
  },
  en: {
    loading: "Loading…",
    notBuiltTitle: "This song page isn't built yet",
    notBuiltLede:
      "No SEO analysis has been generated for this song yet. Want us to notify you when it's ready?",
    notBuiltPlaceholder: "your email",
    notBuiltSubmit: "Notify me",
    notBuiltSending: "Sending…",
    notBuiltSent: "Thanks! We'll let you know when it's ready.",
    scoreOf: "/100 SEO score",
    bpm: "BPM",
    key: "Key",
    unknown: "—",
    updated: "Last updated",
    gateHeadline: "Enter your email for the full analysis + playlist placements + covers.",
    deepTitle: "Deep Analysis",
    playlistsTitle: "Playlists This Song Is On",
    coversTitle: "Known Covers",
    subscoresTitle: "Score Breakdown",
    noDeepData: "No extra data has been processed for this song yet.",
    fraudCta: "Wondering if a playlist is fake?",
    fraudLink: "Fake Playlist Analysis →",
  },
};

type DeepPlaylist = { title?: string; url?: string; platform?: string };
type DeepCover = { artist?: string; title?: string; url?: string };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asPlaylistList(value: unknown): DeepPlaylist[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord) as DeepPlaylist[];
}

function asCoverList(value: unknown): DeepCover[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord) as DeepCover[];
}

function asSubscores(value: unknown): Record<string, number> {
  if (!isRecord(value)) return {};
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(value)) {
    if (typeof v === "number") out[k] = v;
  }
  return out;
}

function NotBuiltYet({ isrc, t }: { isrc: string; t: (typeof T)["tr"] }) {
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = email.trim();
    if (!trimmed || sending) return;
    setSending(true);
    setError(null);
    try {
      const { data, error: apiError } = await captureLead(
        trimmed,
        `song_notify_${isrc}`,
        { isrc }
      );
      if (data?.ok) {
        setSent(true);
        return;
      }
      setError(apiError ?? "—");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className={`nb-card ${styles.notBuilt}`}>
      <h1 className="nb-h">{t.notBuiltTitle}</h1>
      <p>{t.notBuiltLede}</p>
      {sent ? (
        <p className={styles.notifySent}>{t.notBuiltSent}</p>
      ) : (
        <form className={styles.notifyForm} onSubmit={handleSubmit}>
          <input
            type="email"
            required
            className="nb-input"
            placeholder={t.notBuiltPlaceholder}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <button type="submit" className="nb-btn" disabled={sending}>
            {sending ? t.notBuiltSending : t.notBuiltSubmit}
          </button>
        </form>
      )}
      {error && <p className={styles.notifyError}>{error}</p>}
    </div>
  );
}

export default function SongSeoPage() {
  const params = useParams<{ isrc: string; slug: string }>();
  const isrc = params?.isrc ?? "";
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [page, setPage] = useState<SongPage | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isrc) {
      setLoading(false);
      return;
    }
    let alive = true;
    (async () => {
      const result = await getSongPage(isrc);
      if (alive) {
        setPage(result);
        setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [isrc]);

  if (loading) {
    return (
      <div className={styles.page}>
        <main className={styles.body}>
          <div className={styles.loading}>{t.loading}</div>
        </main>
      </div>
    );
  }

  if (!page) {
    return (
      <div className={styles.page}>
        <main className={styles.body}>
          <NotBuiltYet isrc={isrc} t={t} />
        </main>
      </div>
    );
  }

  const score = page.score == null ? null : Math.max(0, Math.min(100, Math.round(page.score)));
  const gaugeColor =
    score === null ? "#888" : score >= 70 ? "var(--green)" : score >= 40 ? "#ffb020" : "var(--red)";

  const playlists = asPlaylistList(page.data_json?.playlists);
  const covers = asCoverList(page.data_json?.covers);
  const subscores = asSubscores(page.data_json?.subscores);
  const hasDeepData = playlists.length > 0 || covers.length > 0 || Object.keys(subscores).length > 0;

  // Schema.org — sadece elimizdeki gercek alanlardan turetilir.
  const schema = {
    "@context": "https://schema.org",
    "@type": "MusicRecording",
    name: page.title,
    byArtist: { "@type": "MusicGroup", name: page.artist },
    isrcCode: page.isrc,
  };

  return (
    <div className={styles.page}>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
      />
      <main className={styles.body}>
        <div className={styles.head}>
          <div
            className={styles.gauge}
            style={{
              background:
                score === null
                  ? "#e6e6e0"
                  : `conic-gradient(${gaugeColor} 0 ${score}%, #e6e6e0 ${score}% 100%)`,
            }}
          >
            <div className={styles.gaugeInner}>
              <div>
                <div className={styles.gaugeScore} style={{ color: gaugeColor }}>
                  {score ?? t.unknown}
                </div>
                <div className={styles.gaugeOf}>{t.scoreOf}</div>
              </div>
            </div>
          </div>
          <div className={styles.headMeta}>
            <div className={styles.tagRow}>
              {page.bpm != null && (
                <span className="nb-pill nb-pill--blue">{Math.round(page.bpm)} {t.bpm}</span>
              )}
              {page.song_key && <span className="nb-pill nb-pill--purple">{page.song_key}</span>}
            </div>
            <h1 className={`nb-h ${styles.title}`}>{page.title || t.unknown}</h1>
            <div className={styles.artist}>{page.artist || t.unknown}</div>
            {page.last_refreshed_at && (
              <div className={styles.updated}>
                {t.updated}:{" "}
                {new Date(page.last_refreshed_at).toLocaleDateString(
                  locale === "tr" ? "tr-TR" : "en-US"
                )}
              </div>
            )}
          </div>
        </div>

        <p className={styles.gateHeadline}>{t.gateHeadline}</p>
        <EmailGate
          source={`song_${isrc}`}
          teaser={<h3 className={styles.sectionTitle}>{t.deepTitle}</h3>}
        >
          <h3 className={styles.sectionTitle}>{t.deepTitle}</h3>
          {!hasDeepData && <p className={styles.noData}>{t.noDeepData}</p>}

          {Object.keys(subscores).length > 0 && (
            <>
              <h4 className={styles.subTitle}>{t.subscoresTitle}</h4>
              <div className={styles.subscoreGrid}>
                {Object.entries(subscores).map(([key, value]) => (
                  <div key={key} className={`nb-card ${styles.subscoreCard}`}>
                    <span className={styles.subscoreKey}>{key.replace(/_/g, " ")}</span>
                    <span className={styles.subscoreVal}>{value}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {playlists.length > 0 && (
            <>
              <h4 className={styles.subTitle}>{t.playlistsTitle}</h4>
              <ul className={styles.list}>
                {playlists.map((pl, index) => (
                  <li key={index} className={`nb-card ${styles.listItem}`}>
                    {pl.url ? (
                      <a href={pl.url} target="_blank" rel="noopener noreferrer">
                        {pl.title ?? pl.url}
                      </a>
                    ) : (
                      <span>{pl.title ?? "—"}</span>
                    )}
                    {pl.platform && <span className={styles.listMeta}>{pl.platform}</span>}
                  </li>
                ))}
              </ul>
            </>
          )}

          {covers.length > 0 && (
            <>
              <h4 className={styles.subTitle}>{t.coversTitle}</h4>
              <ul className={styles.list}>
                {covers.map((cv, index) => (
                  <li key={index} className={`nb-card ${styles.listItem}`}>
                    {cv.url ? (
                      <a href={cv.url} target="_blank" rel="noopener noreferrer">
                        {cv.artist ?? "—"} — {cv.title ?? page.title}
                      </a>
                    ) : (
                      <span>
                        {cv.artist ?? "—"} — {cv.title ?? page.title}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </EmailGate>

        <div className={`nb-card ${styles.fraudCard}`}>
          <span>{t.fraudCta}</span>
          <a href="/sahte-playlist" className="nb-btn nb-btn--purple">
            {t.fraudLink}
          </a>
        </div>
      </main>
    </div>
  );
}
