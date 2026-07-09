"use client";

/** Paylasilan site header — ana sayfa + tum nis sayfalari (sahte-playlist,
 *  attribution, yayin-zamanlamasi, cover-avcisi ve rapor/aday alt sayfalari)
 *  tarafindan kullanilir. Nis sayfalarindaki bagimsiz "SOZY ECHO" topnav'ini
 *  degistirir — tek, tutarli neo-brutal header.
 *
 *  "Sanatcilar Icin" menusu tek dropdown icinde 4 gruba ayrilir (19 duz link
 *  yerine): SEO & Karne / Tanitim / Araclar (Yeni) / Hesap & Pro. Hicbir eski
 *  hedef kaybolmaz — sadece gruplanir. */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale, pick, LangToggle } from "../lib/locale";
import { getToken, getMe, setToken } from "../lib/api";
import styles from "./SiteHeader.module.css";

type LinkItem = { href: string; label: string };

type Dict = {
  artistsFor: string;
  curatorsFor: string;
  radioAds: string;
  login: string;
  join: string;
  logout: string;
  credits: string;
  groups: {
    seo: string;
    promo: string;
    tools: string;
    account: string;
  };
  seoLinks: LinkItem[];
  promoLinks: LinkItem[];
  toolLinks: LinkItem[];
  accountLinks: LinkItem[];
  curatorLinks: LinkItem[];
};

const T: { tr: Dict; en: Dict } = {
  tr: {
    artistsFor: "Sanatçılar İçin ▾",
    curatorsFor: "Küratörler İçin ▾",
    radioAds: "Radyo Reklamı",
    login: "Giriş",
    join: "Bize Katıl",
    logout: "Çıkış",
    credits: "kredi",
    groups: {
      seo: "SEO & Karne",
      promo: "Tanıtım",
      tools: "Araçlar (Yeni)",
      account: "Hesap / Pro",
    },
    seoLinks: [
      { href: "/#nasil-calisir", label: "Nasıl Çalışır" },
      { href: "/karne", label: "Sanatçı İpuçları — SEO Karnesi" },
      { href: "/rapor", label: "🧠 Geri Bildirim Raporu" },
      { href: "/lig", label: "🏆 Karne Ligi" },
      { href: "/kanit", label: "Kanıt Panosu" },
    ],
    promoLinks: [
      { href: "/playlistler", label: "Playlist Eşleştirme" },
      { href: "/gonder", label: "🎵 Şarkını Şimdi Gönder" },
      { href: "/tanitim", label: "🎬 Tanıtım Kartı" },
      { href: "/radyo", label: "📻 Radyo Takibi" },
      { href: "/linkler", label: "🔗 Akıllı Link & Pre-Save" },
      { href: "/reklamlarim", label: "🎙️ Reklamlarım" },
    ],
    toolLinks: [
      { href: "/sahte-playlist", label: "⚖ Sahte Playlist Analizi" },
      { href: "/attribution", label: "📈 ROI Atıf Motoru" },
      { href: "/yayin-zamanlamasi", label: "🗓 Yayın Zamanlaması" },
      { href: "/cover-avcisi", label: "🎯 Cover Avcısı" },
    ],
    accountLinks: [
      { href: "/pro", label: "⭐ Artist Pro" },
      { href: "/panel", label: "📊 A&R Kariyer Panosu" },
      { href: "/takvim", label: "🗓️ Yayın Planı" },
      { href: "/sync/yonet", label: "🎬 Sync İlanlarım" },
    ],
    curatorLinks: [
      { href: "/giris", label: "Küratör Ol" },
      { href: "/#kuratorler", label: "Küratör & Profesyonel Türleri" },
      { href: "/curator/inbox", label: "Gelen Kutusu" },
      { href: "/reklam/yonet", label: "📻 Reklam Envanterim" },
    ],
  },
  en: {
    artistsFor: "For Artists ▾",
    curatorsFor: "For Curators ▾",
    radioAds: "Radio Ads",
    login: "Log In",
    join: "Join Us",
    logout: "Log Out",
    credits: "credits",
    groups: {
      seo: "SEO & Report Card",
      promo: "Promotion",
      tools: "Tools (New)",
      account: "Account / Pro",
    },
    seoLinks: [
      { href: "/#nasil-calisir", label: "How It Works" },
      { href: "/karne", label: "Artist Tips — SEO Report Card" },
      { href: "/rapor", label: "🧠 Feedback Report" },
      { href: "/lig", label: "🏆 Report Card League" },
      { href: "/kanit", label: "Proof Board" },
    ],
    promoLinks: [
      { href: "/playlistler", label: "Playlist Matching" },
      { href: "/gonder", label: "🎵 Submit Your Song Now" },
      { href: "/tanitim", label: "🎬 Promo Card" },
      { href: "/radyo", label: "📻 Radio Airplay Tracking" },
      { href: "/linkler", label: "🔗 Smart Link & Pre-Save" },
      { href: "/reklamlarim", label: "🎙️ My Ads" },
    ],
    toolLinks: [
      { href: "/sahte-playlist", label: "⚖ Fake Playlist Analysis" },
      { href: "/attribution", label: "📈 ROI Attribution Engine" },
      { href: "/yayin-zamanlamasi", label: "🗓 Release Timing" },
      { href: "/cover-avcisi", label: "🎯 Cover Hunter" },
    ],
    accountLinks: [
      { href: "/pro", label: "⭐ Artist Pro" },
      { href: "/panel", label: "📊 A&R Career Dashboard" },
      { href: "/takvim", label: "🗓️ Release Plan" },
      { href: "/sync/yonet", label: "🎬 My Sync Listings" },
    ],
    curatorLinks: [
      { href: "/giris", label: "Become a Curator" },
      { href: "/#kuratorler", label: "Curator & Professional Types" },
      { href: "/curator/inbox", label: "Inbox" },
      { href: "/reklam/yonet", label: "📻 My Ad Inventory" },
    ],
  },
};

/** Oturum-farkinda hesap kontrolu: token varsa isim + kredi + Cikis;
 *  yoksa Giris + Katil. Ana sayfadan tasindi — tum sayfalarda ayni davranis. */
function AccountNav() {
  const { locale } = useLocale();
  const t = pick(T, locale);
  const [me, setMe] = useState<{ name: string; credits: number } | null>(null);

  useEffect(() => {
    if (!getToken()) return;
    let alive = true;
    getMe().then((r) => {
      if (alive && r?.user) {
        setMe({ name: r.user.name, credits: r.user.credits ?? 0 });
      }
    });
    return () => {
      alive = false;
    };
  }, []);

  if (!me) {
    return (
      <>
        <Link href="/giris" className={styles.menuLink}>
          {t.login}
        </Link>
        <Link href="/giris" className="nb-btn">
          {t.join}
        </Link>
      </>
    );
  }

  const logout = () => {
    setToken(null);
    setMe(null);
    if (typeof window !== "undefined") window.location.href = "/";
  };

  return (
    <>
      <Link href="/gonder" className={styles.accountName}>
        <span aria-hidden>👤</span>
        {me.name}
      </Link>
      <span className="nb-pill nb-pill--neon" title={t.credits}>
        ◆ {me.credits} {t.credits}
      </span>
      <button type="button" onClick={logout} className="nb-btn nb-btn--outline">
        {t.logout}
      </button>
    </>
  );
}

function LinkGroup({ title, items, onLinkClick }: {
  title: string;
  items: LinkItem[];
  onLinkClick?: () => void;
}) {
  return (
    <div className={styles.dropdownGroup}>
      <span className={styles.dropdownGroupTitle}>{title}</span>
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={styles.dropdownLink}
          onClick={onLinkClick}
        >
          {item.label}
        </Link>
      ))}
    </div>
  );
}

export default function SiteHeader() {
  const { locale } = useLocale();
  const t = pick(T, locale);
  const tr = locale === "tr";
  const [menuOpen, setMenuOpen] = useState(false);

  const closeMenu = () => setMenuOpen(false);

  return (
    <nav className={styles.nav}>
      <div className={styles.navWrap}>
        <Link href="/" className={styles.logo}>
          SOZY<span className={styles.logoAccent}>ECHO</span>
        </Link>
        <button
          type="button"
          className={styles.hamburger}
          aria-label={tr ? "Menüyü aç/kapat" : "Toggle menu"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? "✕" : "☰"}
        </button>
        <div className={`${styles.menu} ${menuOpen ? styles.menuOpen : ""}`}>
          <div className={styles.menuGroup}>
            <button type="button" className={styles.menuGroupBtn}>
              {t.artistsFor}
            </button>
            <div className={styles.artistsDropdown}>
              <LinkGroup title={t.groups.seo} items={t.seoLinks} onLinkClick={closeMenu} />
              <LinkGroup title={t.groups.promo} items={t.promoLinks} onLinkClick={closeMenu} />
              <LinkGroup title={t.groups.tools} items={t.toolLinks} onLinkClick={closeMenu} />
              <LinkGroup title={t.groups.account} items={t.accountLinks} onLinkClick={closeMenu} />
            </div>
          </div>
          <div className={styles.menuGroup}>
            <button type="button" className={styles.menuGroupBtn}>
              {t.curatorsFor}
            </button>
            <div className={styles.dropdown}>
              {t.curatorLinks.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={styles.dropdownLink}
                  onClick={closeMenu}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
          <Link href="/reklam" className={styles.menuLink} onClick={closeMenu}>
            {t.radioAds}
          </Link>
          <LangToggle />
          <AccountNav />
        </div>
      </div>
    </nav>
  );
}
