import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { LocaleProvider } from "@/lib/locale";
import SiteHeader from "@/components/SiteHeader";
import "./globals.css";

export const metadata: Metadata = {
  title: "Songdeck — Get your music the visibility it deserves",
  description:
    "SEO report card, systematic playlist pitching, verified results. " +
    "We don't sell guaranteed streams — we sell proof.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

// Bu layout zaten cookies() kullandigi icin dogal olarak dinamik, ama Next
// 15.5.x bunu ORTULU olarak cikarinca build sirasinda "statik govde"
// (partial prerender) denemesi yapiyor ve bu adimda dahili bir metadata/
// viewport cozumleme hatasina takiliyor: "Cannot read properties of
// undefined (reading 'length')" (tum route'larda ayni hata, app kodundan
// bagimsiz — bilinen Next.js dahili sorunu). `dynamic` acikca "force-dynamic"
// olarak belirtilince Next bu statik govde denemesini tamamen atliyor ve
// build hatasiz tamamlaniyor. Runtime davranisi degismiyor: rota zaten
// cookies() nedeniyle her istekte sunucuda render ediliyordu.
export const dynamic = "force-dynamic";

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
        <LocaleProvider>
          <SiteHeader />
          {children}
        </LocaleProvider>
      </body>
    </html>
  );
}
