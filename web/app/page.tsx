import Link from "next/link";
import styles from "./page.module.css";

export default function HomePage() {
  return (
    <>
      <nav className={styles.nav}>
        <div className={styles.navWrap}>
          <div className={styles.logo}>MuzikSEO</div>
          <div className={styles.menu}>
            <Link href="/karne" className={styles.menuLink}>
              Karne
            </Link>
            <Link href="/playlistler" className={styles.menuLink}>
              Playlistler
            </Link>
            <Link href="/kanit" className={styles.menuLink}>
              Kanıt
            </Link>
            <Link href="/admin" className={styles.menuLink}>
              Admin
            </Link>
            <a href="#" className={styles.menuLink}>
              Giriş
            </a>
            <Link href="/karne" className="nb-btn">
              Ücretsiz Dene
            </Link>
          </div>
        </div>
      </nav>

      <header className={styles.hero}>
        <div className={styles.wrap}>
          <span className={styles.heroBadge}>
            Türkiye&apos;nin ilk müzik SEO panosu
          </span>
          <h1 className={styles.heroTitle}>
            ŞARKIN <span className={styles.heroHighlight}>HAK ETTİĞİ</span>
            <br />
            GÖRÜNÜRLÜĞE ULAŞSIN
          </h1>
          <p className={styles.heroSub}>
            SEO karnesi, doğru playlist&apos;lere sistemli pitch, kanıtlı
            sonuç. Garanti dinlenme satmıyoruz — kanıt satıyoruz.
          </p>
          <div className={styles.ctaRow}>
            <Link href="/karne" className={`nb-btn ${styles.ctaBtn}`}>
              Sanatçıyım — Karnemi Çıkar
            </Link>
            <Link
              href="/curator/basvuru"
              className={`nb-btn nb-btn--purple ${styles.ctaBtn}`}
            >
              Curator&apos;ım — Listemle Kazan
            </Link>
          </div>
        </div>
      </header>

      <section className={styles.features}>
        <div className={styles.wrap}>
          <span className={styles.sectionTag}>Nasıl Çalışır</span>
          <h2 className={styles.featuresTitle}>
            ÜÇ ADIMDA GÖRÜNÜRLÜKTEN KANITA
          </h2>
          <div className={styles.featureGrid}>
            <div className={styles.featureCard}>
              <div className={styles.ring}>99</div>
              <h3 className={styles.featureTitle}>SEO Karnesi 0-100</h3>
              <p className={styles.featureText}>
                Metadata, dijital varlık, tutarlılık ve anahtar kelime
                başlıklarında şarkının tam karnesini çıkarır, eksikleri net
                şekilde gösteririz.
              </p>
            </div>
            <div className={`${styles.featureCard} ${styles.featureCardPurple}`}>
              <div className={`${styles.ring} ${styles.ringPurple}`}>🎯</div>
              <h3 className={styles.featureTitle}>Playlist Eşleştirme</h3>
              <p className={styles.featureText}>
                Şarkının tarzına, tempouna ve dinleyici kitlene en uygun
                curator listelerini bulur, skorlar ve önceliklendiririz.
              </p>
            </div>
            <div className={`${styles.featureCard} ${styles.featureCardBlue}`}>
              <div className={styles.iconBox}>✅</div>
              <h3 className={styles.featureTitle}>
                Doğrulanmış Yerleşim Kanıtı
              </h3>
              <p className={styles.featureText}>
                Her yerleşim bağımsız API&apos;lerden doğrulanır. Ekran
                görüntüsü değil, gerçek zaman damgalı kanıt sunarız.
              </p>
            </div>
          </div>
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.footerWrap}>
          <div className={styles.footerChip}>MuzikSEO © 2026</div>
          <div className={styles.trust}>
            Her hafta <b>340+</b> yerleşim doğrulanıyor · <b>Sıfır</b> sahte
            dinlenme garantisi
          </div>
        </div>
      </footer>
    </>
  );
}
