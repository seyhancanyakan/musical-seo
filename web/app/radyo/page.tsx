"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  getMe,
  getToken,
  myAirplayHits,
  myAirplaySubscriptions,
  subscribeAirplay,
  type AirplayHit,
  type AirplaySubscription,
  type User,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

const T = {
  tr: {
    gateTitle: "Giriş gerekli",
    gateText: "Radyo takibi için sanatçı hesabınla giriş yap.",
    gateLink: "Giriş / Kayıt",
    walletLine: (credits: number, name: string) => `💳 ${credits} kredi · ${name}`,
    heading: "Radyo Takibi",
    promise:
      "Şarkın hangi online radyoda çaldı? Stream metadata'sından bağımsız kanıt — 2 kredi / 30 gün / parça.",
    subscribeTitle: "Yeni Abonelik",
    songPlaceholder: 'Şarkın: "Sanatçı - Şarkı"',
    subscribeCta: "Abone Ol (2 kredi)",
    busy: "...",
    errSongFormat: 'Şarkıyı "Sanatçı - Şarkı" formatında yaz.',
    errSubscribeFailed:
      "Abonelik başarısız — kredin yetersiz olabilir ya da bu şarkı için zaten aktif bir abonelik var.",
    subsTitle: "Aboneliklerim",
    subsEmpty: "Henüz abonelik yok.",
    colSong: "Şarkı",
    colExpires: "Bitiş Tarihi",
    colStatus: "Durum",
    statusActive: "Aktif",
    statusExpired: "Süresi Dolmuş",
    hitsTitle: "Çalma Kayıtları",
    hitsEmpty: "Henüz çalma yakalanmadı — istasyonlar 10 dakikada bir taranıyor.",
    colDate: "Tarih - Saat",
    colStation: "İstasyon",
    colRawTitle: "Yakalanan Ham Başlık",
    loading: "Yükleniyor...",
  },
  en: {
    gateTitle: "Login required",
    gateText: "Log in with your artist account to track radio airplay.",
    gateLink: "Login / Sign Up",
    walletLine: (credits: number, name: string) => `💳 ${credits} credits · ${name}`,
    heading: "Radio Airplay Tracking",
    promise:
      "Did your song play on an online radio station? Proof independent of stream metadata — 2 credits / 30 days / track.",
    subscribeTitle: "New Subscription",
    songPlaceholder: 'Your song: "Artist - Title"',
    subscribeCta: "Subscribe (2 credits)",
    busy: "...",
    errSongFormat: 'Write your song as "Artist - Title".',
    errSubscribeFailed:
      "Subscription failed — you may not have enough credits, or there's already an active subscription for this song.",
    subsTitle: "My Subscriptions",
    subsEmpty: "No subscriptions yet.",
    colSong: "Song",
    colExpires: "Expires",
    colStatus: "Status",
    statusActive: "Active",
    statusExpired: "Expired",
    hitsTitle: "Airplay Hits",
    hitsEmpty: "No airplay caught yet — stations are scanned every 10 minutes.",
    colDate: "Date - Time",
    colStation: "Station",
    colRawTitle: "Captured Raw Title",
    loading: "Loading...",
  },
} as const;

function parseSong(raw: string): { artist: string; title: string } | null {
  const trimmed = raw.trim();
  if (!trimmed.includes(" - ")) return null;
  const [artist, ...rest] = trimmed.split(" - ");
  const title = rest.join(" - ").trim();
  if (!artist.trim() || !title) return null;
  return { artist: artist.trim(), title };
}

function isSubscriptionActive(sub: AirplaySubscription): boolean {
  if (!sub.active) return false;
  return new Date(sub.expires_at).getTime() > Date.now();
}

function localeTag(locale: string): string {
  return locale === "tr" ? "tr-TR" : "en-US";
}

/** Radyo Takibi — sanatci abone oldugu sarkinin online radyolarda calip
 *  calmadigini izler (icecast/shoutcast metadata taramasi, 10 dk periyodik). */
export default function RadyoPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [subscriptions, setSubscriptions] = useState<AirplaySubscription[]>([]);
  const [hits, setHits] = useState<AirplayHit[]>([]);
  const [loading, setLoading] = useState(true);

  const [song, setSong] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      if (getToken()) {
        const me = await getMe();
        if (me && me.user.role === "artist") {
          setUser(me.user);
          const [subs, hitList] = await Promise.all([
            myAirplaySubscriptions(),
            myAirplayHits(),
          ]);
          if (subs) setSubscriptions(subs);
          if (hitList) setHits(hitList);
        }
      }
      setChecked(true);
      setLoading(false);
    })();
  }, []);

  async function handleSubscribe(e: FormEvent) {
    e.preventDefault();
    setError("");
    const parsed = parseSong(song);
    if (!parsed) {
      setError(t.errSongFormat);
      return;
    }
    setBusy(true);
    const created = await subscribeAirplay(parsed.artist, parsed.title);
    setBusy(false);
    if (!created) {
      setError(t.errSubscribeFailed);
      return;
    }
    setSubscriptions((prev) => [created, ...prev]);
    setUser((prev) => (prev ? { ...prev, credits: prev.credits - 2 } : prev));
    setSong("");
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

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" className={styles.logo}>Songdeck</Link>
          <LangToggle />
        </div>
        {user && (
          <div className={styles.wallet}>{t.walletLine(user.credits, user.name)}</div>
        )}
      </div>

      <h1 className="nb-h">{t.heading}</h1>
      <p className={styles.promise}>{t.promise}</p>

      <h2 className="nb-h" style={{ fontSize: 18 }}>{t.subscribeTitle}</h2>
      <form className={`nb-card ${styles.subscribeForm}`} onSubmit={handleSubscribe}>
        <input
          className="nb-input"
          placeholder={t.songPlaceholder}
          value={song}
          onChange={(e) => setSong(e.target.value)}
        />
        {error && <div className={styles.error}>{error}</div>}
        <button type="submit" className="nb-btn nb-btn--purple" disabled={busy}>
          {busy ? t.busy : t.subscribeCta}
        </button>
      </form>

      <h2 className="nb-h" style={{ fontSize: 18 }}>{t.subsTitle}</h2>
      {loading && <div className={styles.empty}>{t.loading}</div>}
      {!loading && subscriptions.length === 0 && (
        <div className={styles.empty}>{t.subsEmpty}</div>
      )}
      {!loading && subscriptions.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t.colSong}</th>
                <th>{t.colExpires}</th>
                <th>{t.colStatus}</th>
              </tr>
            </thead>
            <tbody>
              {subscriptions.map((s) => {
                const active = isSubscriptionActive(s);
                return (
                  <tr key={s.id}>
                    <td>{s.artist} — {s.title}</td>
                    <td>{new Date(s.expires_at).toLocaleString(localeTag(locale))}</td>
                    <td>
                      <span className={`${styles.pill} ${active ? styles.ok : styles.fail}`}>
                        {active ? t.statusActive : t.statusExpired}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="nb-h" style={{ fontSize: 18 }}>{t.hitsTitle}</h2>
      {!loading && hits.length === 0 && (
        <div className={styles.empty}>{t.hitsEmpty}</div>
      )}
      {!loading && hits.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t.colDate}</th>
                <th>{t.colStation}</th>
                <th>{t.colRawTitle}</th>
              </tr>
            </thead>
            <tbody>
              {hits.map((h) => (
                <tr key={h.id}>
                  <td>{new Date(h.created_at).toLocaleString(localeTag(locale))}</td>
                  <td>{h.station_name}</td>
                  <td>{h.raw_title ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
