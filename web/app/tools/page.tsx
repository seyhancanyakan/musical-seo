"use client";

/** Araclar index — Tier-2 ucretsiz araclar (programatik SEO §3). Yapiskan,
 *  aliskanlik yaratan ucretsiz araclar: 4 tanesi anlik API sonucu doner
 *  (/tools/[tool]), 2 tanesi (sahte playlist, cover avcisi) zaten kendi
 *  tam sayfalarina sahip dunya-ilk ozellikler — burada da one cikarilir. */

import Link from "next/link";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";

type Card = {
  href: string;
  emoji: string;
  title: string;
  desc: string;
  badge?: string;
};

const T = {
  tr: {
    title: "Ücretsiz Müzik Araçları",
    lede:
      "Kayıt olmadan, saniyeler içinde: BPM bul, ton tahmini al, ISRC sorgula — ve dünyada eşi olmayan iki analiz aracımızı keşfet.",
    cards: [
      {
        href: "/tools/bpm-finder",
        emoji: "🎵",
        title: "BPM Bulucu",
        desc: "Şarkı adını yaz, tempoyu (BPM) saniyeler içinde öğren — Deezer önizlemesinden gerçek ses analizi.",
      },
      {
        href: "/tools/song-key-detector",
        emoji: "🎹",
        title: "Şarkı Tonu Tahmincisi",
        desc: "Ses profilinden (parlaklık/enerji) sezgisel bir ton tahmini — DJ setleri ve mix hazırlığı için hızlı ipucu.",
      },
      {
        href: "/tools/isrc-lookup",
        emoji: "🔖",
        title: "ISRC Sorgulama",
        desc: "Sanatçı - şarkı adını gir, uluslararası standart kayıt kodunu (ISRC) ve yayın tarihini bul.",
      },
      {
        href: "/tools/spotify-monthly-listeners-tracker",
        emoji: "📊",
        title: "Aylık Dinleyici Takibi",
        desc: "Spotify aylık dinleyici sayısı public API'de yok — bu araç neden olmadığını ve gerçek alternatifleri anlatır.",
      },
      {
        href: "/sahte-playlist",
        emoji: "⚖",
        title: "Sahte Playlist Kontrolcüsü",
        desc: "Follower anomalisi, track churn, coğrafi kümelenme — para ödemeden önce playlist'in gerçek mi bot mu olduğunu anla.",
        badge: "Dünyada İlk",
      },
      {
        href: "/cover-avcisi",
        emoji: "🎯",
        title: "Cover Avcısı",
        desc: "Şarkının izinsiz cover/derivative sürümlerini ses parmak iziyle tarar, telif itirazı belgesi üretir.",
        badge: "Dünyada İlk",
      },
    ] as Card[],
  },
  en: {
    title: "Free Music Tools",
    lede:
      "No signup, results in seconds: find BPM, estimate key, look up ISRC — plus two analysis tools that exist nowhere else.",
    cards: [
      {
        href: "/tools/bpm-finder",
        emoji: "🎵",
        title: "BPM Finder",
        desc: "Type a song name, get its tempo (BPM) in seconds — real audio analysis from a Deezer preview.",
      },
      {
        href: "/tools/song-key-detector",
        emoji: "🎹",
        title: "Song Key Detector",
        desc: "A heuristic key estimate from the audio profile (brightness/energy) — a quick hint for DJ sets and mixing.",
      },
      {
        href: "/tools/isrc-lookup",
        emoji: "🔖",
        title: "ISRC Lookup",
        desc: "Enter Artist - Title, get the International Standard Recording Code (ISRC) and release date.",
      },
      {
        href: "/tools/spotify-monthly-listeners-tracker",
        emoji: "📊",
        title: "Monthly Listeners Tracker",
        desc: "Spotify monthly listeners isn't in the public API — this tool explains why, and the real alternatives.",
      },
      {
        href: "/sahte-playlist",
        emoji: "⚖",
        title: "Fake Playlist Checker",
        desc: "Follower anomalies, track churn, geo clustering — know if a playlist is real or bot-filled before you pay.",
        badge: "World-First",
      },
      {
        href: "/cover-avcisi",
        emoji: "🎯",
        title: "Cover Finder",
        desc: "Scans for unlicensed cover/derivative versions of your song by audio fingerprint, generates a takedown packet.",
        badge: "World-First",
      },
    ] as Card[],
  },
};

export default function ToolsIndexPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  return (
    <div className={styles.page}>
      <main className={styles.body}>
        <h1 className={`nb-h ${styles.title}`}>{t.title}</h1>
        <p className={styles.lede}>{t.lede}</p>

        <div className={styles.grid}>
          {t.cards.map((card) => (
            <Link key={card.href} href={card.href} className={`nb-card ${styles.card}`}>
              {card.badge && <span className={styles.badge}>{card.badge}</span>}
              <span className={styles.emoji} aria-hidden>
                {card.emoji}
              </span>
              <span className={styles.cardTitle}>{card.title}</span>
              <span className={styles.cardDesc}>{card.desc}</span>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
