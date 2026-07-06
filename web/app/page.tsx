import Link from "next/link";
import styles from "./page.module.css";

export default function HomePage() {
  return (
    <>
      <nav className={styles.nav}>
        <div className={styles.navWrap}>
          <div className={styles.logo}>MuzikSEO</div>
          <div className={styles.menu}>
            <div className={styles.menuGroup}>
              <button type="button" className={styles.menuGroupBtn}>
                Sanatçılar İçin ▾
              </button>
              <div className={styles.dropdown}>
                <a href="#nasil-calisir" className={styles.dropdownLink}>
                  Nasıl Çalışır
                </a>
                <Link href="/karne" className={styles.dropdownLink}>
                  Sanatçı İpuçları — SEO Karnesi
                </Link>
                <Link href="/playlistler" className={styles.dropdownLink}>
                  Playlist Eşleştirme
                </Link>
                <Link href="/kanit" className={styles.dropdownLink}>
                  Kanıt Panosu
                </Link>
                <Link href="/gonder" className={styles.dropdownLink}>
                  🎵 Şarkını Şimdi Gönder
                </Link>
                <Link href="/panel" className={styles.dropdownLink}>
                  📊 A&amp;R Kariyer Panosu
                </Link>
                <Link href="/takvim" className={styles.dropdownLink}>
                  🗓️ Yayın Planı
                </Link>
                <Link href="/lig" className={styles.dropdownLink}>
                  🏆 Karne Ligi
                </Link>
                <Link href="/pro" className={styles.dropdownLink}>
                  ⭐ Artist Pro
                </Link>
              </div>
            </div>
            <div className={styles.menuGroup}>
              <button type="button" className={styles.menuGroupBtn}>
                Küratörler İçin ▾
              </button>
              <div className={styles.dropdown}>
                <Link href="/giris" className={styles.dropdownLink}>
                  Küratör Ol
                </Link>
                <a href="#kuratorler" className={styles.dropdownLink}>
                  Küratör &amp; Profesyonel Türleri
                </a>
                <Link href="/curator/inbox" className={styles.dropdownLink}>
                  Gelen Kutusu
                </Link>
              </div>
            </div>
            <Link href="/admin" className={styles.menuLink}>
              Admin
            </Link>
            <Link href="/giris" className={styles.menuLink}>
              Giriş
            </Link>
            <Link href="/giris" className="nb-btn">
              Bize Katıl
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

      <div className={styles.statsStrip}>
        <div className={styles.statsWrap}>
          <div className={styles.statItem}>
            <strong>72 saat</strong>
            <span>garantili yanıt SLA&apos;sı</span>
          </div>
          <div className={styles.statItem}>
            <strong>9 tür</strong>
            <span>küratör &amp; müzik profesyoneli</span>
          </div>
          <div className={styles.statItem}>
            <strong>%100</strong>
            <span>API&apos;den doğrulanmış yerleşim</span>
          </div>
        </div>
      </div>

      <section id="nasil-calisir" className={styles.features}>
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
                Şarkının tarzına, temposuna ve dinleyici kitlene en uygun
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

      <section id="kuratorler" className={styles.roles}>
        <div className={styles.wrap}>
          <span className={styles.sectionTag}>Küratörler İçin</span>
          <h2 className={styles.rolesTitle}>
            SADECE PLAYLIST DEĞİL — 9 TÜR MÜZİK PROFESYONELİ
          </h2>
          <p className={styles.rolesSub}>
            Şarkılar doğru kulaklara gitsin: her tür kendi fırsatını sunar.
            Nitelikli geri bildirim her türde kazandırır.
          </p>
          <div className={styles.roleGrid}>
            <div className={styles.roleCard}>🎧 Playlist Küratörü<span>Listeye ekleme fırsatı</span></div>
            <div className={styles.roleCard}>📻 Radyo<span>Yayında çalma fırsatı</span></div>
            <div className={styles.roleCard}>📰 Medya / Blog<span>Haber &amp; yazı fırsatı</span></div>
            <div className={styles.roleCard}>💿 Label<span>Değerlendirme fırsatı</span></div>
            <div className={styles.roleCard}>🧑‍💼 Menajer<span>Görüşme fırsatı</span></div>
            <div className={styles.roleCard}>🎪 Booker<span>Sahne / booking fırsatı</span></div>
            <div className={styles.roleCard}>🎛️ DJ<span>Sette çalma fırsatı</span></div>
            <div className={styles.roleCard}>🎓 Mentor<span>Mentorluk seansı</span></div>
            <div className={styles.roleCard}>🎬 Sync Uzmanı<span>Film / dizi / reklam</span></div>
          </div>
          <div style={{ marginTop: 28 }}>
            <Link href="/giris" className="nb-btn nb-btn--purple">
              Küratör Ol — Başvur
            </Link>
          </div>
        </div>
      </section>

      <section className={styles.faq}>
        <div className={styles.wrap}>
          <span className={styles.sectionTag}>Sık Sorulanlar</span>
          <h2 className={styles.featuresTitle}>MERAK EDİLENLER</h2>
          <div className={styles.faqList}>
            <details className={styles.faqItem}>
              <summary>Label&apos;sız kullanabilir miyim?</summary>
              <div className={styles.faqAnswer}>
                Evet. MuzikSEO bağımsız ve kendi işini yöneten sanatçılar için
                kuruldu — label ya da PR ajansı şartı yok.
              </div>
            </details>
            <details className={styles.faqItem}>
              <summary>Küratör cevap vermezse ne olur?</summary>
              <div className={styles.faqAnswer}>
                72 saat içinde yanıt gelmezse kredin otomatik iade edilir.
                Elle talep gerekmez; sistem SLA&apos;yı kendisi işletir.
              </div>
            </details>
            <details className={styles.faqItem}>
              <summary>Kredi nedir, nasıl çalışır?</summary>
              <div className={styles.faqAnswer}>
                Her gönderim 1 kredi harcar. Karşılığında gerçek dinleme ve en
                az 120 karakter yazılı değerlendirme garantisi alırsın.
                Playlist&apos;e ekleme satılmaz — küratör editoryal olarak
                bağımsızdır.
              </div>
            </details>
            <details className={styles.faqItem}>
              <summary>Hangi türler destekleniyor?</summary>
              <div className={styles.faqAnswer}>
                Tüm müzik türleri. Eşleştirme motoru şarkının tarzına,
                temposuna ve dinleyici kitlene göre en uygun küratörleri
                skorlar.
              </div>
            </details>
          </div>
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.footerCols}>
          <div className={styles.footerCol}>
            <h4>Ürün</h4>
            <Link href="/karne">SEO Karnesi</Link>
            <Link href="/playlistler">Playlist Eşleştirme</Link>
            <Link href="/gonder">Şarkı Gönder</Link>
            <Link href="/kanit">Kanıt Panosu</Link>
            <Link href="/lig">Karne Ligi</Link>
            <Link href="/pro">Artist Pro</Link>
          </div>
          <div className={styles.footerCol}>
            <h4>Sanatçılar</h4>
            <Link href="/giris">Kayıt Ol</Link>
            <Link href="/kampanyalar">Kampanyalarım</Link>
            <Link href="/panel">Kariyer Panosu</Link>
            <Link href="/takvim">Yayın Planı</Link>
            <a href="#nasil-calisir">Nasıl Çalışır</a>
          </div>
          <div className={styles.footerCol}>
            <h4>Profesyoneller</h4>
            <Link href="/giris">Küratör Ol</Link>
            <a href="#kuratorler">Profesyonel Türleri</a>
            <Link href="/curator/inbox">Gelen Kutusu</Link>
          </div>
        </div>
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
