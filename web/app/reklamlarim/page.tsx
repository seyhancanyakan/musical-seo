"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFileUrl, getToken, myAds, type ProducedAd } from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

const T = {
  tr: {
    logo: "Sozy Echo",
    gateTitle: "Giriş gerekli",
    gateText: "Ürettiğin reklamları görmek için hesabınla giriş yap.",
    gateLink: "Giriş / Kayıt",
    heading: "Reklamlarım",
    intro:
      "Kampanya Sihirbazı'nda ürettiğin (yönetmen modu veya adım-adım mix) tüm reklam spotları burada listelenir.",
    loading: "Yükleniyor...",
    emptyTitle: "Henüz reklam üretmedin",
    emptyCta: "Kampanya Sihirbazı'ndan başla",
    downloadBtn: "İndir",
    unnamedProduct: "Adsız ürün/sanatçı",
  },
  en: {
    logo: "Sozy Echo",
    gateTitle: "Login required",
    gateText: "Log in with your account to see the ads you've produced.",
    gateLink: "Login / Sign Up",
    heading: "My Ads",
    intro:
      "Every ad spot you produced in the Campaign Wizard (director mode or step-by-step mix) is listed here.",
    loading: "Loading...",
    emptyTitle: "You haven't produced an ad yet",
    emptyCta: "Start from the Campaign Wizard",
    downloadBtn: "Download",
    unnamedProduct: "Unnamed product/artist",
  },
} as const;

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

/** Reklamlarim — sihirbazda (yonetmen/adim-adim) uretilip hesaba kaydedilmis
 *  reklam spotlarinin listesi: dinleme + indirme. Giris gerektirir. */
export default function MyAdsPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [checked, setChecked] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [ads, setAds] = useState<ProducedAd[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!getToken()) {
        setChecked(true);
        return;
      }
      setLoggedIn(true);
      const result = await myAds();
      if (cancelled) return;
      setAds(result ?? []);
      setChecked(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (checked && !loggedIn) {
    return (
      <div className={styles.gate}>
        <div className="nb-card" style={{ padding: 28, maxWidth: 460 }}>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
            <LangToggle />
          </div>
          <h2 className="nb-h">{t.gateTitle}</h2>
          <p className={styles.gateText}>{t.gateText}</p>
          <Link href="/giris" className="nb-btn">
            {t.gateLink}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <Link href="/" className={styles.logo}>
          {t.logo}
        </Link>
        <LangToggle />
      </div>

      <h1 className="nb-h">{t.heading}</h1>
      <p className={styles.intro}>{t.intro}</p>

      {!checked && <div className={styles.empty}>{t.loading}</div>}

      {checked && ads && ads.length === 0 && (
        <div className={`nb-card ${styles.emptyCard}`}>
          <div className={styles.emptyTitle}>{t.emptyTitle}</div>
          <Link href="/reklam/kampanya" className="nb-btn nb-btn--purple">
            {t.emptyCta}
          </Link>
        </div>
      )}

      {checked && ads && ads.length > 0 && (
        <div className={styles.list}>
          {ads.map((ad) => (
            <div key={ad.id} className={`nb-card ${styles.adCard}`}>
              <div className={styles.adInfo}>
                <div className={styles.adName}>
                  {ad.product_name || t.unnamedProduct}
                </div>
                <div className={styles.adDate}>{formatDate(ad.created_at)}</div>
              </div>
              <audio
                controls
                src={apiFileUrl(ad.file_url)}
                className={styles.audioPlayer}
              />
              <a
                href={apiFileUrl(ad.file_url)}
                download
                className="nb-btn nb-btn--outline"
              >
                {t.downloadBtn}
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
