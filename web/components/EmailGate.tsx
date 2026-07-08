"use client";

/** Yeniden kullanilabilir e-posta kapisi — programatik SEO sayfalarinin (Tier 3
 *  sanatci sayfalari, araclar) "ucretsiz teaser + tam icerik icin e-posta"
 *  huninde kullanilir (bkz. docs/PROGRAMATIK_SEO_WORKFLOW.md §8).
 *
 *  Kilit durumu localStorage'da tutulur: `msq_lead_<source>` (bu kaynağa
 *  ozel) + global `msq_lead` (herhangi bir sayfada acilan kilit hepsini
 *  acar — kullanici deneyimi icin). Backend'e lead POST /leads/capture ile
 *  gider; hata olursa kilit acilmaz, mesaj gorunur (asla sessizce yutulmaz). */

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { captureLead } from "../lib/api";
import { useLocale, pick } from "../lib/locale";
import styles from "./EmailGate.module.css";

const GLOBAL_FLAG = "msq_lead";

function leadKey(source: string): string {
  return `msq_lead_${source}`;
}

function hasLead(source: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return (
      window.localStorage.getItem(leadKey(source)) === "1" ||
      window.localStorage.getItem(GLOBAL_FLAG) === "1"
    );
  } catch {
    // localStorage kapali (gizli mod/kurumsal politika) — kilit bu oturumda
    // kalici olmaz ama form yine calisir, cokmez.
    return false;
  }
}

function markLead(source: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(leadKey(source), "1");
    window.localStorage.setItem(GLOBAL_FLAG, "1");
  } catch {
    // Ayni sebep: yazma basarisiz olursa sessizce gec — kullanici yine de
    // bu render'da icerigi gorur (unlocked state zaten true).
  }
}

const T = {
  tr: {
    title: "Kilidi Aç",
    lede: "Tam rapor + gerçek zamanlı takip için e-posta gir.",
    placeholder: "e-posta adresin",
    submit: "Kilidi Aç",
    submitting: "Gönderiliyor…",
    errorPrefix: "Kilit açılamadı:",
  },
  en: {
    title: "Unlock",
    lede: "Enter your email for the full report + real-time tracking.",
    placeholder: "your email",
    submit: "Unlock",
    submitting: "Sending…",
    errorPrefix: "Couldn't unlock:",
  },
};

type Props = {
  /** Lead kaynagi (or. "artist_tarkan") — analytics + localStorage anahtari. */
  source: string;
  /** Kilit acildiginda gosterilecek gercek icerik. */
  children: ReactNode;
  /** Kilitliyken arka planda blur'lu gosterilecek onizleme; verilmezse
   *  children'in kendisi blur'lu gosterilir. */
  teaser?: ReactNode;
};

export default function EmailGate({ source, children, teaser }: Props) {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [unlocked, setUnlocked] = useState(false);
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState(""); // honeypot
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setUnlocked(hasLead(source));
  }, [source]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = email.trim();
    if (!trimmed || loading) return;

    if (website.trim()) {
      // Honeypot doldurulmus (bot) — sessizce "basarili" gibi davran, gercek
      // istek atma. Gercek kullanicilar bu alani hic gormez.
      markLead(source);
      setUnlocked(true);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const { data, error: apiError } = await captureLead(trimmed, source);
      if (data?.ok) {
        markLead(source);
        setUnlocked(true);
        return;
      }
      setError(apiError ?? "—");
    } finally {
      setLoading(false);
    }
  }

  if (unlocked) return <>{children}</>;

  return (
    <div className={styles.gate}>
      <div className={styles.blurred} aria-hidden="true">
        {teaser ?? children}
      </div>
      <div className={styles.overlay}>
        <form className={`nb-card ${styles.form}`} onSubmit={handleSubmit}>
          <h4 className={styles.title}>{t.title}</h4>
          <p className={styles.lede}>{t.lede}</p>
          <input
            type="email"
            required
            className="nb-input"
            placeholder={t.placeholder}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          {/* Honeypot: gercek kullanicilar gormez/doldurmaz (CSS ile gizli). */}
          <input
            type="text"
            name="website"
            value={website}
            onChange={(event) => setWebsite(event.target.value)}
            className={styles.honeypot}
            tabIndex={-1}
            autoComplete="off"
            aria-hidden="true"
          />
          <button type="submit" className="nb-btn" disabled={loading}>
            {loading ? t.submitting : t.submit}
          </button>
          {error && (
            <div className={styles.error}>
              {t.errorPrefix} {error}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
