"use client";

/** Tier-2 ucretsiz arac sayfasi — tek query input, anlik API sonucu.
 *  4 slug API'ye baglanir (bpm/key/isrc/monthly-listeners); fraud/cover
 *  slug'lari kendi tam sayfalarina (sahte-playlist, cover-avcisi) yonlendirir;
 *  bilinmeyen slug notFound(). SoftwareApplication + HowTo JSON-LD ekler
 *  (araclar programatik SEO'nun organik trafik motoru). */

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter, notFound } from "next/navigation";
import EmailGate from "@/components/EmailGate";
import { useLocale, pick } from "@/lib/locale";
import {
  toolBpm, toolKey, toolIsrc, toolMonthlyListeners,
  type BpmResult, type KeyResult, type IsrcResult, type MonthlyListenersResult,
} from "@/lib/api";
import styles from "./page.module.css";

type ToolKind = "bpm" | "key" | "isrc" | "listeners";
type ToolResult = BpmResult | KeyResult | IsrcResult | MonthlyListenersResult;

/** Eski/muhtemel gelen linkler dogrudan kendi tam sayfasina gitsin — bu iki
 *  nis ozellik (dunya-ilk) /tools/[tool] altinda degil, kendi rotasinda yasar. */
const REDIRECTS: Record<string, string> = {
  "fake-playlist-checker": "/sahte-playlist",
  "fake-playlist": "/sahte-playlist",
  "cover-finder": "/cover-avcisi",
  "cover-hunter": "/cover-avcisi",
};

type ToolConfig = {
  kind: ToolKind;
  demoQuery: string;
  tr: { pill: string; title: string; lede: string; submit: string; placeholder: string };
  en: { pill: string; title: string; lede: string; submit: string; placeholder: string };
};

const TOOLS: Record<string, ToolConfig> = {
  "bpm-finder": {
    kind: "bpm",
    demoQuery: "Tarkan - Şımarık",
    tr: {
      pill: "Ücretsiz Araç",
      title: "BPM Bulucu",
      lede: "Şarkının adını yaz, gerçek ses analiziyle tempoyu (BPM) saniyeler içinde öğren. Deezer'ın 30 sn önizlemesinden hesaplanır.",
      submit: "🎵 BPM'i Bul",
      placeholder: "Sanatçı - Şarkı",
    },
    en: {
      pill: "Free Tool",
      title: "BPM Finder",
      lede: "Type a song name, get its real tempo (BPM) in seconds — computed from a Deezer 30-second preview.",
      submit: "🎵 Find BPM",
      placeholder: "Artist - Title",
    },
  },
  "song-key-detector": {
    kind: "key",
    demoQuery: "Tarkan - Şımarık",
    tr: {
      pill: "Ücretsiz Araç",
      title: "Şarkı Tonu Tahmincisi",
      lede: "Ses profilinden (parlaklık/enerji) sezgisel bir ton tahmini üretir — gerçek bir chroma/pitch-class analizi değildir, hızlı bir ipucudur.",
      submit: "🎹 Tonu Tahmin Et",
      placeholder: "Sanatçı - Şarkı",
    },
    en: {
      pill: "Free Tool",
      title: "Song Key Detector",
      lede: "Produces a heuristic key estimate from the audio profile (brightness/energy) — not a real chroma/pitch-class analysis, just a quick hint.",
      submit: "🎹 Estimate Key",
      placeholder: "Artist - Title",
    },
  },
  "isrc-lookup": {
    kind: "isrc",
    demoQuery: "Tarkan - Şımarık",
    tr: {
      pill: "Ücretsiz Araç",
      title: "ISRC Sorgulama",
      lede: "Sanatçı - şarkı adını gir, uluslararası standart kayıt kodunu (ISRC) ve yayın tarihini Deezer katalog verisinden bul.",
      submit: "🔖 ISRC Bul",
      placeholder: "Sanatçı - Şarkı",
    },
    en: {
      pill: "Free Tool",
      title: "ISRC Lookup",
      lede: "Enter Artist - Title, find the International Standard Recording Code (ISRC) and release date from Deezer catalog data.",
      submit: "🔖 Find ISRC",
      placeholder: "Artist - Title",
    },
  },
  "spotify-monthly-listeners-tracker": {
    kind: "listeners",
    demoQuery: "Tarkan - Şımarık",
    tr: {
      pill: "Ücretsiz Araç",
      title: "Aylık Dinleyici Takibi",
      lede: "Spotify aylık dinleyici sayısı public API'de yok (yalnızca Spotify for Artists — kimlik doğrulamalı). Burada neden mümkün olmadığını ve gerçek alternatifleri görürsün.",
      submit: "📊 Sorgula",
      placeholder: "Sanatçı - Şarkı",
    },
    en: {
      pill: "Free Tool",
      title: "Monthly Listeners Tracker",
      lede: "Spotify monthly listeners isn't in the public API (only Spotify for Artists — authenticated). See why, and the real alternatives.",
      submit: "📊 Look Up",
      placeholder: "Artist - Title",
    },
  },
};

const CTA_T = {
  tr: {
    title: "Bu şarkıyı takip et",
    lede: "E-postanı bırak — skor, playlist eşleşmesi ve daha fazlasını gerçek zamanlı takip et.",
  },
  en: {
    title: "Track this song",
    lede: "Leave your email — track score, playlist matches, and more in real time.",
  },
};

function callTool(kind: ToolKind, query: string) {
  if (kind === "bpm") return toolBpm(query);
  if (kind === "key") return toolKey(query);
  if (kind === "isrc") return toolIsrc(query);
  return toolMonthlyListeners(query);
}

function ResultDisplay({ kind, result, tr }: { kind: ToolKind; result: ToolResult; tr: boolean }) {
  if (!result.found) {
    return (
      <div className={styles.notFoundNote}>
        {kind === "listeners"
          ? (result as MonthlyListenersResult).note
          : tr
            ? "Bulunamadı — şarkı adını ve sanatçıyı kontrol et."
            : "Not found — check the artist and song name."}
      </div>
    );
  }

  if (kind === "bpm") {
    const r = result as BpmResult;
    return (
      <div className={styles.resultGrid}>
        <div className={styles.stat}>
          <span className={styles.statLabel}>{tr ? "Sanatçı" : "Artist"}</span>
          <span className={styles.statValue} style={{ fontSize: 16 }}>{r.artist}</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>BPM</span>
          <span className={styles.statValue}>{r.bpm}</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>{tr ? "Enerji" : "Energy"}</span>
          <span className={styles.statValue}>{Math.round((r.energy ?? 0) * 100)}%</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>{tr ? "Parlaklık" : "Brightness"}</span>
          <span className={styles.statValue}>{Math.round((r.brightness ?? 0) * 100)}%</span>
        </div>
      </div>
    );
  }

  if (kind === "key") {
    const r = result as KeyResult;
    return (
      <>
        <div className={styles.resultGrid}>
          <div className={styles.stat}>
            <span className={styles.statLabel}>{tr ? "Sanatçı" : "Artist"}</span>
            <span className={styles.statValue} style={{ fontSize: 16 }}>{r.artist}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>{tr ? "Tahmini Ton" : "Estimated Key"}</span>
            <span className={styles.statValue}>{r.estimated_key}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>{tr ? "Güven" : "Confidence"}</span>
            <span className={styles.statValue}>{Math.round((r.confidence ?? 0) * 100)}%</span>
          </div>
        </div>
        <p className={styles.heuristicNote}>{r.note}</p>
      </>
    );
  }

  if (kind === "isrc") {
    const r = result as IsrcResult;
    return (
      <div className={styles.resultGrid}>
        <div className={styles.stat}>
          <span className={styles.statLabel}>{tr ? "Sanatçı" : "Artist"}</span>
          <span className={styles.statValue} style={{ fontSize: 16 }}>{r.artist}</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>ISRC</span>
          <span className={styles.statValue} style={{ fontSize: 20 }}>{r.isrc}</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>{tr ? "Yayın Tarihi" : "Release Date"}</span>
          <span className={styles.statValue} style={{ fontSize: 16 }}>{r.release_date ?? "—"}</span>
        </div>
      </div>
    );
  }

  return null;
}

export default function ToolPage() {
  const params = useParams<{ tool: string }>();
  const tool = params?.tool ?? "";
  const router = useRouter();
  const { locale } = useLocale();
  const tr = locale === "tr";

  const config = TOOLS[tool];
  const redirectTarget = REDIRECTS[tool];

  useEffect(() => {
    if (redirectTarget) router.replace(redirectTarget);
  }, [redirectTarget, router]);

  const [query, setQuery] = useState(config?.demoQuery ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ToolResult | null>(null);

  if (!config && !redirectTarget) {
    notFound();
  }
  if (!config) {
    // Yonlendirme akiyor — bosuna sonuc/skeleton cizmeyelim.
    return null;
  }

  const t = pick(config, locale);
  const ctaT = pick(CTA_T, locale);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const { data, error: apiError } = await callTool(config.kind, trimmed);
      if (data) {
        setResult(data);
        return;
      }
      setError(apiError ?? "—");
    } finally {
      setLoading(false);
    }
  }

  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "SoftwareApplication",
        name: t.title,
        applicationCategory: "MusicApplication",
        operatingSystem: "Web",
        offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
        description: t.lede,
      },
      {
        "@type": "HowTo",
        name: t.title,
        step: [
          {
            "@type": "HowToStep",
            text: tr ? "Sanatçı ve şarkı adını gir." : "Enter the artist and song name.",
          },
          {
            "@type": "HowToStep",
            text: tr ? "Sonucu anında görüntüle — kayıt gerekmez." : "View the result instantly — no signup required.",
          },
        ],
      },
    ],
  };

  return (
    <div className={styles.page}>
      <script
        type="application/ld+json"
        // Guvenli: sabit sablon + bu bilesenin kendi metinleri; kullanici girdisi yok.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
      />
      <main className={styles.body}>
        <span className="nb-pill nb-pill--blue">{t.pill}</span>
        <h1 className={`nb-h ${styles.title}`}>{t.title}</h1>
        <p className={styles.lede}>{t.lede}</p>

        <form className={`nb-card ${styles.formCard}`} onSubmit={handleSubmit}>
          <label className={styles.lbl} htmlFor="tool-query">
            {t.placeholder}
          </label>
          <input
            id="tool-query"
            className="nb-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t.placeholder}
          />
          <div className={styles.row}>
            <button type="submit" className="nb-btn" disabled={loading}>
              {loading ? (tr ? "Aranıyor…" : "Searching…") : t.submit}
            </button>
          </div>
          {error && <div className={styles.errorBanner}>{error}</div>}
        </form>

        {result && (
          <div className={`nb-card ${styles.resultCard}`}>
            <p className={styles.resultHead}>
              {tr ? "Sonuç" : "Result"} · “{result.query}”
            </p>
            <ResultDisplay kind={config.kind} result={result} tr={tr} />
          </div>
        )}

        {result?.found && (
          <div className={styles.teaser}>
            <EmailGate source={`tool_${tool}`}>
              <div className="nb-card" style={{ padding: 20 }}>
                <strong>{ctaT.title}</strong>
                <p style={{ margin: "8px 0 0", fontSize: 13, color: "#555" }}>{ctaT.lede}</p>
              </div>
            </EmailGate>
          </div>
        )}
      </main>
    </div>
  );
}
