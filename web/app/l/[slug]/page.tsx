"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { addLinkFan, getPublicLink, recordLinkClick, type SmartLink } from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type PlatformMeta = { labelTr: string; labelEn: string; bg: string; color: string };

const PLATFORM_META: Record<string, PlatformMeta> = {
  spotify: { labelTr: "Spotify'da Dinle", labelEn: "Listen on Spotify", bg: "#1DB954", color: "#fff" },
  deezer: { labelTr: "Deezer'da Dinle", labelEn: "Listen on Deezer", bg: "#A238FF", color: "#fff" },
  youtube: { labelTr: "YouTube'da İzle", labelEn: "Watch on YouTube", bg: "#FF0000", color: "#fff" },
  apple: { labelTr: "Apple Music'te Dinle", labelEn: "Listen on Apple Music", bg: "#000000", color: "#fff" },
  other: { labelTr: "Bağlantıyı Aç", labelEn: "Open Link", bg: "#2d6bff", color: "#fff" },
};

const PLATFORM_ORDER = ["spotify", "deezer", "youtube", "apple", "other"];

const T = {
  tr: {
    loading: "Yükleniyor...",
    notFoundTitle: "Link bulunamadı",
    notFoundText: "Bu bağlantı geçersiz olabilir ya da kaldırılmış.",
    backHome: "Ana Sayfaya Dön",
    presaveLabel: "Yakında Çıkıyor",
    days: "gün",
    hours: "saat",
    minutes: "dakika",
    seconds: "saniye",
    notifyReleaseLabel: "Çıkışta haber ver",
    notifyFutureLabel: "Yeni çıkışlardan haberdar ol",
    emailPlaceholder: "E-posta adresin",
    notifyBtn: "Haber Ver",
    busy: "...",
    subscribeSuccess: "✓ Kaydedildi — çıkışında haber vereceğiz.",
    subscribeRepeat: "Zaten kayıtlısın — tekrar haber vereceğiz.",
    subscribeError: "Kaydedilemedi — tekrar dene.",
    badge: "Songdeck",
  },
  en: {
    loading: "Loading...",
    notFoundTitle: "Link not found",
    notFoundText: "This link may be invalid or has been removed.",
    backHome: "Back to Home",
    presaveLabel: "Coming Soon",
    days: "days",
    hours: "hours",
    minutes: "minutes",
    seconds: "seconds",
    notifyReleaseLabel: "Notify me on release",
    notifyFutureLabel: "Get notified about new releases",
    emailPlaceholder: "Your email address",
    notifyBtn: "Notify Me",
    busy: "...",
    subscribeSuccess: "✓ Saved — we'll let you know when it's out.",
    subscribeRepeat: "You're already signed up — we'll notify you.",
    subscribeError: "Couldn't save — try again.",
    badge: "Songdeck",
  },
} as const;

function isFuture(iso: string | null): boolean {
  if (!iso) return false;
  return new Date(iso).getTime() > Date.now();
}

function formatCountdown(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000));
  return {
    days: Math.floor(total / 86400),
    hours: Math.floor((total % 86400) / 3600),
    minutes: Math.floor((total % 3600) / 60),
    seconds: total % 60,
  };
}

function useCountdown(target: string | null): number {
  const [remaining, setRemaining] = useState<number>(() =>
    target ? new Date(target).getTime() - Date.now() : 0
  );

  useEffect(() => {
    if (!target) {
      setRemaining(0);
      return;
    }
    setRemaining(new Date(target).getTime() - Date.now());
    const id = setInterval(() => {
      setRemaining(new Date(target).getTime() - Date.now());
    }, 1000);
    return () => clearInterval(id);
  }, [target]);

  return Math.max(0, remaining);
}

/** Public akilli link sayfasi — auth yok. Platform butonlari + presave geri
 *  sayimi ya da genel hayran kaydi formu. Her cagri goruntuleme sayacini
 *  artirir (getPublicLink backend tarafinda). */
export default function PublicSmartLinkPage() {
  const params = useParams<{ slug: string }>();
  const slug = params?.slug ?? "";
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [link, setLink] = useState<SmartLink | null | undefined>(undefined);
  const [email, setEmail] = useState("");
  const [subBusy, setSubBusy] = useState(false);
  const [subMsg, setSubMsg] = useState<"success" | "repeat" | "error" | "">("");

  useEffect(() => {
    if (!slug) {
      setLink(null);
      return;
    }
    (async () => {
      const result = await getPublicLink(slug);
      setLink(result);
    })();
  }, [slug]);

  const showPresave = !!link && link.presave === 1 && isFuture(link.release_date);
  const remainingMs = useCountdown(showPresave && link ? link.release_date : null);
  const cd = formatCountdown(remainingMs);

  function handlePlatformClick(platform: string, url: string) {
    void recordLinkClick(slug, platform);
    window.location.href = url;
  }

  async function handleSubscribe(e: FormEvent) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;
    setSubBusy(true);
    setSubMsg("");
    const result = await addLinkFan(slug, trimmed);
    setSubBusy(false);
    if (!result) {
      setSubMsg("error");
      return;
    }
    setSubMsg(result.added ? "success" : "repeat");
    if (result.added) setEmail("");
  }

  if (link === undefined) {
    return (
      <div className={styles.center}>
        <div className={styles.loadingText}>{t.loading}</div>
      </div>
    );
  }

  if (link === null) {
    return (
      <div className={styles.center}>
        <div className={`nb-card ${styles.notFoundCard}`}>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
            <LangToggle />
          </div>
          <div className={styles.notFoundTitle}>{t.notFoundTitle}</div>
          <p className={styles.notFoundText}>{t.notFoundText}</p>
          <Link href="/" className="nb-btn">{t.backHome}</Link>
        </div>
      </div>
    );
  }

  const platforms = PLATFORM_ORDER.filter((p) => link.links[p]);

  return (
    <div className={styles.wrap}>
      <div className={styles.topbar}>
        <span className={styles.brandTag}>Songdeck</span>
        <LangToggle />
      </div>

      <main className={`nb-card ${styles.card}`}>
        <div className={styles.headline}>
          <div className={styles.artist}>{link.artist}</div>
          <div className={styles.title}>{link.title}</div>
        </div>

        {showPresave && (
          <div className={styles.presaveBox}>
            <div className={styles.presaveLabel}>{t.presaveLabel}</div>
            <div className={styles.countdown}>
              <div className={styles.countUnit}>
                <span className={styles.countNum}>{cd.days}</span>
                <small className={styles.countUnitLabel}>{t.days}</small>
              </div>
              <div className={styles.countUnit}>
                <span className={styles.countNum}>{cd.hours}</span>
                <small className={styles.countUnitLabel}>{t.hours}</small>
              </div>
              <div className={styles.countUnit}>
                <span className={styles.countNum}>{cd.minutes}</span>
                <small className={styles.countUnitLabel}>{t.minutes}</small>
              </div>
              <div className={styles.countUnit}>
                <span className={styles.countNum}>{cd.seconds}</span>
                <small className={styles.countUnitLabel}>{t.seconds}</small>
              </div>
            </div>
          </div>
        )}

        <div className={styles.platformList}>
          {platforms.map((p) => {
            const meta = PLATFORM_META[p] ?? PLATFORM_META.other;
            const label = locale === "tr" ? meta.labelTr : meta.labelEn;
            return (
              <button
                key={p}
                type="button"
                className={styles.platformBtn}
                style={{ background: meta.bg, color: meta.color }}
                onClick={() => handlePlatformClick(p, link.links[p])}
              >
                {label}
              </button>
            );
          })}
        </div>

        <form className={styles.fanForm} onSubmit={handleSubscribe}>
          <label className={styles.fanFormLabel} htmlFor="fan-email">
            {showPresave ? t.notifyReleaseLabel : t.notifyFutureLabel}
          </label>
          <div className={styles.fanFormRow}>
            <input
              id="fan-email"
              className="nb-input"
              type="email"
              required
              placeholder={t.emailPlaceholder}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <button type="submit" className="nb-btn" disabled={subBusy}>
              {subBusy ? t.busy : t.notifyBtn}
            </button>
          </div>
          {subMsg === "success" && (
            <div className={styles.fanMsgSuccess}>{t.subscribeSuccess}</div>
          )}
          {subMsg === "repeat" && (
            <div className={styles.fanMsgRepeat}>{t.subscribeRepeat}</div>
          )}
          {subMsg === "error" && (
            <div className={styles.fanMsgError}>{t.subscribeError}</div>
          )}
        </form>
      </main>

      <Link href="/" className={styles.badge}>{t.badge}</Link>
    </div>
  );
}
