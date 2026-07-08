/** Tier-6 blog yazi sayfasi — SERVER component (statik SEO icerigi, "use client"
 *  YOK). generateStaticParams tum slug'lari onceden uretir; generateMetadata
 *  baslik/aciklamayi verir. Article + FAQPage JSON-LD enjekte edilir. Icerik
 *  blogData.ts'ten gelir — veri dosyasi yazilmaz. */

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import SiteHeader from "@/components/SiteHeader";
import { getBlogPost, BLOG_SLUGS } from "@/lib/blogData";
import styles from "./page.module.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3100";

// Her yazi icin CTA'da gosterilecek ilgili arac (link + etiket). Varsayilan:
// SEO Karnesi. Icerige gore en alakali mevcut arac rotasina eslesir.
const TOOL_LINKS: Record<string, { href: string; label: string }> = {
  "how-to-get-on-spotify-editorial-playlists": { href: "/karne", label: "SEO Report Card" },
  "what-is-isrc-and-why-it-matters": { href: "/karne", label: "SEO Report Card" },
  "how-to-check-if-a-spotify-playlist-is-fake": { href: "/sahte-playlist", label: "Fake Playlist Checker" },
  "spotify-bot-detection-explained": { href: "/sahte-playlist", label: "Fake Playlist Checker" },
  "music-seo-guide-2026": { href: "/karne", label: "SEO Report Card" },
  "how-to-copyright-your-music": { href: "/karne", label: "SEO Report Card" },
  "how-to-find-unauthorized-covers-of-your-song": { href: "/cover-avcisi", label: "Cover Hunter" },
  "spotify-vs-apple-music-for-artists": { href: "/sahte-playlist", label: "Fake Playlist Checker" },
  "how-music-playlist-payola-works": { href: "/sahte-playlist", label: "Fake Playlist Checker" },
  "best-time-to-release-a-song": { href: "/yayin-zamanlamasi", label: "Release Timing" },
  "how-to-get-more-spotify-monthly-listeners": { href: "/karne", label: "SEO Report Card" },
  "music-metadata-checklist-before-release": { href: "/karne", label: "SEO Report Card" },
};

const DEFAULT_TOOL = { href: "/karne", label: "SEO Report Card" };

export function generateStaticParams(): { slug: string }[] {
  return BLOG_SLUGS.map((slug) => ({ slug }));
}

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> },
): Promise<Metadata> {
  const { slug } = await params;
  const post = getBlogPost(slug);
  if (!post) return { title: "Not found" };
  return {
    title: post.title,
    description: post.metaDescription,
    alternates: { canonical: `${SITE_URL}/blog/${post.slug}` },
    openGraph: {
      title: post.title,
      description: post.metaDescription,
      url: `${SITE_URL}/blog/${post.slug}`,
      type: "article",
    },
  };
}

export default async function BlogPostRoute(
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params;
  const post = getBlogPost(slug);
  if (!post) notFound();

  const tool = TOOL_LINKS[post.slug] ?? DEFAULT_TOOL;

  const articleLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.h1,
    description: post.metaDescription,
    url: `${SITE_URL}/blog/${post.slug}`,
    author: { "@type": "Organization", name: "Songdeck" },
    publisher: { "@type": "Organization", name: "Songdeck" },
  };

  const faqLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: post.faq.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };

  return (
    <>
      <SiteHeader />
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
          <Link href="/">Songdeck</Link> / <Link href="/blog">Blog</Link> /{" "}
          {post.slug}
        </nav>

        <h1 className={styles.h1}>{post.h1}</h1>

        <div className={styles.meta}>
          <span className="nb-pill nb-pill--blue">Guide</span>
          <span className="nb-chip">{post.readingMinutes} min read</span>
        </div>

        <p className={styles.excerpt}>{post.excerpt}</p>

        {post.sections.map((s, i) => (
          <section key={i} className={styles.section}>
            <h2 className={styles.sectionHeading}>{s.heading}</h2>
            <div className={styles.sectionBody}>
              {s.body.split("\n\n").map((para, j) => (
                <p key={j}>{para}</p>
              ))}
            </div>
          </section>
        ))}

        <section className={styles.faq}>
          <h2 className={styles.faqTitle}>Frequently Asked Questions</h2>
          {post.faq.map((f, i) => (
            <div key={i} className={styles.faqItem}>
              <div className={styles.faqQ}>{f.q}</div>
              <div className={styles.faqA}>{f.a}</div>
            </div>
          ))}
        </section>

        <div className={styles.cta}>
          <div className={styles.ctaLabel}>Try Songdeck Free</div>
          <p className={styles.ctaBody}>{post.cta}</p>
          <div className={styles.ctaBtns}>
            <Link href="/giris" className="nb-btn nb-btn--green">
              Sign Up Free
            </Link>
            <Link href={tool.href} className="nb-btn nb-btn--outline">
              {tool.label}
            </Link>
          </div>
        </div>
      </article>
    </>
  );
}
