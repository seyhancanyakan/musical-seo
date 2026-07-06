"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getMe,
  getPackages,
  getToken,
  requestPackage,
  type CreditPackage,
  type User,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

const CONTACT_EMAIL = "destek@muzikseo.com";

type RequestState = "idle" | "busy" | "requested" | "error";

const T = {
  tr: {
    creditsWord: "kredi",
    heroTitle: "Artist Pro",
    priceUnit: "/ay",
    tagline: "Kariyerini büyütmek için tüm premium araçlar tek pakette.",
    loading: "Yükleniyor...",
    benefitsTitle: "Avantajlar",
    benefits: [
      (monthly: number) => `Aylık ${monthly} kredi`,
      () => "Gönderimlerde 1 kredi indirim",
      (_: number, sla: number) => `${sla} saat SLA garantisi`,
      () => "Kohort kıyaslaması (kariyer panonda)",
      () => "EPK, sertifika, etki raporu ve otopilot ücretsiz",
    ] as ((monthly: number, sla: number) => string)[],
    contactCta: "Pro'ya Geçmek İçin Bize Yaz",
    mailSubject: "Artist Pro talebi",
    mailBody: (email?: string) =>
      `Merhaba,\n\nArtist Pro'ya geçmek istiyorum.${email ? `\n\nHesap: ${email}` : ""}`,
    manualPayNote:
      "Pilot döneminde ödeme manuel (havale/Papara) — bize yazınca 24 saat içinde aktif ederiz.",
    packagesTitle: "Kredi Paketleri",
    request: "Talep Et",
    requested: "✓ Talep Alındı",
    busy: "...",
    loginCta: "Giriş Yap",
    requestError: "Talep gönderilemedi — tekrar dene.",
    requestedNote: "Admin onayı bekleniyor — onaylanınca kredin yüklenir.",
  },
  en: {
    creditsWord: "credits",
    heroTitle: "Artist Pro",
    priceUnit: "/mo",
    tagline: "Every premium tool for growing your career, in one plan.",
    loading: "Loading...",
    benefitsTitle: "Benefits",
    benefits: [
      (monthly: number) => `${monthly} credits per month`,
      () => "1 credit discount on submissions",
      (_: number, sla: number) => `${sla}-hour SLA guarantee`,
      () => "Cohort comparison (in your dashboard)",
      () => "Free EPK, certificate, impact report, and autopilot",
    ] as ((monthly: number, sla: number) => string)[],
    contactCta: "Email Us to Go Pro",
    mailSubject: "Artist Pro request",
    mailBody: (email?: string) =>
      `Hi,\n\nI'd like to upgrade to Artist Pro.${email ? `\n\nAccount: ${email}` : ""}`,
    manualPayNote:
      "During the pilot, payment is handled manually (bank transfer/Papara) — we'll activate your account within 24 hours of hearing from you.",
    packagesTitle: "Credit Packages",
    request: "Request",
    requested: "✓ Request Received",
    busy: "...",
    loginCta: "Log In",
    requestError: "Couldn't send request — try again.",
    requestedNote: "Waiting on admin approval — your credits will land once approved.",
  },
} as const;

/** Artist Pro tanitim + kredi paketleri — pilot doneminde odeme manuel
 *  (havale/Papara), admin talebi onaylayip krediyi yukler. */
export default function ProPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [user, setUser] = useState<User | null>(null);
  const [packages, setPackages] = useState<CreditPackage[]>([]);
  const [pro, setPro] = useState<{ price_try: number; monthly_credits: number; sla_hours: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [requestStates, setRequestStates] = useState<Record<string, RequestState>>({});

  useEffect(() => {
    (async () => {
      const packagesData = await getPackages();
      if (packagesData) {
        setPackages(packagesData.packages);
        setPro(packagesData.pro);
      }
      if (getToken()) {
        const me = await getMe();
        if (me) setUser(me.user);
      }
      setLoading(false);
    })();
  }, []);

  async function handleRequest(key: string) {
    setRequestStates((prev) => ({ ...prev, [key]: "busy" }));
    const result = await requestPackage(key);
    setRequestStates((prev) => ({ ...prev, [key]: result ? "requested" : "error" }));
  }

  const mailSubject = encodeURIComponent(t.mailSubject);
  const mailBody = encodeURIComponent(t.mailBody(user?.email));

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

      <div className={styles.hero}>
        <h1 className="nb-h">{t.heroTitle}</h1>
        {pro && (
          <div className={styles.price}>
            {pro.price_try.toLocaleString("tr-TR")} TL<span className={styles.priceUnit}>{t.priceUnit}</span>
          </div>
        )}
        <p className={styles.tagline}>{t.tagline}</p>
      </div>

      {loading && <div className={styles.empty}>{t.loading}</div>}

      {!loading && pro && (
        <div className={`nb-card ${styles.benefitsCard}`}>
          <div className={styles.benefitsTitle}>{t.benefitsTitle}</div>
          <ul className={styles.benefitsList}>
            {t.benefits.map((render, i) => (
              <li key={i} className={styles.benefitItem}>
                ✓ {render(pro.monthly_credits, pro.sla_hours)}
              </li>
            ))}
          </ul>
          <a
            href={`mailto:${CONTACT_EMAIL}?subject=${mailSubject}&body=${mailBody}`}
            className="nb-btn nb-btn--purple"
          >
            {t.contactCta}
          </a>
          <p className={styles.note}>{t.manualPayNote}</p>
        </div>
      )}

      <h2 className="nb-h" style={{ fontSize: 18 }}>{t.packagesTitle}</h2>
      <div className={styles.packageGrid}>
        {packages.map((p) => {
          const state = requestStates[p.key] ?? "idle";
          return (
            <div key={p.key} className={`nb-card ${styles.packageCard}`}>
              <div className={styles.packageLabel}>{p.label}</div>
              <div className={styles.packageCredits}>{p.credits} {t.creditsWord}</div>
              <div className={styles.packagePrice}>
                {p.price_try.toLocaleString("tr-TR")} TL
              </div>
              {user ? (
                <button
                  type="button"
                  className="nb-btn"
                  disabled={state === "busy" || state === "requested"}
                  onClick={() => handleRequest(p.key)}
                >
                  {state === "requested"
                    ? t.requested
                    : state === "busy"
                      ? t.busy
                      : t.request}
                </button>
              ) : (
                <Link href="/giris" className="nb-btn nb-btn--outline">
                  {t.loginCta}
                </Link>
              )}
              {state === "error" && (
                <div className={styles.error}>{t.requestError}</div>
              )}
              {state === "requested" && (
                <div className={styles.requestedNote}>{t.requestedNote}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
