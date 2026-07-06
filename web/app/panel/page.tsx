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
import styles from "./page.module.css";

type FunnelKey = "total" | "pending" | "accepted" | "rejected" | "expired" | "verified_placements";

const FUNNEL_CARDS: { key: FunnelKey; label: string }[] = [
  { key: "total", label: "Toplam Gönderim" },
  { key: "pending", label: "Bekleyen" },
  { key: "accepted", label: "Kabul" },
  { key: "rejected", label: "Red" },
  { key: "expired", label: "Süresi Dolmuş" },
  { key: "verified_placements", label: "Doğrulanmış Yerleşim" },
];

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
      setEpkError("EPK oluşturulamadı — kredin yetersiz olabilir, tekrar dene.");
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
          <h2 className="nb-h">Giriş gerekli</h2>
          <p className={styles.gateText}>
            Kariyer panonu görmek için sanatçı hesabınla giriş yap.
          </p>
          <Link href="/giris" className="nb-btn">Giriş / Kayıt</Link>
        </div>
      </div>
    );
  }

  const avgScore = dashboard ? trackAverage(dashboard.tracks) : null;

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <Link href="/" className={styles.logo}>MuzikSEO</Link>
        {user && (
          <div className={styles.wallet}>💳 {user.credits} kredi · {user.name}</div>
        )}
      </div>

      <h1 className="nb-h">A&amp;R Kariyer Panosu</h1>
      <p className={styles.promise}>
        Gönderim huninden skor trendlerine kadar kariyerinin tüm verisi burada.
      </p>

      {loading && <div className={styles.empty}>Yükleniyor...</div>}

      {!loading && dashboard && (
        <>
          <div className={styles.funnelGrid}>
            {FUNNEL_CARDS.map((f) => (
              <div key={f.key} className={`nb-card ${styles.funnelCard}`}>
                <div className={styles.funnelValue}>{dashboard.funnel[f.key] ?? 0}</div>
                <div className={styles.funnelLabel}>{f.label}</div>
              </div>
            ))}
          </div>

          <div className={`nb-card ${styles.creditsCard}`}>
            <span>Harcanan kredi</span>
            <b>{dashboard.credits_spent}</b>
          </div>

          {dashboard.notifications.length > 0 && (
            <div className={styles.notifSection}>
              <div className={styles.sectionHead}>
                <h2 className="nb-h" style={{ fontSize: 18 }}>Bildirimler</h2>
                <button
                  type="button"
                  className="nb-btn nb-btn--outline"
                  style={{ fontSize: 12, padding: "8px 14px" }}
                  onClick={handleMarkRead}
                  disabled={notifBusy}
                >
                  {notifBusy ? "..." : "Tümünü Okundu İşaretle"}
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

          <h2 className="nb-h" style={{ fontSize: 18, marginTop: 8 }}>Parçalarım</h2>
          <div className={styles.trackList}>
            {dashboard.tracks.length === 0 && (
              <div className={styles.empty}>
                Henüz izlenen parça yok — gönderim yaptığında burada görünür.
              </div>
            )}
            {dashboard.tracks.map((t, i) => {
              const points = buildSparkline(t.trend);
              return (
                <div key={`${t.artist}-${t.title}-${i}`} className={`nb-card ${styles.trackCard}`}>
                  <div className={styles.trackInfo}>
                    <div className={styles.trackTitle}>{t.artist} — {t.title}</div>
                    <div className={styles.trackScore}>
                      Skor: <b>{t.latest_score ?? "—"}</b>
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
                      <span className={styles.sparkEmpty}>Trend için yeterli veri yok</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <h2 className="nb-h" style={{ fontSize: 18, marginTop: 8 }}>Kohort Kıyaslaması</h2>
          {dashboard.cohort === null ? (
            <div className={`nb-card ${styles.lockedCard}`}>
              <div className={styles.lockedTitle}>🔒 Kohort kıyaslaması Artist Pro&apos;ya özel</div>
              <p className={styles.lockedText}>
                Aynı havuzdaki diğer sanatçıların ortalama skoruyla kendini kıyasla.
              </p>
              <Link href="/pro" className="nb-btn nb-btn--purple">Artist Pro&apos;yu Gör</Link>
            </div>
          ) : (
            <div className={`nb-card ${styles.cohortCard}`}>
              <div className={styles.cohortBox}>
                <div className={styles.cohortLabel}>Senin Ortalaman</div>
                <div className={styles.cohortValue}>{avgScore ?? "—"}</div>
              </div>
              <div className={styles.cohortSep}>vs</div>
              <div className={styles.cohortBox}>
                <div className={styles.cohortLabel}>Kohort Ortalaması</div>
                <div className={styles.cohortValue}>{dashboard.cohort.avg_score ?? "—"}</div>
                <div className={styles.cohortSub}>{dashboard.cohort.artists} sanatçı</div>
              </div>
            </div>
          )}

          {referral && (
            <div className={`nb-card ${styles.referralCard}`}>
              <div className={styles.referralHead}>🎁 Referans Kodun</div>
              <p className={styles.referralNote}>{referral.note}</p>
              <div className={styles.referralRow}>
                <code className={styles.referralCode}>{referral.code}</code>
                <button type="button" className="nb-btn" onClick={handleCopyInvite}>
                  {copied ? "✓ Kopyalandı" : "Davet Linkini Kopyala"}
                </button>
              </div>
            </div>
          )}

          <div className={`nb-card ${styles.epkCard}`}>
            <div>
              <div className={styles.epkTitle}>📄 EPK Oluştur</div>
              <p className={styles.epkNote}>
                {dashboard.pro
                  ? "Artist Pro'da ücretsiz."
                  : "Pro'ya ücretsiz — değilse 2 kredi düşer."}
              </p>
              {epkError && <div className={styles.error}>{epkError}</div>}
            </div>
            <button type="button" className="nb-btn nb-btn--purple" onClick={handleEpk} disabled={epkBusy}>
              {epkBusy ? "..." : "EPK Oluştur"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
