import { NextResponse, type NextRequest } from "next/server";

/** Ilk ziyarette dil cookie'si ata: TR ip/tarayici -> tr, digerleri -> en.
 *
 *  Ulke tespiti CDN basliklarindan (Cloudflare: cf-ipcountry, Vercel:
 *  x-vercel-ip-country); CDN yoksa Accept-Language'a duser. Kullanici
 *  LangToggle ile secim yapinca cookie onu ezer — middleware dokunmaz.
 */

const COOKIE = "msq_loc";

export function middleware(request: NextRequest) {
  if (request.cookies.has(COOKIE)) return NextResponse.next();

  const country = (
    request.headers.get("cf-ipcountry") ??
    request.headers.get("x-vercel-ip-country") ??
    ""
  ).toUpperCase();
  const acceptLang = request.headers.get("accept-language") ?? "";
  const isTurkish =
    country === "TR" || acceptLang.toLowerCase().split(",")[0]?.startsWith("tr");

  const response = NextResponse.next();
  response.cookies.set(COOKIE, isTurkish ? "tr" : "en", {
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });
  return response;
}

export const config = {
  // Statik varliklara dokunma; sadece sayfa istekleri.
  matcher: ["/((?!_next|favicon.ico|.*\\.).*)"],
};
