/** Tier-6 blog index — SERVER component (statik SEO icerigi, "use client" YOK).
 *  Tum yazilari neo-brutal kart izgarasinda listeler; her kart /blog/{slug}'a
 *  baglanir. Icerik blogData.ts'ten gelir — veri dosyasi yazilmaz. */

import type { Metadata } from "next";
import Link from "next/link";
import { BLOG_POSTS } from "@/lib/blogData";
import styles from "./page.module.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3100";

export const metadata: Metadata = {
  title: "Songdeck Blog — Music SEO, Distribution & Playlist Guides",
  description:
    "Practical, no-hype guides for independent artists: Spotify editorial pitching, ISRC and metadata, fake-playlist detection, music SEO, copyright, and release timing.",
  alternates: { canonical: `${SITE_URL}/blog` },
  openGraph: {
    title: "Songdeck Blog — Music SEO, Distribution & Playlist Guides",
    description:
      "Practical, no-hype guides for independent artists: Spotify pitching, ISRC and metadata, fake-playlist detection, music SEO, copyright, and release timing.",
    url: `${SITE_URL}/blog`,
    type: "website",
  },
};

export default function BlogIndexPage() {
  return (
    <>
      <main className={styles.wrap}>
        <nav className={styles.breadcrumb}>
          <Link href="/">Songdeck</Link> / Blog
        </nav>

        <header className={styles.header}>
          <h1 className={styles.h1}>The Songdeck Blog</h1>
          <p className={styles.lede}>
            Practical, no-hype guides for independent artists — Spotify editorial
            pitching, ISRC and metadata, fake-playlist detection, music SEO,
            copyright, and release timing. No shortcuts, just what actually works.
          </p>
        </header>

        <div className={styles.grid}>
          {BLOG_POSTS.map((post, i) => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}`}
              className={styles.card}
            >
              <div className={styles.cardMeta}>
                <span className="nb-pill nb-pill--blue">Guide</span>
                <span className={styles.cardNum}>
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="nb-chip">{post.readingMinutes} min read</span>
              </div>
              <h2 className={styles.cardTitle}>{post.title}</h2>
              <p className={styles.cardExcerpt}>{post.excerpt}</p>
              <span className={styles.cardCta}>Read guide →</span>
            </Link>
          ))}
        </div>
      </main>
    </>
  );
}
