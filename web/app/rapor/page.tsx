"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  createFeedbackDigest,
  getMe,
  getToken,
  latestFeedbackDigest,
  type FeedbackDigest,
  type User,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

/** Fırsat türü kodları -> gösterim etiketi (backend PRIMARY_KINDS/SECONDARY_KINDS
 *  ile aynı degerler; bkz. curator/inbox/page.tsx OPPORTUNITY_VALUES). */
const OPPORTUNITY_LABELS: { tr: Record<string, string>; en: Record<string, string> } = {
  tr: {
    playlist_ekleme: "Playlist'e Ekleme",
    radyo_calma: "Radyoda Çalma",
    haber_yazi: "Haber / Yazı",
    label_degerlendirme: "Label Değerlendirmesi",
    menajerlik_gorusme: "Menajerlik Görüşmesi",
    booking_teklif: "Booking Teklifi",
    dj_set: "DJ Set",
    mentorluk_seansi: "Mentorluk Seansı",
    sync_degerlendirme: "Sync Değerlendirmesi",
    sosyal_paylasim: "Sosyal Paylaşım",
    tavsiye: "Tavsiye",
    iletisimde_kal: "İletişimde Kalma",
  },
  en: {
    playlist_ekleme: "Playlist Add",
    radyo_calma: "Radio Play",
    haber_yazi: "News / Article",
    label_degerlendirme: "Label Review",
    menajerlik_gorusme: "Management Chat",
    booking_teklif: "Booking Offer",
    dj_set: "DJ Set",
    mentorluk_seansi: "Mentorship Session",
    sync_degerlendirme: "Sync Review",
    sosyal_paylasim: "Social Share",
    tavsiye: "Recommendation",
    iletisimde_kal: "Stay in Touch",
  },
};

const T = {
  tr: {
    gateTitle: "Giriş gerekli",
    gateText: "Geri bildirim sentez raporunu görmek için sanatçı hesabınla giriş yap.",
    gateLink: "Giriş / Kayıt",
    creditsWord: "kredi",
    heading: "Geri Bildirim Sentez Raporu",
    promise:
      "Küratörlerden aldığın tüm geri bildirimleri tek akıllı rapora damıtır — 1 kredi (Pro ücretsiz), en az 2 geri bildirim gerekir.",
    generateBtn: "Rapor Oluştur",
    busy: "...",
    generateError:
      "Rapor oluşturulamadı — yeterli geri bildirimin yok (en az 2 gerekli) ya da kredin yetersiz.",
    loading: "Yükleniyor...",
    noReportYet: "Henüz oluşturulmuş bir rapor yok — yukarıdaki düğmeyle ilkini oluştur.",
    statTotal: "Toplam Yanıt",
    statAcceptance: "Kabul Oranı",
    oppTitle: "Fırsat Dağılımı",
    oppEmpty: "Henüz kayıtlı fırsat türü yok.",
    keywordsTitle: "Anahtar Kelimeler",
    keywordsEmpty: "Henüz belirgin bir anahtar kelime yok.",
    themesTitle: "Temalar ve Önerilen Aksiyonlar",
    themesEmpty: "Henüz tekrar eden bir tema tespit edilmedi.",
    themeMentions: (n: number) => `${n} geri bildirimde geçti`,
    actionLabel: "Önerilen aksiyon",
    createdAt: (d: string) => `Oluşturuldu: ${d}`,
    dateLocale: "tr-TR",
  },
  en: {
    gateTitle: "Login required",
    gateText: "Log in with your artist account to see the feedback synthesis report.",
    gateLink: "Login / Sign Up",
    creditsWord: "credits",
    heading: "Feedback Synthesis Report",
    promise:
      "Distills every piece of feedback you've gotten from curators into one smart report — 1 credit (free on Pro), requires at least 2 feedback items.",
    generateBtn: "Generate Report",
    busy: "...",
    generateError:
      "Couldn't generate the report — you may not have enough feedback (at least 2 required), or you're low on credits.",
    loading: "Loading...",
    noReportYet: "No report generated yet — create your first one with the button above.",
    statTotal: "Total Responses",
    statAcceptance: "Acceptance Rate",
    oppTitle: "Opportunity Breakdown",
    oppEmpty: "No opportunity types recorded yet.",
    keywordsTitle: "Keywords",
    keywordsEmpty: "No clear keywords yet.",
    themesTitle: "Themes & Suggested Actions",
    themesEmpty: "No recurring theme detected yet.",
    themeMentions: (n: number) => `mentioned in ${n} feedback items`,
    actionLabel: "Suggested action",
    createdAt: (d: string) => `Created: ${d}`,
    dateLocale: "en-US",
  },
} as const;

/** Geri bildirim sentez raporu — biriken kurator geri bildirimlerini tek
 *  akilli raporda ozetler: istatistikler + firsat dagilimi + kelime/tema. */
export default function RaporPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);
  const oppLabels = pick(OPPORTUNITY_LABELS, locale);

  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [digest, setDigest] = useState<FeedbackDigest | null>(null);

  const [genBusy, setGenBusy] = useState(false);
  const [genError, setGenError] = useState("");

  useEffect(() => {
    (async () => {
      if (getToken()) {
        const me = await getMe();
        if (me && me.user.role === "artist") {
          setUser(me.user);
          const latest = await latestFeedbackDigest();
          if (latest) setDigest(latest);
        }
      }
      setChecked(true);
      setLoading(false);
    })();
  }, []);

  async function handleGenerate() {
    setGenError("");
    setGenBusy(true);
    const result = await createFeedbackDigest();
    setGenBusy(false);
    if (!result) {
      setGenError(t.generateError);
      return;
    }
    setDigest(result);
    const me = await getMe();
    if (me) setUser(me.user);
  }

  if (checked && !user) {
    return (
      <div className={styles.gate}>
        <div className="nb-card" style={{ padding: 28, maxWidth: 460 }}>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
            <LangToggle />
          </div>
          <h2 className="nb-h">{t.gateTitle}</h2>
          <p className={styles.gateText}>{t.gateText}</p>
          <Link href="/giris" className="nb-btn">{t.gateLink}</Link>
        </div>
      </div>
    );
  }

  const maxOpportunity = digest
    ? Math.max(1, ...Object.values(digest.opportunity_breakdown))
    : 1;
  const opportunityEntries = digest
    ? Object.entries(digest.opportunity_breakdown).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" className={styles.logo}>MuzikSEO</Link>
          <LangToggle />
        </div>
        {user && (
          <div className={styles.wallet}>💳 {user.credits} {t.creditsWord} · {user.name}</div>
        )}
      </div>

      <h1 className="nb-h">{t.heading}</h1>
      <p className={styles.promise}>{t.promise}</p>

      <div>
        <button
          type="button"
          className="nb-btn nb-btn--purple"
          disabled={genBusy}
          onClick={handleGenerate}
        >
          {genBusy ? t.busy : t.generateBtn}
        </button>
      </div>

      {genError && <div className={styles.error}>{genError}</div>}

      {loading && <div className={styles.empty}>{t.loading}</div>}

      {!loading && !digest && !genError && (
        <div className={styles.empty}>{t.noReportYet}</div>
      )}

      {digest && (
        <>
          <div className={styles.statGrid}>
            <div className={`nb-card ${styles.statCard}`}>
              <div className={styles.statValue}>{digest.stats.total_feedback}</div>
              <div className={styles.statLabel}>{t.statTotal}</div>
            </div>
            <div className={`nb-card ${styles.statCard}`}>
              <div className={styles.statValue}>%{digest.stats.acceptance_rate}</div>
              <div className={styles.statLabel}>{t.statAcceptance}</div>
            </div>
          </div>

          <h2 className="nb-h" style={{ fontSize: 18, marginTop: 8 }}>{t.oppTitle}</h2>
          {opportunityEntries.length === 0 ? (
            <div className={styles.empty}>{t.oppEmpty}</div>
          ) : (
            <div className={`nb-card ${styles.oppCard}`}>
              {opportunityEntries.map(([kind, count]) => (
                <div key={kind} className={styles.oppRow}>
                  <div className={styles.oppLabel}>{oppLabels[kind] ?? kind}</div>
                  <div className={styles.oppTrack}>
                    <div
                      className={styles.oppFill}
                      style={{ width: `${(count / maxOpportunity) * 100}%` }}
                    />
                  </div>
                  <div className={styles.oppCount}>{count}</div>
                </div>
              ))}
            </div>
          )}

          <h2 className="nb-h" style={{ fontSize: 18, marginTop: 8 }}>{t.keywordsTitle}</h2>
          {digest.top_keywords.length === 0 ? (
            <div className={styles.empty}>{t.keywordsEmpty}</div>
          ) : (
            <div className={styles.chipRow}>
              {digest.top_keywords.map((kw) => (
                <span key={kw.keyword} className="nb-chip">
                  {kw.keyword} <b>({kw.count})</b>
                </span>
              ))}
            </div>
          )}

          <h2 className="nb-h" style={{ fontSize: 18, marginTop: 8 }}>{t.themesTitle}</h2>
          {digest.themes.length === 0 ? (
            <div className={styles.empty}>{t.themesEmpty}</div>
          ) : (
            <div className={styles.themeList}>
              {digest.themes.map((theme) => (
                <div key={theme.keyword} className={`nb-card ${styles.themeCard}`}>
                  <div className={styles.themeHead}>
                    <span className={styles.themeKeyword}>{theme.keyword}</span>
                    <span className={styles.themeMentions}>
                      {t.themeMentions(theme.mentions)}
                    </span>
                  </div>
                  <div className={styles.themeAction}>
                    <span className={styles.themeActionLabel}>{t.actionLabel}:</span>{" "}
                    {theme.action}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className={styles.createdAt}>
            {t.createdAt(new Date(digest.created_at).toLocaleString(t.dateLocale))}
          </div>
        </>
      )}
    </div>
  );
}
