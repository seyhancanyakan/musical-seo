"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  affiliateClick,
  createSmartLink,
  exportLinkFans,
  getMe,
  getToken,
  linkFans,
  listAffiliates,
  mySmartLinks,
  type AffiliatePartner,
  type LinkFan,
  type SmartLink,
  type User,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

const PLATFORM_KEYS = ["spotify", "deezer", "youtube", "apple", "other"] as const;
type PlatformKey = (typeof PLATFORM_KEYS)[number];

const EMPTY_PLATFORM_URLS: Record<PlatformKey, string> = {
  spotify: "",
  deezer: "",
  youtube: "",
  apple: "",
  other: "",
};

const T = {
  tr: {
    gateTitle: "Giriş gerekli",
    gateText: "Akıllı link oluşturmak için sanatçı hesabınla giriş yap.",
    gateLink: "Giriş / Kayıt",
    walletLine: (credits: number, name: string) => `💳 ${credits} kredi · ${name}`,
    heading: "Akıllı Linklerin",
    promise:
      "Tüm platformları tek bağlantıda topla; görüntülenme, tıklama ve hayran verilerini takip et.",
    createTitle: "Yeni Akıllı Link",
    songPlaceholder: 'Şarkın: "Sanatçı - Şarkı"',
    platformLabels: {
      spotify: "Spotify",
      deezer: "Deezer",
      youtube: "YouTube",
      apple: "Apple Music",
      other: "Diğer",
    } as Record<PlatformKey, string>,
    urlPlaceholder: (label: string) => `${label} linki`,
    releaseDateLabel: "Çıkış tarihi (opsiyonel)",
    presaveHint: "🔜 Bu link ön-kayıt (presave) modunda oluşturulacak",
    createBtn: "Oluştur",
    busy: "...",
    errSongFormat: 'Şarkıyı "Sanatçı - Şarkı" formatında yaz.',
    errNoLink: "En az bir platform linki gir.",
    errCreateFailed: "Link oluşturulamadı — bilgileri kontrol et.",
    listTitle: "Linklerin",
    loading: "Yükleniyor...",
    emptyLinks: "Henüz akıllı link oluşturmadın.",
    viewsLabel: "görüntüleme",
    fanCountLabel: (n: number) => `${n} fan`,
    copyBtn: "Kopyala",
    copiedBtn: "Kopyalandı ✓",
    fansBtn: "Fanları Gör",
    fansHideBtn: "Fanları Gizle",
    fanEmailCol: "E-posta",
    fanDateCol: "Kayıt Tarihi",
    fanConsentCol: "Onay",
    noFans: "Henüz fan yok.",
    exportBtn: "CSV İndir",
    exportNote: (isPro: boolean) => (isPro ? "Pro: ücretsiz" : "2 kredi"),
    exportFailed: "Dışa aktarılamadı — tekrar dene.",
    presaveBadge: "Ön-kayıt",
    affiliatesTitle: "Ortaklar",
    affiliatesPromise: "Önerdiğimiz araçlar — tıkla, ortağın sayfasına git.",
    visitBtn: "Ziyaret Et",
    dateLocale: "tr-TR",
  },
  en: {
    gateTitle: "Login required",
    gateText: "Log in with your artist account to create a smart link.",
    gateLink: "Login / Sign Up",
    walletLine: (credits: number, name: string) => `💳 ${credits} credits · ${name}`,
    heading: "Your Smart Links",
    promise:
      "Gather every platform into one link; track views, clicks, and fan data.",
    createTitle: "New Smart Link",
    songPlaceholder: 'Your song: "Artist - Song"',
    platformLabels: {
      spotify: "Spotify",
      deezer: "Deezer",
      youtube: "YouTube",
      apple: "Apple Music",
      other: "Other",
    } as Record<PlatformKey, string>,
    urlPlaceholder: (label: string) => `${label} link`,
    releaseDateLabel: "Release date (optional)",
    presaveHint: "🔜 This link will be created in pre-save mode",
    createBtn: "Create",
    busy: "...",
    errSongFormat: 'Write your song as "Artist - Song".',
    errNoLink: "Enter at least one platform link.",
    errCreateFailed: "Couldn't create the link — check the details.",
    listTitle: "Your Links",
    loading: "Loading...",
    emptyLinks: "You haven't created a smart link yet.",
    viewsLabel: "views",
    fanCountLabel: (n: number) => `${n} fans`,
    copyBtn: "Copy",
    copiedBtn: "Copied ✓",
    fansBtn: "View Fans",
    fansHideBtn: "Hide Fans",
    fanEmailCol: "Email",
    fanDateCol: "Signed Up",
    fanConsentCol: "Consent",
    noFans: "No fans yet.",
    exportBtn: "Download CSV",
    exportNote: (isPro: boolean) => (isPro ? "Pro: free" : "2 credits"),
    exportFailed: "Couldn't export — try again.",
    presaveBadge: "Pre-save",
    affiliatesTitle: "Affiliates",
    affiliatesPromise: "Tools we recommend — click to visit the partner's page.",
    visitBtn: "Visit",
    dateLocale: "en-US",
  },
} as const;

function parseSong(raw: string): { artist: string; title: string } | null {
  const trimmed = raw.trim();
  if (!trimmed.includes(" - ")) return null;
  const [artist, ...rest] = trimmed.split(" - ");
  const title = rest.join(" - ").trim();
  if (!artist.trim() || !title) return null;
  return { artist: artist.trim(), title };
}

function isFutureDateOnly(dateStr: string): boolean {
  if (!dateStr) return false;
  return new Date(dateStr).getTime() > Date.now();
}

function csvEscape(value: string): string {
  if (value.includes(",") || value.includes('"') || value.includes("\n")) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function fansToCsv(fans: LinkFan[]): string {
  const header = "email,created_at,consent";
  const rows = fans.map(
    (f) => `${csvEscape(f.email)},${csvEscape(f.created_at)},${f.consent}`
  );
  return [header, ...rows].join("\n");
}

function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Sanatci akilli link yonetimi: olusturma + liste (goruntulenme/tiklama/fan) +
 *  fan disa aktarimi + ortaklik vitrini. */
export default function LinklerPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [links, setLinks] = useState<SmartLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [origin, setOrigin] = useState("");

  // Olusturma formu
  const [song, setSong] = useState("");
  const [platformUrls, setPlatformUrls] = useState<Record<PlatformKey, string>>(
    EMPTY_PLATFORM_URLS
  );
  const [releaseDate, setReleaseDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Fan paneli (linkId -> fan listesi, ilk yuklemede tumu cekilir)
  const [fansMap, setFansMap] = useState<Record<number, LinkFan[]>>({});
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // CSV disa aktarimi
  const [exportingId, setExportingId] = useState<number | null>(null);
  const [exportMsg, setExportMsg] = useState<Record<number, string>>({});

  // Kopyalama geri bildirimi
  const [copiedSlug, setCopiedSlug] = useState<string | null>(null);

  // Ortaklar
  const [affiliates, setAffiliates] = useState<AffiliatePartner[]>([]);
  const [affiliateBusyKey, setAffiliateBusyKey] = useState<string | null>(null);

  useEffect(() => {
    setOrigin(window.location.origin);
    (async () => {
      if (getToken()) {
        const me = await getMe();
        if (me) {
          setUser(me.user);
          const list = await mySmartLinks();
          if (list) {
            setLinks(list);
            const fansResults = await Promise.all(list.map((l) => linkFans(l.id)));
            const map: Record<number, LinkFan[]> = {};
            list.forEach((l, i) => {
              const fans = fansResults[i];
              if (fans) map[l.id] = fans;
            });
            setFansMap(map);
          }
        }
      }
      setChecked(true);
      setLoading(false);
      const aff = await listAffiliates();
      if (aff) setAffiliates(aff);
    })();
  }, []);

  const isPro = !!user?.pro_until && new Date(user.pro_until).getTime() > Date.now();
  const showPresaveHint = isFutureDateOnly(releaseDate);

  function publicUrl(slug: string): string {
    return `${origin}/l/${slug}`;
  }

  async function handleCopy(slug: string) {
    try {
      await navigator.clipboard.writeText(publicUrl(slug));
      setCopiedSlug(slug);
      setTimeout(() => setCopiedSlug((prev) => (prev === slug ? null : prev)), 1500);
    } catch {
      // Panoya erisim engellenmisse sessizce yoksay.
    }
  }

  function toggleFans(linkId: number) {
    setExpandedId((prev) => (prev === linkId ? null : linkId));
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    const parsed = parseSong(song);
    if (!parsed) {
      setError(t.errSongFormat);
      return;
    }
    const linksPayload: Record<string, string> = {};
    PLATFORM_KEYS.forEach((key) => {
      const value = platformUrls[key].trim();
      if (value) linksPayload[key] = value;
    });
    if (Object.keys(linksPayload).length === 0) {
      setError(t.errNoLink);
      return;
    }
    setBusy(true);
    const created = await createSmartLink({
      artist: parsed.artist,
      title: parsed.title,
      links: linksPayload,
      release_date: releaseDate || undefined,
    });
    setBusy(false);
    if (!created) {
      setError(t.errCreateFailed);
      return;
    }
    setLinks((prev) => [created, ...prev]);
    setFansMap((prev) => ({ ...prev, [created.id]: [] }));
    setSong("");
    setPlatformUrls(EMPTY_PLATFORM_URLS);
    setReleaseDate("");
  }

  async function handleExportCsv(link: SmartLink) {
    setExportingId(link.id);
    setExportMsg((prev) => ({ ...prev, [link.id]: "" }));
    const fans = await exportLinkFans(link.id);
    setExportingId(null);
    if (!fans) {
      setExportMsg((prev) => ({ ...prev, [link.id]: t.exportFailed }));
      return;
    }
    setFansMap((prev) => ({ ...prev, [link.id]: fans }));
    downloadCsv(`${link.slug}-fans.csv`, fansToCsv(fans));
  }

  async function handleAffiliateClick(key: string) {
    setAffiliateBusyKey(key);
    const res = await affiliateClick(key);
    setAffiliateBusyKey(null);
    if (res?.url) window.open(res.url, "_blank", "noopener,noreferrer");
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
          <div className={styles.wallet}>{t.walletLine(user.credits, user.name)}</div>
        )}
      </div>

      <h1 className="nb-h">{t.heading}</h1>
      <p className={styles.promise}>{t.promise}</p>

      <h2 className="nb-h" style={{ fontSize: 18 }}>{t.createTitle}</h2>
      <form className={`nb-card ${styles.createForm}`} onSubmit={handleCreate}>
        <input
          className="nb-input"
          placeholder={t.songPlaceholder}
          value={song}
          onChange={(e) => setSong(e.target.value)}
        />

        <div className={styles.urlGrid}>
          {PLATFORM_KEYS.map((key) => (
            <input
              key={key}
              className="nb-input"
              placeholder={t.urlPlaceholder(t.platformLabels[key])}
              value={platformUrls[key]}
              onChange={(e) =>
                setPlatformUrls((prev) => ({ ...prev, [key]: e.target.value }))
              }
            />
          ))}
        </div>

        <div className={styles.dateRow}>
          <label className={styles.dateLabel} htmlFor="release-date">
            {t.releaseDateLabel}
          </label>
          <input
            id="release-date"
            className="nb-input"
            type="date"
            value={releaseDate}
            onChange={(e) => setReleaseDate(e.target.value)}
          />
          {showPresaveHint && <span className={styles.presaveHint}>{t.presaveHint}</span>}
        </div>

        {error && <div className={styles.error}>{error}</div>}

        <button type="submit" className="nb-btn nb-btn--purple" disabled={busy}>
          {busy ? t.busy : t.createBtn}
        </button>
      </form>

      <h2 className="nb-h" style={{ fontSize: 18 }}>{t.listTitle}</h2>
      {loading && <div className={styles.empty}>{t.loading}</div>}
      {!loading && links.length === 0 && (
        <div className={styles.empty}>{t.emptyLinks}</div>
      )}

      <div className={styles.linkList}>
        {links.map((link) => {
          const fans = fansMap[link.id] ?? [];
          const isExpanded = expandedId === link.id;
          const isFuturePresave =
            link.presave === 1 && link.release_date
              ? new Date(link.release_date).getTime() > Date.now()
              : false;

          return (
            <div key={link.id} className={`nb-card ${styles.linkCard}`}>
              <div className={styles.linkHead}>
                <div>
                  <div className={styles.slugRow}>
                    <span className={styles.songName}>
                      {link.artist} — {link.title}
                    </span>
                    {isFuturePresave && (
                      <span className="nb-pill nb-pill--purple">{t.presaveBadge}</span>
                    )}
                  </div>
                  <div className={styles.urlRow}>
                    <code className={styles.urlText}>{publicUrl(link.slug)}</code>
                    <button
                      type="button"
                      className={styles.copyBtn}
                      onClick={() => handleCopy(link.slug)}
                    >
                      {copiedSlug === link.slug ? t.copiedBtn : t.copyBtn}
                    </button>
                  </div>
                </div>
              </div>

              <div className={styles.metrics}>
                <span className={styles.metric}>
                  👁️ {link.views} {t.viewsLabel}
                </span>
                {Object.entries(link.links).map(([platform]) => (
                  <span key={platform} className={styles.metric}>
                    {t.platformLabels[platform as PlatformKey] ?? platform}:{" "}
                    {link.clicks[platform] ?? 0}
                  </span>
                ))}
                <span className={styles.metric}>{t.fanCountLabel(fans.length)}</span>
              </div>

              <div className={styles.actionsRow}>
                <button
                  type="button"
                  className="nb-btn nb-btn--outline"
                  onClick={() => toggleFans(link.id)}
                >
                  {isExpanded ? t.fansHideBtn : t.fansBtn}
                </button>
                <button
                  type="button"
                  className="nb-btn"
                  disabled={exportingId === link.id}
                  onClick={() => handleExportCsv(link)}
                >
                  {exportingId === link.id ? t.busy : t.exportBtn}
                </button>
                <span className={styles.exportNote}>{t.exportNote(isPro)}</span>
              </div>

              {exportMsg[link.id] && (
                <div className={styles.error}>{exportMsg[link.id]}</div>
              )}

              {isExpanded && (
                <div className={styles.fansPanel}>
                  {fans.length === 0 ? (
                    <div className={styles.noFans}>{t.noFans}</div>
                  ) : (
                    <div className={styles.tableWrap}>
                      <table className={styles.table}>
                        <thead>
                          <tr>
                            <th>{t.fanEmailCol}</th>
                            <th>{t.fanDateCol}</th>
                            <th>{t.fanConsentCol}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {fans.map((fan) => (
                            <tr key={fan.id}>
                              <td>{fan.email}</td>
                              <td>{new Date(fan.created_at).toLocaleDateString(t.dateLocale)}</td>
                              <td>{fan.consent ? "✓" : "✗"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <h2 className="nb-h" style={{ fontSize: 18 }}>{t.affiliatesTitle}</h2>
      <p className={styles.promise}>{t.affiliatesPromise}</p>
      <div className={styles.affiliateGrid}>
        {affiliates.map((a) => (
          <div key={a.key} className={`nb-card ${styles.affiliateCard}`}>
            <div className={styles.affiliateName}>{a.name}</div>
            <div className={styles.affiliateCategory}>{a.category}</div>
            <p className={styles.affiliateDesc}>{a.description}</p>
            <button
              type="button"
              className="nb-btn nb-btn--green"
              disabled={affiliateBusyKey === a.key}
              onClick={() => handleAffiliateClick(a.key)}
            >
              {affiliateBusyKey === a.key ? t.busy : t.visitBtn}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
