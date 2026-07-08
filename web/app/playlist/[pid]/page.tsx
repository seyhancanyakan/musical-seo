"use client";

/** Tier-5 programatik playlist sayfasi (bkz. docs/PROGRAMATIK_SEO_WORKFLOW.md §6).
 *  Backend uc noktasi (GET /seo/playlist/{pid}) ZATEN VAR ama playlist build
 *  pipeline'i henuz baglanmadi -> tablo bos, backend HER ZAMAN 404 doner.
 *  Sayfa ASLA cokmemeli: page===null durumu "henuz hazir degil" + bildirim
 *  formu gosterir (artist/song sayfalariyla ayni desen).
 *
 *  "Bu playlist guvenli mi yoksa sahte mi?" cercevesi — fraud_score + verdict
 *  (sahte-playlist/rapor sayfasindaki VERDICT_MAP fikri kucultulmus halde
 *  yeniden kullanilir), tam analiz icin /sahte-playlist'e link. data_json'un
 *  ic yapisi henuz BILINMIYOR (build pipeline yazilmadi) — tum okumalar
 *  optional-chain'li, alan yoksa bolum sessizce gizlenir. */

import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getPlaylistPage,
  captureLead,
  type PlaylistPage,
} from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import SiteHeader from "@/components/SiteHeader";
import styles from "./page.module.css";

const T = {
  tr: {
    loading: "Yükleniyor…",
    notBuiltTitle: "Bu playlist sayfası henüz hazır değil",
    notBuiltLede:
      "Bu playlist için henüz bir sahtecilik analizi üretilmedi. Hazır olduğunda haber vermemizi ister misin?",
    notBuiltPlaceholder: "e-posta adresin",
    notBuiltSubmit: "Beni bilgilendir",
    notBuiltSending: "Gönderiliyor…",
    notBuiltSent: "Teşekkürler! Hazır olunca haber vereceğiz.",
    unknown: "—",
    updated: "Son güncelleme",
    question: "Bu playlist güvenli mi, sahte mi?",
    fullAnalysisCta: "Tam sahtecilik analizi için:",
    fullAnalysisLink: "Sahte Playlist Analizi →",
  },
  en: {
    loading: "Loading…",
    notBuiltTitle: "This playlist page isn't built yet",
    notBuiltLede:
      "No fraud analysis has been generated for this playlist yet. Want us to notify you when it's ready?",
    notBuiltPlaceholder: "your email",
    notBuiltSubmit: "Notify me",
    notBuiltSending: "Sending…",
    notBuiltSent: "Thanks! We'll let you know when it's ready.",
    unknown: "—",
    updated: "Last updated",
    question: "Is this playlist safe or fake?",
    fullAnalysisCta: "For the full fraud analysis:",
    fullAnalysisLink: "Fake Playlist Analysis →",
  },
};

const VERDICT_MAP: Record<
  string,
  { tr: { pill: string; title: string }; en: { pill: string; title: string }; color: string; emoji: string }
> = {
  guvenli: {
    tr: { pill: "◆ Temiz — Güvenli", title: "Güvenli görünüyor" },
    en: { pill: "◆ Clean — Safe", title: "Looks safe" },
    color: "var(--green)",
    emoji: "✅",
  },
  riskli: {
    tr: { pill: "◆ Şüpheli — Riskli", title: "Dikkatli ol" },
    en: { pill: "◆ Suspicious — Risky", title: "Be careful" },
    color: "#ffb020",
    emoji: "⚠️",
  },
  cok_riskli: {
    tr: { pill: "◆ Yüksek Risk", title: "Para ödeme" },
    en: { pill: "◆ High Risk", title: "Don't pay" },
    color: "var(--red)",
    emoji: "🚫",
  },
  sahte: {
    tr: { pill: "◆ SAHTE", title: "Para ödeme" },
    en: { pill: "◆ FAKE", title: "Don't pay" },
    color: "var(--red)",
    emoji: "🚫",
  },
  veri_yetersiz: {
    tr: { pill: "◆ Veri Yetersiz", title: "Güvenilir analiz için veri gerekli" },
    en: { pill: "◆ Insufficient Data", title: "Needs data for a reliable verdict" },
    color: "var(--blue)",
    emoji: "ℹ️",
  },
};

const VERDICT_DEFAULT = {
  tr: { pill: "◆ Bilinmiyor", title: "Sonuç belirsiz" },
  en: { pill: "◆ Unknown", title: "Verdict unclear" },
  color: "#888",
  emoji: "❓",
};

function NotBuiltYet({ pid, t }: { pid: string; t: (typeof T)["tr"] }) {
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
        `playlist_notify_${pid}`,
        { pid }
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

export default function PlaylistSeoPage() {
  const params = useParams<{ pid: string }>();
  const pid = params?.pid ?? "";
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [page, setPage] = useState<PlaylistPage | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!pid) {
      setLoading(false);
      return;
    }
    let alive = true;
    (async () => {
      const result = await getPlaylistPage(pid);
      if (alive) {
        setPage(result);
        setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [pid]);

  if (loading) {
    return (
      <div className={styles.page}>
        <SiteHeader />
        <main className={styles.body}>
          <div className={styles.loading}>{t.loading}</div>
        </main>
      </div>
    );
  }

  if (!page) {
    return (
      <div className={styles.page}>
        <SiteHeader />
        <main className={styles.body}>
          <NotBuiltYet pid={pid} t={t} />
        </main>
      </div>
    );
  }

  const verdictInfo = VERDICT_MAP[page.verdict ?? ""] ?? VERDICT_DEFAULT;
  const verdictText = pick(verdictInfo, locale);
  const riskScore =
    page.fraud_score == null ? null : Math.max(0, Math.min(100, Math.round(page.fraud_score)));

  // Schema.org — sadece elimizdeki gercek alanlardan turetilir.
  const schema = {
    "@context": "https://schema.org",
    "@type": "MusicPlaylist",
    name: page.title,
  };

  return (
    <div className={styles.page}>
      <SiteHeader />
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
                riskScore === null
                  ? "#e6e6e0"
                  : `conic-gradient(${verdictInfo.color} 0 ${riskScore}%, #e6e6e0 ${riskScore}% 100%)`,
            }}
          >
            <div className={styles.gaugeInner}>
              <div>
                <div className={styles.gaugeScore} style={{ color: verdictInfo.color }}>
                  {riskScore ?? t.unknown}
                </div>
                <div className={styles.gaugeOf}>/100 risk</div>
              </div>
            </div>
          </div>
          <div className={styles.headMeta}>
            <span className="nb-pill nb-pill--red">{verdictText.pill}</span>
            <h1 className={`nb-h ${styles.title}`}>{page.title || t.unknown}</h1>
            <div className={styles.question}>{t.question}</div>
            <div className={styles.verdict}>
              <span className={styles.verdictEmoji}>{verdictInfo.emoji}</span>
              <div className={styles.verdictTitle} style={{ color: verdictInfo.color }}>
                {verdictText.title}
              </div>
            </div>
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

        <div className={`nb-card ${styles.fullCard}`}>
          <span>{t.fullAnalysisCta}</span>
          <Link href="/sahte-playlist" className="nb-btn nb-btn--purple">
            {t.fullAnalysisLink}
          </Link>
        </div>
      </main>
    </div>
  );
}
