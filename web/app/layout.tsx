import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MuzikSEO — Şarkın hak ettiği görünürlüğe ulaşsın",
  description:
    "SEO karnesi, doğru playlist'lere sistemli pitch, kanıtlı sonuç. Garanti dinlenme satmıyoruz — kanıt satıyoruz.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr">
      {/* suppressHydrationWarning: tarayici eklentileri body'ye attribute
          enjekte edip (or. data-smart-converter-loaded) sahte hydration
          uyarisi uretiyor; sadece bu elementin attribute farklarini susturur. */}
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
