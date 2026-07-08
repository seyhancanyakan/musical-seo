"use client";

/** Tier-3 programatik sanatci sayfasi (bkz. docs/PROGRAMATIK_SEO_WORKFLOW.md §4).
 *  Ucretsiz katman (Google + herkes): skor gostergesi, kac platformda, ilk 3
 *  bulgu, MusicGroup+AggregateRating schema. Derinlemesine icerik (kalan
 *  bulgular + tam rapor CTA) EmailGate arkasinda. Sayfa hic uretilmemisse
 *  (backend 404 -> null) asla cokmez, "henuz hazir degil" + bildirim formu
 *  gosterir. */

import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getArtistPage,
  captureLead,
  type ArtistPage,
  type ArtistPageFinding,
} from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import SiteHeader from "@/components/SiteHeader";
import EmailGate from "@/components/EmailGate";
import styles from "./page.module.css";

const T = {
  tr: {
    loading: "Yükleniyor…",
    notBuiltTitle: "Bu sanatçı sayfası henüz hazır değil",
    notBuiltLede:
      "Bu sanatçı için henüz bir SEO Karnesi üretilmedi. Hazır olduğunda haber vermemizi ister misin?",
    notBuiltPlaceholder: "e-posta adresin",
    notBuiltSubmit: "Beni bilgilendir",
    notBuiltSending: "Gönderiliyor…",
    notBuiltSent: "Teşekkürler! Hazır olunca haber vereceğiz.",
    platforms: (n: number) => `${n} platformda bulundu`,
    scoreOf: "/100 SEO skoru",
    findingsTitle: "Öne Çıkan Bulgular",
    gateHeadline: (score: number) =>
      `Skorun ${score}. Tam rapor + gerçek zamanlı takip için e-posta gir.`,
    remainingFindings: "Kalan Bulgular + Tam Rapor",
    claimTitle: "Bu senin sayfan mı?",
    claimCta: "Talep Et",
    updated: "Son güncelleme",
  },
  en: {
    loading: "Loading…",
    notBuiltTitle: "This artist page isn't built yet",
    notBuiltLede:
      "No SEO report card has been generated for this artist yet. Want us to notify you when it's ready?",
    notBuiltPlaceholder: "your email",
    notBuiltSubmit: "Notify me",
    notBuiltSending: "Sending…",
    notBuiltSent: "Thanks! We'll let you know when it's ready.",
    platforms: (n: number) => `Found on ${n} platforms`,
    scoreOf: "/100 SEO score",
    findingsTitle: "Top Findings",
    gateHeadline: (score: number) =>
      `Your score is ${score}. Enter your email for the full report + real-time tracking.`,
    remainingFindings: "Remaining Findings + Full Report",
    claimTitle: "Is this your page?",
    claimCta: "Claim It",
    updated: "Last updated",
  },
};

const SEVERITY_COLOR: Record<string, string> = {
  critical: "var(--red)",
  warn: "#ffb020",
  info: "var(--blue)",
  ok: "var(--green)",
};

function findingColor(severity?: string): string {
  return SEVERITY_COLOR[severity ?? ""] ?? "#888";
}

function FindingCard({ finding }: { finding: ArtistPageFinding }) {
  const color = findingColor(finding.severity);
  return (
    <div className={`nb-card ${styles.finding}`}>
      <span className="nb-pill" style={{ background: color, color: "#fff" }}>
        {(finding.severity ?? finding.category ?? "—").toUpperCase()}
      </span>
      <p className={styles.findingMsg}>{finding.message}</p>
      {finding.action && <p className={styles.findingAction}>→ {finding.action}</p>}
    </div>
  );
}

function NotBuiltYet({ slug, t }: { slug: string; t: (typeof T)["tr"] }) {
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
        `artist_notify_${slug}`,
        { slug }
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

export default function ArtistSeoPage() {
  const params = useParams<{ slug: string }>();
  const slug = params?.slug ?? "";
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [page, setPage] = useState<ArtistPage | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!slug) {
      setLoading(false);
      return;
    }
    let alive = true;
    (async () => {
      const result = await getArtistPage(slug);
      if (alive) {
        setPage(result);
        setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [slug]);

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
          <NotBuiltYet slug={slug} t={t} />
        </main>
      </div>
    );
  }

  const score = Math.max(0, Math.min(100, Math.round(page.score ?? 0)));
  // DIKKAT: backend alani `findings_json` adiyla doner (parse edilmis liste
  // olsa da anahtar adi degismez — bkz. api.ts ArtistPage yorumu).
  const findings = page.findings_json ?? [];
  const firstFindings = findings.slice(0, 3);
  const remainingFindings = findings.slice(3);
  const gaugeColor = score >= 70 ? "var(--green)" : score >= 40 ? "#ffb020" : "var(--red)";

  // Schema.org — minimal + valid, sadece elimizdeki gercek alanlardan turetilir
  // (window/URL gibi ortama bagli deger yok -> server/client hydration farki
  // olmaz).
  const schema = {
    "@context": "https://schema.org",
    "@type": "MusicGroup",
    name: page.artist_name,
    aggregateRating: {
      "@type": "AggregateRating",
      ratingValue: Math.round((score / 20) * 10) / 10,
      bestRating: 5,
      ratingCount: page.platform_count || 1,
    },
  };

  return (
    <div className={styles.page}>
      <SiteHeader />
      <script
        type="application/ld+json"
        // Guvenli: JSON.stringify ile bu bilesenin kendi ureti verisi; kullanici
        // girdisi yok.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
      />
      <main className={styles.body}>
        <div className={styles.head}>
          <div
            className={styles.gauge}
            style={{
              background: `conic-gradient(${gaugeColor} 0 ${score}%, #e6e6e0 ${score}% 100%)`,
            }}
          >
            <div className={styles.gaugeInner}>
              <div>
                <div className={styles.gaugeScore} style={{ color: gaugeColor }}>
                  {score}
                </div>
                <div className={styles.gaugeOf}>{t.scoreOf}</div>
              </div>
            </div>
          </div>
          <div className={styles.headMeta}>
            <span className="nb-pill nb-pill--blue">
              {t.platforms(page.platform_count ?? 0)}
            </span>
            <h1 className={`nb-h ${styles.artistName}`}>{page.artist_name}</h1>
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

        {firstFindings.length > 0 && (
          <>
            <h3 className={styles.sectionTitle}>{t.findingsTitle}</h3>
            <div className={styles.findingGrid}>
              {firstFindings.map((finding, index) => (
                <FindingCard key={index} finding={finding} />
              ))}
            </div>
          </>
        )}

        {remainingFindings.length > 0 && (
          <>
            <p className={styles.gateHeadline}>{t.gateHeadline(score)}</p>
            <EmailGate
              source={`artist_${slug}`}
              teaser={
                <>
                  <h3 className={styles.sectionTitle}>{t.remainingFindings}</h3>
                  <div className={styles.findingGrid}>
                    {remainingFindings.map((finding, index) => (
                      <FindingCard key={index} finding={finding} />
                    ))}
                  </div>
                </>
              }
            >
              <h3 className={styles.sectionTitle}>{t.remainingFindings}</h3>
              <div className={styles.findingGrid}>
                {remainingFindings.map((finding, index) => (
                  <FindingCard key={index} finding={finding} />
                ))}
              </div>
            </EmailGate>
          </>
        )}

        <div className={`nb-card ${styles.claimCard}`}>
          <div className={styles.claimTitle}>{t.claimTitle}</div>
          <Link href="/giris" className="nb-btn nb-btn--purple">
            {t.claimCta}
          </Link>
        </div>
      </main>
    </div>
  );
}
