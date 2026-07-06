import type { Metadata } from "next";
import { LocaleProvider } from "@/lib/locale";
import "./globals.css";

export const metadata: Metadata = {
  title: "MuzikSEO — Get your music the visibility it deserves",
  description:
    "SEO report card, systematic playlist pitching, verified results. " +
    "We don't sell guaranteed streams — we sell proof.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      {/* suppressHydrationWarning: tarayici eklentileri body'ye attribute
          enjekte edip (or. data-smart-converter-loaded) sahte hydration
          uyarisi uretiyor; sadece bu elementin attribute farklarini susturur. */}
      <body suppressHydrationWarning>
        <LocaleProvider>{children}</LocaleProvider>
      </body>
    </html>
  );
}
