/** Dinamik sitemap — Next.js App Router ozel dosyasi (server-side, "use client"
 *  YOK). Statik rotalar + programatik sanatci sayfalarini (seo_pages.db)
 *  birlestirir. Backend erisilemezse (agdown/hata) sadece statik rotalari
 *  doner — asla firlatmaz (bkz. docs/PROGRAMATIK_SEO_WORKFLOW.md §10). */

import type { MetadataRoute } from "next";
import { getArtistSitemap } from "@/lib/api";
import { COMPARE_SLUGS } from "@/lib/compareData";
import { BLOG_SLUGS } from "@/lib/blogData";

export const revalidate = 3600;

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3100";

// Ana sayfa + 4 nis arac sayfasi (bkz. SiteHeader toolLinks).
const STATIC_PATHS = [
  "/",
  "/sahte-playlist",
  "/attribution",
  "/yayin-zamanlamasi",
  "/cover-avcisi",
  "/blog",
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticEntries: MetadataRoute.Sitemap = STATIC_PATHS.map((path) => ({
    url: `${SITE_URL}${path}`,
    lastModified: new Date(),
  }));

  const compareEntries: MetadataRoute.Sitemap = COMPARE_SLUGS.map((slug) => ({
    url: `${SITE_URL}/compare/${slug}`,
    lastModified: new Date(),
  }));

  const blogEntries: MetadataRoute.Sitemap = BLOG_SLUGS.map((slug) => ({
    url: `${SITE_URL}/blog/${slug}`,
    lastModified: new Date(),
  }));

  const artists = await getArtistSitemap();
  if (!artists || artists.length === 0) {
    return [...staticEntries, ...compareEntries, ...blogEntries];
  }

  const artistEntries: MetadataRoute.Sitemap = artists
    .filter((entry) => Boolean(entry?.slug))
    .map((entry) => ({
      url: `${SITE_URL}/artist/${encodeURIComponent(entry.slug)}`,
      lastModified: entry.last_refreshed_at ? new Date(entry.last_refreshed_at) : new Date(),
    }));

  return [...staticEntries, ...compareEntries, ...blogEntries, ...artistEntries];
}
