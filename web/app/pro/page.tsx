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
import styles from "./page.module.css";

const CONTACT_EMAIL = "destek@muzikseo.com";

type RequestState = "idle" | "busy" | "requested" | "error";

const BENEFITS = [
  (monthly: number) => `Aylık ${monthly} kredi`,
  () => "Gönderimlerde 1 kredi indirim",
  (_: number, sla: number) => `${sla} saat SLA garantisi`,
  () => "Kohort kıyaslaması (kariyer panonda)",
  () => "EPK, sertifika, etki raporu ve otopilot ücretsiz",
];

/** Artist Pro tanitim + kredi paketleri — pilot doneminde odeme manuel
 *  (havale/Papara), admin talebi onaylayip krediyi yukler. */
export default function ProPage() {
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

  const mailSubject = encodeURIComponent("Artist Pro talebi");
  const mailBody = encodeURIComponent(
    `Merhaba,\n\nArtist Pro'ya geçmek istiyorum.${user ? `\n\nHesap: ${user.email}` : ""}`
  );

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <Link href="/" className={styles.logo}>MuzikSEO</Link>
        {user && (
          <div className={styles.wallet}>💳 {user.credits} kredi · {user.name}</div>
        )}
      </div>

      <div className={styles.hero}>
        <h1 className="nb-h">Artist Pro</h1>
        {pro && (
          <div className={styles.price}>
            {pro.price_try.toLocaleString("tr-TR")} TL<span className={styles.priceUnit}>/ay</span>
          </div>
        )}
        <p className={styles.tagline}>
          Kariyerini büyütmek için tüm premium araçlar tek pakette.
        </p>
      </div>

      {loading && <div className={styles.empty}>Yükleniyor...</div>}

      {!loading && pro && (
        <div className={`nb-card ${styles.benefitsCard}`}>
          <div className={styles.benefitsTitle}>Avantajlar</div>
          <ul className={styles.benefitsList}>
            {BENEFITS.map((render, i) => (
              <li key={i} className={styles.benefitItem}>
                ✓ {render(pro.monthly_credits, pro.sla_hours)}
              </li>
            ))}
          </ul>
          <a
            href={`mailto:${CONTACT_EMAIL}?subject=${mailSubject}&body=${mailBody}`}
            className="nb-btn nb-btn--purple"
          >
            Pro&apos;ya Geçmek İçin Bize Yaz
          </a>
          <p className={styles.note}>
            Pilot döneminde ödeme manuel (havale/Papara) — bize yazınca 24
            saat içinde aktif ederiz.
          </p>
        </div>
      )}

      <h2 className="nb-h" style={{ fontSize: 18 }}>Kredi Paketleri</h2>
      <div className={styles.packageGrid}>
        {packages.map((p) => {
          const state = requestStates[p.key] ?? "idle";
          return (
            <div key={p.key} className={`nb-card ${styles.packageCard}`}>
              <div className={styles.packageLabel}>{p.label}</div>
              <div className={styles.packageCredits}>{p.credits} kredi</div>
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
                    ? "✓ Talep Alındı"
                    : state === "busy"
                      ? "..."
                      : "Talep Et"}
                </button>
              ) : (
                <Link href="/giris" className="nb-btn nb-btn--outline">
                  Giriş Yap
                </Link>
              )}
              {state === "error" && (
                <div className={styles.error}>Talep gönderilemedi — tekrar dene.</div>
              )}
              {state === "requested" && (
                <div className={styles.requestedNote}>
                  Admin onayı bekleniyor — onaylanınca kredin yüklenir.
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
