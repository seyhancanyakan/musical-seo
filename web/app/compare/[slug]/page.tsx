/** Tier-1 karsilastirma sayfalari — SERVER component (statik SEO icerigi,
 *  "use client" YOK). generateStaticParams tum 50 slug'i onceden uretir;
 *  generateMetadata baslik/aciklamayi verir. Article + FAQPage JSON-LD enjekte
 *  edilir. Icerik compareData.ts'ten gelir — veri dosyasi yazilmaz. */

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { getComparePage, COMPARE_SLUGS } from "@/lib/compareData";
import styles from "./page.module.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3100";

export async function generateStaticParams(): Promise<{ slug: string }[]> {
  return COMPARE_SLUGS.map((slug) => ({ slug }));
}

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> },
): Promise<Metadata> {
  const { slug } = await params;
  const page = getComparePage(slug);
  if (!page) return { title: "Not found" };
  return {
    title: page.title,
    description: page.metaDescription,
    alternates: { canonical: `${SITE_URL}/compare/${page.slug}` },
    openGraph: {
      title: page.title,
      description: page.metaDescription,
      url: `${SITE_URL}/compare/${page.slug}`,
      type: "article",
    },
  };
}

export default async function ComparePageRoute(
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params;
  const page = getComparePage(slug);
  if (!page) notFound();

  const articleLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: page.h1,
    description: page.metaDescription,
    url: `${SITE_URL}/compare/${page.slug}`,
    author: { "@type": "Organization", name: "Sozy Echo" },
    publisher: { "@type": "Organization", name: "Sozy Echo" },
  };

  const faqLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: page.faq.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };

  const hasTable =
    Array.isArray(page.comparisonTable) && page.comparisonTable.length > 0;
  const leftName = page.leftName ?? "Left";
  const rightName = page.rightName ?? "Right";

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqLd) }}
      />

      <article className={styles.wrap}>
        <nav className={styles.breadcrumb}>
          <Link href="/">Sozy Echo</Link> / <Link href="/compare">Compare</Link> /{" "}
          {page.slug}
        </nav>

        <h1 className={styles.h1}>{page.h1}</h1>

        {page.leftName && page.rightName && (
          <div className={styles.versus}>
            <span className="nb-pill nb-pill--blue">{page.leftName}</span>
            <span className="nb-pill nb-pill--red">vs</span>
            <span className="nb-pill nb-pill--purple">{page.rightName}</span>
          </div>
        )}

        <p className={styles.intro}>{page.intro}</p>

        {hasTable && (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>{leftName}</th>
                  <th>{rightName}</th>
                </tr>
              </thead>
              <tbody>
                {page.comparisonTable!.map((row, i) => (
                  <tr key={i}>
                    <th scope="row">{row.feature}</th>
                    <td>{row.left}</td>
                    <td>{row.right}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {page.sections.map((s, i) => (
          <section key={i} className={styles.section}>
            <h2 className={styles.sectionHeading}>{s.heading}</h2>
            <p className={styles.sectionBody}>{s.body}</p>
          </section>
        ))}

        <div className={styles.verdict}>
          <div className={styles.verdictLabel}>Verdict</div>
          <p className={styles.verdictBody}>{page.verdict}</p>
        </div>

        <section className={styles.faq}>
          <h2 className={styles.faqTitle}>Frequently Asked Questions</h2>
          {page.faq.map((f, i) => (
            <div key={i} className={styles.faqItem}>
              <div className={styles.faqQ}>{f.q}</div>
              <div className={styles.faqA}>{f.a}</div>
            </div>
          ))}
        </section>

        <div className={styles.cta}>
          <div className={styles.ctaLabel}>Try Sozy Echo Free</div>
          <p className={styles.ctaBody}>{page.cta}</p>
          <div className={styles.ctaBtns}>
            <Link href="/giris" className="nb-btn nb-btn--green">
              Sign Up Free
            </Link>
            <Link href="/sahte-playlist" className="nb-btn nb-btn--outline">
              Fake Playlist Checker
            </Link>
            <Link href="/cover-avcisi" className="nb-btn nb-btn--outline">
              Cover Hunter
            </Link>
          </div>
        </div>
      </article>
    </>
  );
}
