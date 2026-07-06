"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  createPromo,
  getMe,
  getToken,
  myPromos,
  openPromoSvg,
  type PromoAsset,
  type User,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type PromoStyle = "dark" | "light";

const T = {
  tr: {
    gateTitle: "Giriş gerekli",
    gateText: "Tanıtım kartı oluşturmak için sanatçı hesabınla giriş yap.",
    gateLink: "Giriş / Kayıt",
    creditsWord: "kredi",
    heading: "Animasyonlu Tanıtım Kartı",
    promise:
      "Story boyutunda animasyonlu tanıtım kartı — skorun + doğrulanmış yerleşimlerinle. 1 kredi (Pro ücretsiz).",
    songLabel: "Şarkı",
    songPlaceholder: '"Sanatçı - Şarkı" (ör. Seyhan Canyakan - Serenity)',
    styleLabel: "Stil",
    styleDark: "Karanlık",
    styleLight: "Açık",
    createBtn: "Kart Oluştur",
    busy: "...",
    songFormatError:
      'Şarkıyı "Sanatçı - Şarkı" formatında yaz (ör. Seyhan Canyakan - Serenity).',
    createError: "Kart oluşturulamadı — kredin yetersiz olabilir, tekrar dene.",
    loading: "Yükleniyor...",
    myCardsTitle: "Kartlarım",
    emptyCards: "Henüz kart oluşturmadın — yukarıdaki formla ilkini oluştur.",
    viewBtn: "Görüntüle",
    previewMissing: "Önizleme yükleniyor...",
    createdAt: (d: string) => `Oluşturuldu: ${d}`,
    dateLocale: "tr-TR",
  },
  en: {
    gateTitle: "Login required",
    gateText: "Log in with your artist account to create a promo card.",
    gateLink: "Login / Sign Up",
    creditsWord: "credits",
    heading: "Animated Promo Card",
    promise:
      "A story-sized animated promo card — with your score and verified placements. 1 credit (free on Pro).",
    songLabel: "Song",
    songPlaceholder: '"Artist - Title" (e.g. Seyhan Canyakan - Serenity)',
    styleLabel: "Style",
    styleDark: "Dark",
    styleLight: "Light",
    createBtn: "Create Card",
    busy: "...",
    songFormatError:
      'Write your song as "Artist - Title" (e.g. Seyhan Canyakan - Serenity).',
    createError: "Couldn't create the card — you may be low on credits, try again.",
    loading: "Loading...",
    myCardsTitle: "My Cards",
    emptyCards: "You haven't created any cards yet — make your first one above.",
    viewBtn: "View",
    previewMissing: "Loading preview...",
    createdAt: (d: string) => `Created: ${d}`,
    dateLocale: "en-US",
  },
} as const;

/** "Sanatçı - Şarkı" ayrıştırıcısı — gonder/page.tsx'teki desenle aynı, bağımsız kopya. */
function parseSongText(raw: string): { artist: string; title: string } | null {
  const trimmed = raw.trim();
  if (!trimmed.includes(" - ")) return null;
  const [artist, ...rest] = trimmed.split(" - ");
  const title = rest.join(" - ").trim();
  if (!artist.trim() || !title) return null;
  return { artist: artist.trim(), title };
}

/** Animasyonlu tanitim karti — createPromo ile SVG uretir, myPromos ile listeler.
 *  Onizlemeler auth gerektirdigi icin blob URL olarak cekilir (img src + yeni sekme). */
export default function TanitimPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [loading, setLoading] = useState(true);

  const [song, setSong] = useState("");
  const [style, setStyle] = useState<PromoStyle>("dark");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const [promos, setPromos] = useState<PromoAsset[]>([]);
  const [previewMap, setPreviewMap] = useState<Record<string, string | null>>({});
  const [viewingToken, setViewingToken] = useState<string | null>(null);

  async function loadPreviews(items: PromoAsset[]) {
    const pairs = await Promise.all(
      items.map(async (p) => [p.token, await openPromoSvg(p.token)] as const)
    );
    setPreviewMap((prev) => {
      const next = { ...prev };
      for (const [token, url] of pairs) next[token] = url;
      return next;
    });
  }

  useEffect(() => {
    (async () => {
      if (getToken()) {
        const me = await getMe();
        if (me && me.user.role === "artist") {
          setUser(me.user);
          const result = await myPromos();
          if (result) {
            setPromos(result.items);
            loadPreviews(result.items);
          }
        }
      }
      setChecked(true);
      setLoading(false);
    })();
  }, []);

  async function handleCreate() {
    setError("");
    const parsed = parseSongText(song);
    if (!parsed) {
      setError(t.songFormatError);
      return;
    }
    setCreating(true);
    const asset = await createPromo(parsed.artist, parsed.title, style);
    setCreating(false);
    if (!asset) {
      setError(t.createError);
      return;
    }
    setPromos((prev) => [asset, ...prev]);
    loadPreviews([asset]);
    const me = await getMe();
    if (me) setUser(me.user);
  }

  async function handleView(token: string) {
    setViewingToken(token);
    const cached = previewMap[token];
    const url = cached ?? (await openPromoSvg(token));
    setViewingToken(null);
    if (url) window.open(url, "_blank");
  }

  if (checked && !user) {
    return (
      <div className={styles.gate}>
        <div className="nb-card" style={{ padding: 28, maxWidth: 460 }}>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
            <LangToggle />
          </div>
          <h2 className="nb-h">{t.gateTitle}</h2>
          <p className={styles.gateText}>{t.gateText}</p>
          <Link href="/giris" className="nb-btn">{t.gateLink}</Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" className={styles.logo}>MuzikSEO</Link>
          <LangToggle />
        </div>
        {user && (
          <div className={styles.wallet}>💳 {user.credits} {t.creditsWord} · {user.name}</div>
        )}
      </div>

      <h1 className="nb-h">{t.heading}</h1>
      <p className={styles.promise}>{t.promise}</p>

      <div className={`nb-card ${styles.formCard}`}>
        <div className={styles.formField}>
          <label className={styles.fieldLabel} htmlFor="promo-song">{t.songLabel}</label>
          <input
            id="promo-song"
            className="nb-input"
            placeholder={t.songPlaceholder}
            value={song}
            onChange={(e) => setSong(e.target.value)}
          />
        </div>

        <div className={styles.formField}>
          <span className={styles.fieldLabel}>{t.styleLabel}</span>
          <div className={styles.styleRow}>
            <button
              type="button"
              className={`${styles.styleBtn} ${styles.styleBtnDark} ${
                style === "dark" ? styles.styleBtnActive : ""
              }`}
              aria-pressed={style === "dark"}
              onClick={() => setStyle("dark")}
            >
              {t.styleDark}
            </button>
            <button
              type="button"
              className={`${styles.styleBtn} ${styles.styleBtnLight} ${
                style === "light" ? styles.styleBtnActive : ""
              }`}
              aria-pressed={style === "light"}
              onClick={() => setStyle("light")}
            >
              {t.styleLight}
            </button>
          </div>
        </div>

        <button
          type="button"
          className="nb-btn nb-btn--purple"
          disabled={creating}
          onClick={handleCreate}
        >
          {creating ? t.busy : t.createBtn}
        </button>

        {error && <div className={styles.error}>{error}</div>}
      </div>

      <h2 className="nb-h" style={{ fontSize: 18, marginTop: 8 }}>{t.myCardsTitle}</h2>

      {loading && <div className={styles.empty}>{t.loading}</div>}

      {!loading && promos.length === 0 && (
        <div className={styles.empty}>{t.emptyCards}</div>
      )}

      <div className={styles.cardGrid}>
        {promos.map((p) => {
          const preview = previewMap[p.token];
          return (
            <div key={p.id} className={`nb-card ${styles.promoCard}`}>
              <div className={`${styles.previewBox} ${
                p.style === "dark" ? styles.previewDark : styles.previewLight
              }`}>
                {preview ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={preview} alt={`${p.artist} — ${p.title}`} className={styles.previewImg} />
                ) : (
                  <span className={styles.previewLoading}>{t.previewMissing}</span>
                )}
              </div>
              <div className={styles.promoInfo}>
                <div className={styles.promoTitle}>{p.artist} — {p.title}</div>
                <div className={styles.promoMeta}>
                  {t.createdAt(new Date(p.created_at).toLocaleString(t.dateLocale))}
                </div>
              </div>
              <button
                type="button"
                className="nb-btn"
                disabled={viewingToken === p.token}
                onClick={() => handleView(p.token)}
              >
                {viewingToken === p.token ? t.busy : t.viewBtn}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
