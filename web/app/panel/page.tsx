"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getDashboard,
  getMe,
  getReferral,
  getToken,
  markNotificationsRead,
  openEpk,
  type Dashboard,
  type User,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type FunnelKey = "total" | "pending" | "accepted" | "rejected" | "expired" | "verified_placements";

const FUNNEL_KEYS: FunnelKey[] = [
  "total",
  "pending",
  "accepted",
  "rejected",
  "expired",
  "verified_placements",
];

const T = {
  tr: {
    loginRequired: "Giriş gerekli",
    loginRequiredText: "Kariyer panonu görmek için sanatçı hesabınla giriş yap.",
    loginCta: "Giriş / Kayıt",
    creditsWord: "kredi",
    title: "A&R Kariyer Panosu",
    promise: "Gönderim huninden skor trendlerine kadar kariyerinin tüm verisi burada.",
    loading: "Yükleniyor...",
    funnel: {
      total: "Toplam Gönderim",
      pending: "Bekleyen",
      accepted: "Kabul",
      rejected: "Red",
      expired: "Süresi Dolmuş",
      verified_placements: "Doğrulanmış Yerleşim",
    } as Record<FunnelKey, string>,
    creditsSpent: "Harcanan kredi",
    notifications: "Bildirimler",
    markAllRead: "Tümünü Okundu İşaretle",
    tracksTitle: "Parçalarım",
    noTracks: "Henüz izlenen parça yok — gönderim yaptığında burada görünür.",
    scoreLabel: "Skor:",
    trendEmpty: "Trend için yeterli veri yok",
    cohortTitle: "Kohort Kıyaslaması",
    cohortLockedTitle: "🔒 Kohort kıyaslaması Artist Pro'ya özel",
    cohortLockedText: "Aynı havuzdaki diğer sanatçıların ortalama skoruyla kendini kıyasla.",
    seeProCta: "Artist Pro'yu Gör",
    yourAvg: "Senin Ortalaman",
    cohortAvg: "Kohort Ortalaması",
    cohortArtists: (n: number) => `${n} sanatçı`,
    referralTitle: "🎁 Referans Kodun",
    copied: "✓ Kopyalandı",
    copyInvite: "Davet Linkini Kopyala",
    epkTitle: "📄 EPK Oluştur",
    epkNotePro: "Artist Pro'da ücretsiz.",
    epkNoteFree: "Pro'ya ücretsiz — değilse 2 kredi düşer.",
    epkError: "EPK oluşturulamadı — kredin yetersiz olabilir, tekrar dene.",
    epkCta: "EPK Oluştur",
    busy: "...",
  },
  en: {
    loginRequired: "Login required",
    loginRequiredText: "Log in with your artist account to see your career dashboard.",
    loginCta: "Log In / Sign Up",
    creditsWord: "credits",
    title: "A&R Career Dashboard",
    promise: "Everything about your career, from the submission funnel to score trends.",
    loading: "Loading...",
    funnel: {
      total: "Total Submissions",
      pending: "Pending",
      accepted: "Accepted",
      rejected: "Rejected",
      expired: "Expired",
      verified_placements: "Verified Placements",
    } as Record<FunnelKey, string>,
    creditsSpent: "Credits spent",
    notifications: "Notifications",
    markAllRead: "Mark All as Read",
    tracksTitle: "My Tracks",
    noTracks: "No tracked songs yet — they'll show up here once you submit.",
    scoreLabel: "Score:",
    trendEmpty: "Not enough data for a trend",
    cohortTitle: "Cohort Comparison",
    cohortLockedTitle: "🔒 Cohort comparison is Artist Pro only",
    cohortLockedText: "Compare yourself to the average score of other artists in the same pool.",
    seeProCta: "See Artist Pro",
    yourAvg: "Your Average",
    cohortAvg: "Cohort Average",
    cohortArtists: (n: number) => `${n} artists`,
    referralTitle: "🎁 Your Referral Code",
    copied: "✓ Copied",
    copyInvite: "Copy Invite Link",
    epkTitle: "📄 Create EPK",
    epkNotePro: "Free on Artist Pro.",
    epkNoteFree: "Free on Pro — otherwise costs 2 credits.",
    epkError: "Couldn't create EPK — you may be low on credits, try again.",
    epkCta: "Create EPK",
    busy: "...",
  },
} as const;

/** Parca trendinden kucuk bir SVG polyline uretir (viewBox 0 0 200 60). */
function buildSparkline(trend: { score: number | null }[]): string | null {
  const values = trend.map((t) => t.score).filter((v): v is number => v !== null);
  if (values.length < 2) return null;
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const spread = maxVal - minVal || 1;
  const xLeft = 4;
  const xRight = 196;
  const yTop = 6;
  const yBottom = 54;
  return values
    .map((v, i) => {
      const x = xLeft + (i / (values.length - 1)) * (xRight - xLeft);
      const y = yBottom - ((v - minVal) / spread) * (yBottom - yTop);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function trackAverage(tracks: Dashboard["tracks"]): number | null {
  const scored = tracks.map((t) => t.latest_score).filter((v): v is number => v !== null);
  if (scored.length === 0) return null;
  return Math.round((scored.reduce((a, b) => a + b, 0) / scored.length) * 10) / 10;
}

/** A&R Kariyer Panosu — sanatcinin tum gonderim performansini tek ekranda gosterir:
 *  huni + skor trendleri + kohort kiyaslamasi (pro) + referans + EPK. */
export default function PanelPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);

  const [referral, setReferral] = useState<{ code: string; bonus_credits: number; note: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const [epkBusy, setEpkBusy] = useState(false);
  const [epkError, setEpkError] = useState("");

  const [notifBusy, setNotifBusy] = useState(false);

  useEffect(() => {
    (async () => {
      if (getToken()) {
        const me = await getMe();
        if (me && me.user.role === "artist") {
          setUser(me.user);
          const [dash, ref] = await Promise.all([getDashboard(), getReferral()]);
          if (dash) setDashboard(dash);
          if (ref) setReferral(ref);
        }
      }
      setChecked(true);
      setLoading(false);
    })();
  }, []);

  async function handleCopyInvite() {
    if (!referral) return;
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const link = `${origin}/giris?ref=${referral.code}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  async function handleEpk() {
    setEpkBusy(true);
    setEpkError("");
    const url = await openEpk();
    setEpkBusy(false);
    if (url) {
      window.open(url, "_blank");
    } else {
      setEpkError(t.epkError);
    }
  }

  async function handleMarkRead() {
    setNotifBusy(true);
    const result = await markNotificationsRead();
    setNotifBusy(false);
    if (result) {
      setDashboard((prev) => (prev ? { ...prev, notifications: [] } : prev));
    }
  }

  if (checked && !user) {
    return (
      <div className={styles.gate}>
        <div className="nb-card" style={{ padding: 28, maxWidth: 460 }}>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <LangToggle />
          </div>
          <h2 className="nb-h">{t.loginRequired}</h2>
          <p className={styles.gateText}>{t.loginRequiredText}</p>
          <Link href="/giris" className="nb-btn">{t.loginCta}</Link>
        </div>
      </div>
    );
  }

  const avgScore = dashboard ? trackAverage(dashboard.tracks) : null;

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <Link href="/" className={styles.logo}>MuzikSEO</Link>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {user && (
            <div className={styles.wallet}>💳 {user.credits} {t.creditsWord} · {user.name}</div>
          )}
          <LangToggle />
        </div>
      </div>

      <h1 className="nb-h">{t.title}</h1>
      <p className={styles.promise}>{t.promise}</p>

      {loading && <div className={styles.empty}>{t.loading}</div>}

      {!loading && dashboard && (
        <>
          <div className={styles.funnelGrid}>
            {FUNNEL_KEYS.map((key) => (
              <div key={key} className={`nb-card ${styles.funnelCard}`}>
                <div className={styles.funnelValue}>{dashboard.funnel[key] ?? 0}</div>
                <div className={styles.funnelLabel}>{t.funnel[key]}</div>
              </div>
            ))}
          </div>

          <div className={`nb-card ${styles.creditsCard}`}>
            <span>{t.creditsSpent}</span>
            <b>{dashboard.credits_spent}</b>
          </div>

          {dashboard.notifications.length > 0 && (
            <div className={styles.notifSection}>
              <div className={styles.sectionHead}>
                <h2 className="nb-h" style={{ fontSize: 18 }}>{t.notifications}</h2>
                <button
                  type="button"
                  className="nb-btn nb-btn--outline"
                  style={{ fontSize: 12, padding: "8px 14px" }}
                  onClick={handleMarkRead}
                  disabled={notifBusy}
                >
                  {notifBusy ? t.busy : t.markAllRead}
                </button>
              </div>
              <div className={styles.notifList}>
                {dashboard.notifications.map((n) => (
                  <div
                    key={n.id}
                    className={
                      n.kind === "score_drop"
                        ? `${styles.notif} ${styles.notifWarn}`
                        : styles.notif
                    }
                  >
                    {n.message}
                  </div>
                ))}
              </div>
            </div>
          )}

          <h2 className="nb-h" style={{ fontSize: 18, marginTop: 8 }}>{t.tracksTitle}</h2>
          <div className={styles.trackList}>
            {dashboard.tracks.length === 0 && (
              <div className={styles.empty}>{t.noTracks}</div>
            )}
            {dashboard.tracks.map((tr, i) => {
              const points = buildSparkline(tr.trend);
              return (
                <div key={`${tr.artist}-${tr.title}-${i}`} className={`nb-card ${styles.trackCard}`}>
                  <div className={styles.trackInfo}>
                    <div className={styles.trackTitle}>{tr.artist} — {tr.title}</div>
                    <div className={styles.trackScore}>
                      {t.scoreLabel} <b>{tr.latest_score ?? "—"}</b>
                    </div>
                  </div>
                  <div className={styles.sparkWrap}>
                    {points ? (
                      <svg viewBox="0 0 200 60" preserveAspectRatio="none">
                        <polyline
                          points={points}
                          fill="none"
                          stroke="#000"
                          strokeWidth="4"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    ) : (
                      <span className={styles.sparkEmpty}>{t.trendEmpty}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <h2 className="nb-h" style={{ fontSize: 18, marginTop: 8 }}>{t.cohortTitle}</h2>
          {dashboard.cohort === null ? (
            <div className={`nb-card ${styles.lockedCard}`}>
              <div className={styles.lockedTitle}>{t.cohortLockedTitle}</div>
              <p className={styles.lockedText}>{t.cohortLockedText}</p>
              <Link href="/pro" className="nb-btn nb-btn--purple">{t.seeProCta}</Link>
            </div>
          ) : (
            <div className={`nb-card ${styles.cohortCard}`}>
              <div className={styles.cohortBox}>
                <div className={styles.cohortLabel}>{t.yourAvg}</div>
                <div className={styles.cohortValue}>{avgScore ?? "—"}</div>
              </div>
              <div className={styles.cohortSep}>vs</div>
              <div className={styles.cohortBox}>
                <div className={styles.cohortLabel}>{t.cohortAvg}</div>
                <div className={styles.cohortValue}>{dashboard.cohort.avg_score ?? "—"}</div>
                <div className={styles.cohortSub}>{t.cohortArtists(dashboard.cohort.artists)}</div>
              </div>
            </div>
          )}

          {referral && (
            <div className={`nb-card ${styles.referralCard}`}>
              <div className={styles.referralHead}>{t.referralTitle}</div>
              <p className={styles.referralNote}>{referral.note}</p>
              <div className={styles.referralRow}>
                <code className={styles.referralCode}>{referral.code}</code>
                <button type="button" className="nb-btn" onClick={handleCopyInvite}>
                  {copied ? t.copied : t.copyInvite}
                </button>
              </div>
            </div>
          )}

          <div className={`nb-card ${styles.epkCard}`}>
            <div>
              <div className={styles.epkTitle}>{t.epkTitle}</div>
              <p className={styles.epkNote}>
                {dashboard.pro ? t.epkNotePro : t.epkNoteFree}
              </p>
              {epkError && <div className={styles.error}>{epkError}</div>}
            </div>
            <button type="button" className="nb-btn nb-btn--purple" onClick={handleEpk} disabled={epkBusy}>
              {epkBusy ? t.busy : t.epkCta}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
