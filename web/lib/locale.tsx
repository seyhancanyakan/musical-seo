"use client";

/** Coklu dil altyapisi — varsayilan EN, Turk ziyaretciye TR.
 *
 *  Tespit sirasi (middleware.ts): msq_loc cookie'si > CDN ulke basligi
 *  (cf-ipcountry / x-vercel-ip-country == TR) > Accept-Language 'tr'.
 *  Sayfalar useLocale() ile okur; metinler sayfa-yerel T sozluklerinde
 *  tutulur (ortak dev sozluk dosyasi yok — sayfalar bagimsiz cevrilir).
 */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Locale = "tr" | "en";

const COOKIE = "msq_loc";

function readCookieLocale(): Locale | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(new RegExp(`(?:^|; )${COOKIE}=(tr|en)`));
  return (m?.[1] as Locale) ?? null;
}

function detectClientLocale(): Locale {
  const fromCookie = readCookieLocale();
  if (fromCookie) return fromCookie;
  if (typeof navigator !== "undefined") {
    const langs = [navigator.language, ...(navigator.languages ?? [])];
    if (langs.some((l) => l?.toLowerCase().startsWith("tr"))) return "tr";
  }
  return "en";
}

const LocaleContext = createContext<{
  locale: Locale;
  setLocale: (l: Locale) => void;
}>({ locale: "en", setLocale: () => {} });

export function LocaleProvider({ children }: { children: ReactNode }) {
  // SSR'da 'en' varsayilir; mount'ta cookie/tarayici dili uygulanir.
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    setLocaleState(detectClientLocale());
  }, []);

  function setLocale(l: Locale) {
    setLocaleState(l);
    if (typeof document !== "undefined") {
      document.cookie = `${COOKIE}=${l}; path=/; max-age=${60 * 60 * 24 * 365}`;
    }
  }

  return (
    <LocaleContext.Provider value={{ locale, setLocale }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  return useContext(LocaleContext);
}

/** Sayfa-yerel sozlukten metin sec: pick(T, locale).key
 *  tr/en ayri tip parametresi: 'as const' sozluklerde literal tipler
 *  birebir eslesmese de calisir (donen tip: birlesim). */
export function pick<A, B>(dict: { tr: A; en: B }, locale: Locale): A | B {
  return dict[locale];
}

/** Dil degistirici — her sayfanin nav'ina eklenebilir. */
export function LangToggle({ className }: { className?: string }) {
  const { locale, setLocale } = useLocale();
  return (
    <span
      className={className}
      style={{ display: "inline-flex", gap: 4, alignItems: "center" }}
    >
      {(["tr", "en"] as Locale[]).map((l) => (
        <button
          key={l}
          type="button"
          onClick={() => setLocale(l)}
          aria-pressed={locale === l}
          style={{
            padding: "2px 8px",
            fontWeight: 800,
            fontSize: 12,
            cursor: "pointer",
            border: "2px solid #111",
            background: locale === l ? "#111" : "transparent",
            color: locale === l ? "#fff" : "#111",
            borderRadius: 6,
          }}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </span>
  );
}
