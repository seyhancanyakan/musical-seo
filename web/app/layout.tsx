import type { Metadata } from "next";
import { cookies } from "next/headers";
import { LocaleProvider } from "@/lib/locale";
import "./globals.css";

export const metadata: Metadata = {
  title: "Songdeck — Get your music the visibility it deserves",
  description:
    "SEO report card, systematic playlist pitching, verified results. " +
    "We don't sell guaranteed streams — we sell proof.",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // lang'i aktif dile gore ayarla: text-transform:uppercase Turkce casing
  // uygulasin (i -> I degil i -> İ). Cookie middleware/LangToggle ile set edilir.
  const store = await cookies();
  const lang = store.get("msq_loc")?.value === "tr" ? "tr" : "en";
  return (
    <html lang={lang}>
      {/* suppressHydrationWarning: tarayici eklentileri body'ye attribute
          enjekte edip (or. data-smart-converter-loaded) sahte hydration
          uyarisi uretiyor; sadece bu elementin attribute farklarini susturur. */}
      <body suppressHydrationWarning>
        <LocaleProvider>{children}</LocaleProvider>
      </body>
    </html>
  );
}
