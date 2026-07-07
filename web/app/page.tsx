"use client";

import Link from "next/link";
import styles from "./page.module.css";
import { useLocale, pick, LangToggle } from "../lib/locale";

type Dict = {
  nav: {
    artistsFor: string;
    howItWorks: string;
    artistTips: string;
    playlistMatch: string;
    proofBoard: string;
    submitSong: string;
    arBoard: string;
    releasePlan: string;
    league: string;
    artistPro: string;
    smartLinks: string;
    radio: string;
    report: string;
    promoCard: string;
    syncManage: string;
    myAds: string;
    curatorsFor: string;
    becomeCurator: string;
    curatorTypes: string;
    inbox: string;
    adInventory: string;
    radioAds: string;
    admin: string;
    login: string;
    join: string;
  };
  hero: {
    badge: string;
    titlePart1: string;
    titleHighlight: string;
    titlePart2: string;
    sub: string;
    ctaArtist: string;
    ctaCurator: string;
  };
  stats: {
    slaValue: string;
    slaLabel: string;
    typesValue: string;
    typesLabel: string;
    verifiedValue: string;
    verifiedLabel: string;
  };
  features: {
    tag: string;
    title: string;
    card1Title: string;
    card1Text: string;
    card2Title: string;
    card2Text: string;
    card3Title: string;
    card3Text: string;
  };
  roles: {
    tag: string;
    title: string;
    sub: string;
    cards: { label: string; note: string }[];
    cta: string;
  };
  faq: {
    tag: string;
    title: string;
    q1: string;
    a1: string;
    q2: string;
    a2: string;
    q3: string;
    a3: string;
    q4: string;
    a4: string;
  };
  footer: {
    productHeading: string;
    seoReport: string;
    playlistMatch: string;
    submitSong: string;
    proofBoard: string;
    league: string;
    artistPro: string;
    artistsHeading: string;
    signUp: string;
    myCampaigns: string;
    careerBoard: string;
    releasePlan: string;
    howItWorks: string;
    professionalsHeading: string;
    becomeCurator: string;
    professionalTypes: string;
    inbox: string;
    chip: string;
    trustPart1: string;
    trustBold1: string;
    trustPart2: string;
    trustBold2: string;
    trustPart3: string;
  };
};

const T: { tr: Dict; en: Dict } = {
  tr: {
    nav: {
      artistsFor: "Sanatçılar İçin ▾",
      howItWorks: "Nasıl Çalışır",
      artistTips: "Sanatçı İpuçları — SEO Karnesi",
      playlistMatch: "Playlist Eşleştirme",
      proofBoard: "Kanıt Panosu",
      submitSong: "🎵 Şarkını Şimdi Gönder",
      arBoard: "📊 A&R Kariyer Panosu",
      releasePlan: "🗓️ Yayın Planı",
      league: "🏆 Karne Ligi",
      artistPro: "⭐ Artist Pro",
      smartLinks: "🔗 Akıllı Link & Pre-Save",
      radio: "📻 Radyo Takibi",
      report: "🧠 Geri Bildirim Raporu",
      promoCard: "🎬 Tanıtım Kartı",
      syncManage: "🎬 Sync İlanlarım",
      myAds: "🎙️ Reklamlarım",
      curatorsFor: "Küratörler İçin ▾",
      becomeCurator: "Küratör Ol",
      curatorTypes: "Küratör & Profesyonel Türleri",
      inbox: "Gelen Kutusu",
      adInventory: "📻 Reklam Envanterim",
      radioAds: "Radyo Reklamı",
      admin: "Admin",
      login: "Giriş",
      join: "Bize Katıl",
    },
    hero: {
      badge: "Türkiye'nin ilk müzik SEO panosu",
      titlePart1: "ŞARKIN ",
      titleHighlight: "HAK ETTİĞİ",
      titlePart2: "GÖRÜNÜRLÜĞE ULAŞSIN",
      sub: "SEO karnesi, doğru playlist'lere sistemli pitch, kanıtlı sonuç. Garanti dinlenme satmıyoruz — kanıt satıyoruz.",
      ctaArtist: "Sanatçıyım — Karnemi Çıkar",
      ctaCurator: "Curator'ım — Listemle Kazan",
    },
    stats: {
      slaValue: "72 saat",
      slaLabel: "garantili yanıt SLA'sı",
      typesValue: "9 tür",
      typesLabel: "küratör & müzik profesyoneli",
      verifiedValue: "%100",
      verifiedLabel: "API'den doğrulanmış yerleşim",
    },
    features: {
      tag: "Nasıl Çalışır",
      title: "ÜÇ ADIMDA GÖRÜNÜRLÜKTEN KANITA",
      card1Title: "SEO Karnesi 0-100",
      card1Text:
        "Metadata, dijital varlık, tutarlılık ve anahtar kelime başlıklarında şarkının tam karnesini çıkarır, eksikleri net şekilde gösteririz.",
      card2Title: "Playlist Eşleştirme",
      card2Text:
        "Şarkının tarzına, temposuna ve dinleyici kitlene en uygun curator listelerini bulur, skorlar ve önceliklendiririz.",
      card3Title: "Doğrulanmış Yerleşim Kanıtı",
      card3Text:
        "Her yerleşim bağımsız API'lerden doğrulanır. Ekran görüntüsü değil, gerçek zaman damgalı kanıt sunarız.",
    },
    roles: {
      tag: "Küratörler İçin",
      title: "SADECE PLAYLIST DEĞİL — 9 TÜR MÜZİK PROFESYONELİ",
      sub: "Şarkılar doğru kulaklara gitsin: her tür kendi fırsatını sunar. Nitelikli geri bildirim her türde kazandırır.",
      cards: [
        { label: "🎧 Playlist Küratörü", note: "Listeye ekleme fırsatı" },
        { label: "📻 Radyo", note: "Yayında çalma fırsatı" },
        { label: "📰 Medya / Blog", note: "Haber & yazı fırsatı" },
        { label: "💿 Label", note: "Değerlendirme fırsatı" },
        { label: "🧑‍💼 Menajer", note: "Görüşme fırsatı" },
        { label: "🎪 Booker", note: "Sahne / booking fırsatı" },
        { label: "🎛️ DJ", note: "Sette çalma fırsatı" },
        { label: "🎓 Mentor", note: "Mentorluk seansı" },
        { label: "🎬 Sync Uzmanı", note: "Film / dizi / reklam" },
      ],
      cta: "Küratör Ol — Başvur",
    },
    faq: {
      tag: "Sık Sorulanlar",
      title: "MERAK EDİLENLER",
      q1: "Label'sız kullanabilir miyim?",
      a1: "Evet. MuzikSEO bağımsız ve kendi işini yöneten sanatçılar için kuruldu — label ya da PR ajansı şartı yok.",
      q2: "Küratör cevap vermezse ne olur?",
      a2: "72 saat içinde yanıt gelmezse kredin otomatik iade edilir. Elle talep gerekmez; sistem SLA'yı kendisi işletir.",
      q3: "Kredi nedir, nasıl çalışır?",
      a3: "Her gönderim 1 kredi harcar. Karşılığında gerçek dinleme ve en az 120 karakter yazılı değerlendirme garantisi alırsın. Playlist'e ekleme satılmaz — küratör editoryal olarak bağımsızdır.",
      q4: "Hangi türler destekleniyor?",
      a4: "Tüm müzik türleri. Eşleştirme motoru şarkının tarzına, temposuna ve dinleyici kitlene göre en uygun küratörleri skorlar.",
    },
    footer: {
      productHeading: "Ürün",
      seoReport: "SEO Karnesi",
      playlistMatch: "Playlist Eşleştirme",
      submitSong: "Şarkı Gönder",
      proofBoard: "Kanıt Panosu",
      league: "Karne Ligi",
      artistPro: "Artist Pro",
      artistsHeading: "Sanatçılar",
      signUp: "Kayıt Ol",
      myCampaigns: "Kampanyalarım",
      careerBoard: "Kariyer Panosu",
      releasePlan: "Yayın Planı",
      howItWorks: "Nasıl Çalışır",
      professionalsHeading: "Profesyoneller",
      becomeCurator: "Küratör Ol",
      professionalTypes: "Profesyonel Türleri",
      inbox: "Gelen Kutusu",
      chip: "MuzikSEO © 2026",
      trustPart1: "Her hafta ",
      trustBold1: "340+",
      trustPart2: " yerleşim doğrulanıyor · ",
      trustBold2: "Sıfır",
      trustPart3: " sahte dinlenme garantisi",
    },
  },
  en: {
    nav: {
      artistsFor: "For Artists ▾",
      howItWorks: "How It Works",
      artistTips: "Artist Tips — SEO Report Card",
      playlistMatch: "Playlist Matching",
      proofBoard: "Proof Board",
      submitSong: "🎵 Submit Your Song Now",
      arBoard: "📊 A&R Career Dashboard",
      releasePlan: "🗓️ Release Plan",
      league: "🏆 Report Card League",
      artistPro: "⭐ Artist Pro",
      smartLinks: "🔗 Smart Link & Pre-Save",
      radio: "📻 Radio Airplay Tracking",
      report: "🧠 Feedback Report",
      promoCard: "🎬 Promo Card",
      syncManage: "🎬 My Sync Listings",
      myAds: "🎙️ My Ads",
      curatorsFor: "For Curators ▾",
      becomeCurator: "Become a Curator",
      curatorTypes: "Curator & Professional Types",
      inbox: "Inbox",
      adInventory: "📻 My Ad Inventory",
      radioAds: "Radio Ads",
      admin: "Admin",
      login: "Log In",
      join: "Join Us",
    },
    hero: {
      badge: "Turkey's first music SEO dashboard",
      titlePart1: "GET YOUR SONG THE ",
      titleHighlight: "VISIBILITY",
      titlePart2: "IT DESERVES",
      sub: "An SEO report card, systematic pitching to the right playlists, and proven results. We don't sell guaranteed streams — we sell proof.",
      ctaArtist: "I'm an Artist — Get My Report Card",
      ctaCurator: "I'm a Curator — Earn With My List",
    },
    stats: {
      slaValue: "72 hours",
      slaLabel: "guaranteed response SLA",
      typesValue: "9 types",
      typesLabel: "curators & music professionals",
      verifiedValue: "100%",
      verifiedLabel: "placements verified via API",
    },
    features: {
      tag: "How It Works",
      title: "FROM VISIBILITY TO PROOF IN THREE STEPS",
      card1Title: "SEO Report Card 0-100",
      card1Text:
        "We generate a full report on your song's metadata, digital assets, consistency, and keyword titles, and show you exactly what's missing.",
      card2Title: "Playlist Matching",
      card2Text:
        "We find, score, and prioritize the curator playlists that best fit your song's style, tempo, and audience.",
      card3Title: "Verified Placement Proof",
      card3Text:
        "Every placement is verified through independent APIs. Not a screenshot — real, timestamped proof.",
    },
    roles: {
      tag: "For Curators",
      title: "NOT JUST PLAYLISTS — 9 TYPES OF MUSIC PROFESSIONALS",
      sub: "Get your songs in front of the right ears: every type offers its own opportunity. Qualified feedback pays off across the board.",
      cards: [
        { label: "🎧 Playlist Curator", note: "Chance of playlist add" },
        { label: "📻 Radio", note: "Chance of airplay" },
        { label: "📰 Media / Blog", note: "Chance of press coverage" },
        { label: "💿 Label", note: "Chance of A&R review" },
        { label: "🧑‍💼 Manager", note: "Chance of a meeting" },
        { label: "🎪 Booker", note: "Chance of stage / booking" },
        { label: "🎛️ DJ", note: "Chance of a set play" },
        { label: "🎓 Mentor", note: "Mentorship session" },
        { label: "🎬 Sync Specialist", note: "Film / TV / ads" },
      ],
      cta: "Become a Curator — Apply",
    },
    faq: {
      tag: "FAQ",
      title: "COMMON QUESTIONS",
      q1: "Can I use this without a label?",
      a1: "Yes. MuzikSEO was built for independent artists managing their own careers — no label or PR agency required.",
      q2: "What happens if a curator doesn't respond?",
      a2: "If no response arrives within 72 hours, your credit is refunded automatically. No manual request needed — the system enforces the SLA itself.",
      q3: "What is a credit, and how does it work?",
      a3: "Each submission spends 1 credit. In return you get a guaranteed real listen and a written review of at least 120 characters. Playlist placement is never for sale — curators remain editorially independent.",
      q4: "Which genres are supported?",
      a4: "All music genres. Our matching engine scores the best-fit curators based on your song's style, tempo, and audience.",
    },
    footer: {
      productHeading: "Product",
      seoReport: "SEO Report Card",
      playlistMatch: "Playlist Matching",
      submitSong: "Submit Song",
      proofBoard: "Proof Board",
      league: "Report Card League",
      artistPro: "Artist Pro",
      artistsHeading: "Artists",
      signUp: "Sign Up",
      myCampaigns: "My Campaigns",
      careerBoard: "Career Dashboard",
      releasePlan: "Release Plan",
      howItWorks: "How It Works",
      professionalsHeading: "Professionals",
      becomeCurator: "Become a Curator",
      professionalTypes: "Professional Types",
      inbox: "Inbox",
      chip: "MuzikSEO © 2026",
      trustPart1: "Every week ",
      trustBold1: "340+",
      trustPart2: " placements verified · ",
      trustBold2: "Zero",
      trustPart3: " fake-stream guarantee",
    },
  },
};

export default function HomePage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  return (
    <>
      <nav className={styles.nav}>
        <div className={styles.navWrap}>
          <div className={styles.logo}>MuzikSEO</div>
          <div className={styles.menu}>
            <div className={styles.menuGroup}>
              <button type="button" className={styles.menuGroupBtn}>
                {t.nav.artistsFor}
              </button>
              <div className={styles.dropdown}>
                <a href="#nasil-calisir" className={styles.dropdownLink}>
                  {t.nav.howItWorks}
                </a>
                <Link href="/karne" className={styles.dropdownLink}>
                  {t.nav.artistTips}
                </Link>
                <Link href="/playlistler" className={styles.dropdownLink}>
                  {t.nav.playlistMatch}
                </Link>
                <Link href="/kanit" className={styles.dropdownLink}>
                  {t.nav.proofBoard}
                </Link>
                <Link href="/gonder" className={styles.dropdownLink}>
                  {t.nav.submitSong}
                </Link>
                <Link href="/panel" className={styles.dropdownLink}>
                  {t.nav.arBoard}
                </Link>
                <Link href="/takvim" className={styles.dropdownLink}>
                  {t.nav.releasePlan}
                </Link>
                <Link href="/lig" className={styles.dropdownLink}>
                  {t.nav.league}
                </Link>
                <Link href="/pro" className={styles.dropdownLink}>
                  {t.nav.artistPro}
                </Link>
                <Link href="/linkler" className={styles.dropdownLink}>
                  {t.nav.smartLinks}
                </Link>
                <Link href="/radyo" className={styles.dropdownLink}>
                  {t.nav.radio}
                </Link>
                <Link href="/rapor" className={styles.dropdownLink}>
                  {t.nav.report}
                </Link>
                <Link href="/tanitim" className={styles.dropdownLink}>
                  {t.nav.promoCard}
                </Link>
                <Link href="/sync/yonet" className={styles.dropdownLink}>
                  {t.nav.syncManage}
                </Link>
                <Link href="/reklamlarim" className={styles.dropdownLink}>
                  {t.nav.myAds}
                </Link>
              </div>
            </div>
            <div className={styles.menuGroup}>
              <button type="button" className={styles.menuGroupBtn}>
                {t.nav.curatorsFor}
              </button>
              <div className={styles.dropdown}>
                <Link href="/giris" className={styles.dropdownLink}>
                  {t.nav.becomeCurator}
                </Link>
                <a href="#kuratorler" className={styles.dropdownLink}>
                  {t.nav.curatorTypes}
                </a>
                <Link href="/curator/inbox" className={styles.dropdownLink}>
                  {t.nav.inbox}
                </Link>
                <Link href="/reklam/yonet" className={styles.dropdownLink}>
                  {t.nav.adInventory}
                </Link>
              </div>
            </div>
            <Link href="/reklam" className={styles.menuLink}>
              {t.nav.radioAds}
            </Link>
            <Link href="/admin" className={styles.menuLink}>
              {t.nav.admin}
            </Link>
            <Link href="/giris" className={styles.menuLink}>
              {t.nav.login}
            </Link>
            <LangToggle />
            <Link href="/giris" className="nb-btn">
              {t.nav.join}
            </Link>
          </div>
        </div>
      </nav>

      <header className={styles.hero}>
        <div className={styles.wrap}>
          <span className={styles.heroBadge}>{t.hero.badge}</span>
          <h1 className={styles.heroTitle}>
            {t.hero.titlePart1}
            <span className={styles.heroHighlight}>{t.hero.titleHighlight}</span>
            <br />
            {t.hero.titlePart2}
          </h1>
          <p className={styles.heroSub}>{t.hero.sub}</p>
          <div className={styles.ctaRow}>
            <Link href="/karne" className={`nb-btn ${styles.ctaBtn}`}>
              {t.hero.ctaArtist}
            </Link>
            <Link
              href="/curator/basvuru"
              className={`nb-btn nb-btn--purple ${styles.ctaBtn}`}
            >
              {t.hero.ctaCurator}
            </Link>
          </div>
        </div>
      </header>

      <div className={styles.statsStrip}>
        <div className={styles.statsWrap}>
          <div className={styles.statItem}>
            <strong>{t.stats.slaValue}</strong>
            <span>{t.stats.slaLabel}</span>
          </div>
          <div className={styles.statItem}>
            <strong>{t.stats.typesValue}</strong>
            <span>{t.stats.typesLabel}</span>
          </div>
          <div className={styles.statItem}>
            <strong>{t.stats.verifiedValue}</strong>
            <span>{t.stats.verifiedLabel}</span>
          </div>
        </div>
      </div>

      <section id="nasil-calisir" className={styles.features}>
        <div className={styles.wrap}>
          <span className={styles.sectionTag}>{t.features.tag}</span>
          <h2 className={styles.featuresTitle}>{t.features.title}</h2>
          <div className={styles.featureGrid}>
            <div className={styles.featureCard}>
              <div className={styles.ring}>99</div>
              <h3 className={styles.featureTitle}>{t.features.card1Title}</h3>
              <p className={styles.featureText}>{t.features.card1Text}</p>
            </div>
            <div className={`${styles.featureCard} ${styles.featureCardPurple}`}>
              <div className={`${styles.ring} ${styles.ringPurple}`}>🎯</div>
              <h3 className={styles.featureTitle}>{t.features.card2Title}</h3>
              <p className={styles.featureText}>{t.features.card2Text}</p>
            </div>
            <div className={`${styles.featureCard} ${styles.featureCardBlue}`}>
              <div className={styles.iconBox}>✅</div>
              <h3 className={styles.featureTitle}>{t.features.card3Title}</h3>
              <p className={styles.featureText}>{t.features.card3Text}</p>
            </div>
          </div>
        </div>
      </section>

      <section id="kuratorler" className={styles.roles}>
        <div className={styles.wrap}>
          <span className={styles.sectionTag}>{t.roles.tag}</span>
          <h2 className={styles.rolesTitle}>{t.roles.title}</h2>
          <p className={styles.rolesSub}>{t.roles.sub}</p>
          <div className={styles.roleGrid}>
            {t.roles.cards.map((card) => (
              <div className={styles.roleCard} key={card.label}>
                {card.label}
                <span>{card.note}</span>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 28 }}>
            <Link href="/giris" className="nb-btn nb-btn--purple">
              {t.roles.cta}
            </Link>
          </div>
        </div>
      </section>

      <section className={styles.faq}>
        <div className={styles.wrap}>
          <span className={styles.sectionTag}>{t.faq.tag}</span>
          <h2 className={styles.featuresTitle}>{t.faq.title}</h2>
          <div className={styles.faqList}>
            <details className={styles.faqItem}>
              <summary>{t.faq.q1}</summary>
              <div className={styles.faqAnswer}>{t.faq.a1}</div>
            </details>
            <details className={styles.faqItem}>
              <summary>{t.faq.q2}</summary>
              <div className={styles.faqAnswer}>{t.faq.a2}</div>
            </details>
            <details className={styles.faqItem}>
              <summary>{t.faq.q3}</summary>
              <div className={styles.faqAnswer}>{t.faq.a3}</div>
            </details>
            <details className={styles.faqItem}>
              <summary>{t.faq.q4}</summary>
              <div className={styles.faqAnswer}>{t.faq.a4}</div>
            </details>
          </div>
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.footerCols}>
          <div className={styles.footerCol}>
            <h4>{t.footer.productHeading}</h4>
            <Link href="/karne">{t.footer.seoReport}</Link>
            <Link href="/playlistler">{t.footer.playlistMatch}</Link>
            <Link href="/gonder">{t.footer.submitSong}</Link>
            <Link href="/kanit">{t.footer.proofBoard}</Link>
            <Link href="/lig">{t.footer.league}</Link>
            <Link href="/pro">{t.footer.artistPro}</Link>
            <Link href="/sync">Sync Market</Link>
            <Link href="/label">Label / A&amp;R</Link>
            <Link href="/reklam">
              {locale === "tr" ? "Radyo Reklamı" : "Radio Ads"}
            </Link>
          </div>
          <div className={styles.footerCol}>
            <h4>{t.footer.artistsHeading}</h4>
            <Link href="/giris">{t.footer.signUp}</Link>
            <Link href="/kampanyalar">{t.footer.myCampaigns}</Link>
            <Link href="/panel">{t.footer.careerBoard}</Link>
            <Link href="/takvim">{t.footer.releasePlan}</Link>
            <a href="#nasil-calisir">{t.footer.howItWorks}</a>
          </div>
          <div className={styles.footerCol}>
            <h4>{t.footer.professionalsHeading}</h4>
            <Link href="/giris">{t.footer.becomeCurator}</Link>
            <a href="#kuratorler">{t.footer.professionalTypes}</a>
            <Link href="/curator/inbox">{t.footer.inbox}</Link>
          </div>
        </div>
        <div className={styles.footerWrap}>
          <div className={styles.footerChip}>{t.footer.chip}</div>
          <div className={styles.trust}>
            {t.footer.trustPart1}
            <b>{t.footer.trustBold1}</b>
            {t.footer.trustPart2}
            <b>{t.footer.trustBold2}</b>
            {t.footer.trustPart3}
          </div>
        </div>
      </footer>
    </>
  );
}
