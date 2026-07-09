"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getImpact,
  getMe,
  getToken,
  mySubmissions,
  openCertificate,
  openShareCard,
  verifyPlacementSelf,
  type ImpactReport,
  type Submission,
  type User,
} from "@/lib/api";
import { LangToggle, pick, useLocale } from "@/lib/locale";
import styles from "./page.module.css";

const T = {
  tr: {
    impactLoading: "Yükleniyor...",
    impactError: "Etki raporu yüklenemedi — tekrar dene.",
    before: "Önce",
    after: "Sonra",
    unverifiedNote: "Yerleşim henüz doğrulanmadı — rapor ön veriyle gösteriliyor.",
    statusAccepted: "Kabul edildi",
    statusRejected: "Reddedildi (geri bildirim geldi)",
    statusExpired: "Süre doldu — kredi iade edildi",
    statusPending: "Bekliyor (72 saat SLA)",
    gateTitle: "Giriş gerekli",
    gateText: "Kampanya geçmişin için sanatçı hesabınla giriş yap.",
    loginBtn: "Giriş / Kayıt",
    walletCredits: (n: number, name: string) => `💳 ${n} kredi · ${name}`,
    pageTitle: "Kampanya Geçmişi",
    newSubmission: "+ Yeni Gönderim",
    loading: "Yükleniyor...",
    emptyBefore: "Henüz gönderim yok — ",
    emptyLink: "ilk şarkını gönder",
    submissionMeta: (id: number, date: string) => `Gönderim #${id} · ${date}`,
    creditsPill: (n: number) => `${n} kredi`,
    guaranteed: "Garantili (2x iade)",
    priority: "Öne çıkan",
    readyToPublish: "Yayına Hazır",
    curatorFeedback: "Küratör geri bildirimi",
    verifyPlacement: "Yerleşimi Doğrula",
    checking: "Kontrol ediliyor...",
    verifySuccess: "🎉 Doğrulandı! Şarkın playlistte yerini aldı.",
    verifyPending: "Henüz playlistte görünmüyor — kürator eklemesi 1-2 gün sürebilir.",
    verifyFail: "Doğrulama başarısız — tekrar dene.",
    placementVerified: "✅ Playlist yerleşimi doğrulandı",
    certificate: "Sertifika",
    preparing: "Hazırlanıyor...",
    proofCard: "Kanıt Kartı (Story)",
    impactReport: "Etki Raporu",
    closeImpactReport: "Etki Raporunu Kapat",
    firstGenHint: "İlk üretim 1 kredi düşer",
    certFail: "Sertifika açılamadı — tekrar dene.",
    shareFail: "Kanıt kartı açılamadı — tekrar dene.",
    dateLocale: "tr-TR",
  },
  en: {
    impactLoading: "Loading...",
    impactError: "Couldn't load the impact report — try again.",
    before: "Before",
    after: "After",
    unverifiedNote: "Placement not verified yet — report shown with preliminary data.",
    statusAccepted: "Accepted",
    statusRejected: "Rejected (feedback available)",
    statusExpired: "Expired — credit refunded",
    statusPending: "Pending (72h SLA)",
    gateTitle: "Login required",
    gateText: "Log in with your artist account to see your campaign history.",
    loginBtn: "Log in / Sign up",
    walletCredits: (n: number, name: string) => `💳 ${n} credits · ${name}`,
    pageTitle: "Campaign History",
    newSubmission: "+ New Submission",
    loading: "Loading...",
    emptyBefore: "No submissions yet — ",
    emptyLink: "submit your first song",
    submissionMeta: (id: number, date: string) => `Submission #${id} · ${date}`,
    creditsPill: (n: number) => `${n} credits`,
    guaranteed: "Guaranteed (2x refund)",
    priority: "Priority",
    readyToPublish: "Release Ready",
    curatorFeedback: "Curator feedback",
    verifyPlacement: "Verify Placement",
    checking: "Checking...",
    verifySuccess: "🎉 Verified! Your song landed on the playlist.",
    verifyPending: "Not showing on the playlist yet — curator additions can take 1-2 days.",
    verifyFail: "Verification failed — try again.",
    placementVerified: "✅ Playlist placement verified",
    certificate: "Certificate",
    preparing: "Preparing...",
    proofCard: "Proof Card (Story)",
    impactReport: "Impact Report",
    closeImpactReport: "Close Impact Report",
    firstGenHint: "First generation costs 1 credit",
    certFail: "Couldn't open the certificate — try again.",
    shareFail: "Couldn't open the proof card — try again.",
    dateLocale: "en-US",
  },
} as const;

/** Etki raporu paneli: once/sonra skor + delta (pozitifse yesil). */
function ImpactPanel({ data }: { data: ImpactReport | null | undefined }) {
  const { locale } = useLocale();
  const t = pick(T, locale);

  if (data === undefined) return <div className={styles.impactMsg}>{t.impactLoading}</div>;
  if (data === null) return <div className={styles.impactMsg}>{t.impactError}</div>;

  const delta = data.score_delta;
  const deltaCls =
    delta !== null && delta > 0 ? styles.deltaUp : delta !== null && delta < 0 ? styles.deltaDown : "";

  return (
    <div className={styles.impactPanel}>
      <div className={styles.impactGrid}>
        <div className={styles.impactBox}>
          <div className={styles.impactLabel}>{t.before}</div>
          <div className={styles.impactScore}>{data.before.score ?? "—"}</div>
        </div>
        <div className={styles.impactArrow}>→</div>
        <div className={styles.impactBox}>
          <div className={styles.impactLabel}>{t.after}</div>
          <div className={styles.impactScore}>{data.after.score ?? "—"}</div>
        </div>
        {delta !== null && (
          <div className={`${styles.impactDelta} ${deltaCls}`}>
            {delta > 0 ? "+" : ""}
            {delta}
          </div>
        )}
      </div>
      {!data.placement_verified && (
        <div className={styles.impactMsg}>{t.unverifiedNote}</div>
      )}
    </div>
  );
}

const READINESS_READY_MIN = 70;

/** Sanatci kampanya gecmisi: gonderim durumu + kurator geri bildirimi + SLA. */
export default function KampanyalarPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [subs, setSubs] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);

  // Yerlesim self-servis dogrulama
  const [verifyBusyId, setVerifyBusyId] = useState<number | null>(null);
  const [verifyMsgs, setVerifyMsgs] = useState<Record<number, string>>({});

  // Sertifika / kanit karti / etki raporu
  const [certBusyId, setCertBusyId] = useState<number | null>(null);
  const [shareBusyId, setShareBusyId] = useState<number | null>(null);
  const [certMsgs, setCertMsgs] = useState<Record<number, string>>({});
  const [expandedImpactId, setExpandedImpactId] = useState<number | null>(null);
  const [impactData, setImpactData] = useState<Record<number, ImpactReport | null | undefined>>({});

  function updateSub(id: number, patch: Partial<Submission>) {
    setSubs((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  async function handleVerify(id: number) {
    setVerifyBusyId(id);
    setVerifyMsgs((prev) => ({ ...prev, [id]: "" }));
    const updated = await verifyPlacementSelf(id);
    setVerifyBusyId(null);
    if (!updated) {
      setVerifyMsgs((prev) => ({ ...prev, [id]: t.verifyFail }));
      return;
    }
    updateSub(id, updated);
    setVerifyMsgs((prev) => ({
      ...prev,
      [id]: updated.placement_verified === 1 ? t.verifySuccess : t.verifyPending,
    }));
  }

  async function handleCertificate(id: number) {
    setCertBusyId(id);
    setCertMsgs((prev) => ({ ...prev, [id]: "" }));
    const url = await openCertificate(id);
    setCertBusyId(null);
    if (url) {
      window.open(url, "_blank");
    } else {
      setCertMsgs((prev) => ({ ...prev, [id]: t.certFail }));
    }
  }

  async function handleShareCard(id: number) {
    setShareBusyId(id);
    setCertMsgs((prev) => ({ ...prev, [id]: "" }));
    const url = await openShareCard(id);
    setShareBusyId(null);
    if (url) {
      window.open(url, "_blank");
    } else {
      setCertMsgs((prev) => ({ ...prev, [id]: t.shareFail }));
    }
  }

  async function handleImpact(id: number) {
    if (expandedImpactId === id) {
      setExpandedImpactId(null);
      return;
    }
    setExpandedImpactId(id);
    if (impactData[id] === undefined) {
      const data = await getImpact(id);
      setImpactData((prev) => ({ ...prev, [id]: data }));
    }
  }

  useEffect(() => {
    (async () => {
      if (getToken()) {
        const me = await getMe();
        if (me && me.user.role === "artist") {
          setUser(me.user);
          const list = await mySubmissions();
          if (list) setSubs(list.reverse()); // en yeni ustte
        }
      }
      setChecked(true);
      setLoading(false);
    })();
  }, []);

  function statusInfo(s: Submission): { label: string; cls: string } {
    if (s.status === "accepted") return { label: t.statusAccepted, cls: styles.ok };
    if (s.status === "rejected") return { label: t.statusRejected, cls: styles.warn };
    if (s.status === "expired") return { label: t.statusExpired, cls: styles.refund };
    return { label: t.statusPending, cls: styles.pending };
  }

  if (checked && !user) {
    return (
      <div className={styles.gate}>
        <div className="nb-card" style={{ padding: 28, maxWidth: 460 }}>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <LangToggle />
          </div>
          <h2 className="nb-h">{t.gateTitle}</h2>
          <p style={{ fontWeight: 600, margin: "12px 0 20px" }}>{t.gateText}</p>
          <Link href="/giris" className="nb-btn">{t.loginBtn}</Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <Link href="/" className={styles.logo}>Sozy Echo</Link>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {user && (
            <div className={styles.wallet}>{t.walletCredits(user.credits, user.name)}</div>
          )}
          <LangToggle />
        </div>
      </div>

      <h1 className="nb-h">{t.pageTitle}</h1>
      <div className={styles.subline}>
        <Link href="/gonder" className="nb-btn nb-btn--purple">{t.newSubmission}</Link>
      </div>

      {loading && <div className={styles.empty}>{t.loading}</div>}
      {!loading && subs.length === 0 && (
        <div className={styles.empty}>
          {t.emptyBefore}
          <Link href="/gonder">{t.emptyLink}</Link>.
        </div>
      )}

      {subs.map((s) => {
        const info = statusInfo(s);
        const readinessReady =
          typeof s.readiness_score === "number" && s.readiness_score >= READINESS_READY_MIN;

        return (
          <div key={s.id} className={`nb-card ${styles.subCard}`}>
            <div className={styles.subHead}>
              <div>
                <div className={styles.subTitle}>
                  {s.artist} — {s.title}
                </div>
                <div className={styles.subMeta}>
                  {t.submissionMeta(s.id, new Date(s.created_at).toLocaleString(t.dateLocale))}
                </div>
                <div className={styles.badgeRow}>
                  {typeof s.cost_credits === "number" && (
                    <span className="nb-pill nb-pill--blue">{t.creditsPill(s.cost_credits)}</span>
                  )}
                  {s.guaranteed === 1 && (
                    <span className="nb-pill nb-pill--green">{t.guaranteed}</span>
                  )}
                  {s.priority === 1 && (
                    <span className="nb-pill nb-pill--purple">{t.priority}</span>
                  )}
                  {readinessReady && (
                    <span className="nb-pill nb-pill--green">{t.readyToPublish}</span>
                  )}
                </div>
              </div>
              <span className={`${styles.pill} ${info.cls}`}>{info.label}</span>
            </div>

            {s.feedback && (
              <div className={styles.feedback}>
                <div className={styles.feedbackLabel}>{t.curatorFeedback}</div>
                {s.feedback}
              </div>
            )}

            {s.status === "accepted" && s.placement_verified === 0 && (
              <div className={styles.verifyBlock}>
                <button
                  type="button"
                  className="nb-btn nb-btn--outline"
                  disabled={verifyBusyId === s.id}
                  onClick={() => handleVerify(s.id)}
                >
                  {verifyBusyId === s.id ? t.checking : t.verifyPlacement}
                </button>
                {verifyMsgs[s.id] && (
                  <div
                    className={
                      verifyMsgs[s.id].startsWith("🎉") ? styles.verifyOk : styles.verifyInfo
                    }
                  >
                    {verifyMsgs[s.id]}
                  </div>
                )}
              </div>
            )}

            {s.placement_verified === 1 && (
              <>
                <div className={styles.placement}>{t.placementVerified}</div>
                <div className={styles.provenActions}>
                  <button
                    type="button"
                    className="nb-btn"
                    disabled={certBusyId === s.id}
                    onClick={() => handleCertificate(s.id)}
                  >
                    {certBusyId === s.id ? t.preparing : t.certificate}
                  </button>
                  <button
                    type="button"
                    className="nb-btn"
                    disabled={shareBusyId === s.id}
                    onClick={() => handleShareCard(s.id)}
                  >
                    {shareBusyId === s.id ? t.preparing : t.proofCard}
                  </button>
                  <button
                    type="button"
                    className="nb-btn nb-btn--purple"
                    onClick={() => handleImpact(s.id)}
                  >
                    {expandedImpactId === s.id ? t.closeImpactReport : t.impactReport}
                  </button>
                  {!s.certificate_token && (
                    <span className={styles.hint}>{t.firstGenHint}</span>
                  )}
                </div>
                {certMsgs[s.id] && <div className={styles.verifyInfo}>{certMsgs[s.id]}</div>}
                {expandedImpactId === s.id && <ImpactPanel data={impactData[s.id]} />}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
