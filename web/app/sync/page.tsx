"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  publicSyncCatalog,
  requestSyncLicense,
  type SyncListing,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type UseKind = "youtube" | "reklam" | "film" | "podcast" | "diger";

/** Sirali kullanim turu listesi — backend USE_KINDS ile ayni sira. */
const USE_KINDS: UseKind[] = ["youtube", "reklam", "film", "podcast", "diger"];

/** Fiyat kolonu -> ilgili kullanim turleri (backend _PRICE_COLUMN ile ayni:
 *  podcast/diger icin ayri kolon yok, price_youtube paylasilir). */
function availableUseKinds(listing: SyncListing): UseKind[] {
  return USE_KINDS.filter((kind) => {
    if (kind === "youtube" || kind === "podcast" || kind === "diger") {
      return (listing.price_youtube ?? 0) > 0;
    }
    if (kind === "reklam") return (listing.price_reklam ?? 0) > 0;
    if (kind === "film") return (listing.price_film ?? 0) > 0;
    return false;
  });
}

const T = {
  tr: {
    logo: "Songdeck",
    manageLink: "Sanatçı mısın? İlan aç",
    heading: "Sync / Lisans Kataloğu",
    intro:
      "Videon/reklamın için lisanslı Türkçe müzik — tek kullanımlık lisans, standart sözleşme, %15 platform komisyonu dahil.",
    useKindLabels: {
      youtube: "YouTube",
      reklam: "Reklam",
      film: "Film / Dizi",
      podcast: "Podcast",
      diger: "Diğer",
    } as Record<UseKind, string>,
    useKindFilterAll: "Tüm kullanım türleri",
    genrePlaceholder: "Tür (ör. pop, rock, lo-fi)",
    priceLabels: {
      price_youtube: "YouTube",
      price_reklam: "Reklam",
      price_film: "Film/Dizi",
    } as Record<string, string>,
    requestBtn: "Lisans Talep Et",
    loading: "Yükleniyor...",
    empty: "Bu filtrelerle eşleşen ilan yok.",
    modalClose: "Kapat",
    formName: "Adın / Şirket adı",
    formEmail: "E-posta",
    formUseKind: "Kullanım türü",
    formMessage: "Mesaj (opsiyonel) — projeni kısaca anlat",
    formSubmit: "Gönder",
    formBusy: "...",
    successMsg: "Talebin sanatçıya iletildi.",
    errorMsg: "Talep gönderilemedi — bilgileri kontrol et ve tekrar dene.",
    nameRequiredError: "Ad ve e-posta zorunlu.",
  },
  en: {
    logo: "Songdeck",
    manageLink: "Are you an artist? Open a listing",
    heading: "Sync / License Catalog",
    intro:
      "Licensed Turkish music for your video or ad — single-use license, standard contract, 15% platform fee included.",
    useKindLabels: {
      youtube: "YouTube",
      reklam: "Ad",
      film: "Film / TV",
      podcast: "Podcast",
      diger: "Other",
    } as Record<UseKind, string>,
    useKindFilterAll: "All use types",
    genrePlaceholder: "Genre (e.g. pop, rock, lo-fi)",
    priceLabels: {
      price_youtube: "YouTube",
      price_reklam: "Ad",
      price_film: "Film/TV",
    } as Record<string, string>,
    requestBtn: "Request License",
    loading: "Loading...",
    empty: "No listings match these filters.",
    modalClose: "Close",
    formName: "Your name / Company",
    formEmail: "Email",
    formUseKind: "Use type",
    formMessage: "Message (optional) — briefly describe your project",
    formSubmit: "Send",
    formBusy: "...",
    successMsg: "Your request has been sent to the artist.",
    errorMsg: "Request failed — check your details and try again.",
    nameRequiredError: "Name and email are required.",
  },
} as const;

/** Fiyat gosterimi icin ham alan -> deger; 0/null olanlar karttan elenir. */
function priceEntries(listing: SyncListing): [string, number][] {
  const all: [string, number | null][] = [
    ["price_youtube", listing.price_youtube],
    ["price_reklam", listing.price_reklam],
    ["price_film", listing.price_film],
  ];
  return all.filter((entry): entry is [string, number] => (entry[1] ?? 0) > 0);
}

/** Public sync/lisans kataloğu — muzik arayan YouTuber/ajans/yapimci icin. */
export default function SyncCatalogPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [listings, setListings] = useState<SyncListing[] | null>(null);
  const [filterUseKind, setFilterUseKind] = useState<UseKind | "">("");
  const [filterGenre, setFilterGenre] = useState("");

  const [activeListing, setActiveListing] = useState<SyncListing | null>(null);
  const [formName, setFormName] = useState("");
  const [formEmail, setFormEmail] = useState("");
  const [formUseKind, setFormUseKind] = useState<UseKind>("youtube");
  const [formMessage, setFormMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [successListingId, setSuccessListingId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const id = setTimeout(async () => {
      const list = await publicSyncCatalog({
        use_kind: filterUseKind || undefined,
        genre: filterGenre.trim() || undefined,
      });
      if (!cancelled) setListings(list ?? []);
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [filterUseKind, filterGenre]);

  function openModal(listing: SyncListing) {
    setActiveListing(listing);
    setFormName("");
    setFormEmail("");
    setFormUseKind(availableUseKinds(listing)[0] ?? "youtube");
    setFormMessage("");
    setFormError("");
    setSuccessListingId(null);
  }

  function closeModal() {
    setActiveListing(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!activeListing || busy) return;
    setFormError("");
    if (!formName.trim() || !formEmail.trim()) {
      setFormError(t.nameRequiredError);
      return;
    }
    setBusy(true);
    const result = await requestSyncLicense(activeListing.id, {
      buyer_name: formName.trim(),
      buyer_email: formEmail.trim(),
      use_kind: formUseKind,
      message: formMessage.trim() || undefined,
    });
    setBusy(false);
    if (!result) {
      setFormError(t.errorMsg);
      return;
    }
    setSuccessListingId(activeListing.id);
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" className={styles.logo}>{t.logo}</Link>
          <LangToggle />
        </div>
        <Link href="/sync/yonet" className={styles.manageLink}>
          {t.manageLink}
        </Link>
      </div>

      <h1 className="nb-h">{t.heading}</h1>
      <p className={styles.intro}>{t.intro}</p>

      <div className={styles.filters}>
        <select
          className="nb-input"
          value={filterUseKind}
          onChange={(e) => setFilterUseKind(e.target.value as UseKind | "")}
          aria-label={t.formUseKind}
        >
          <option value="">{t.useKindFilterAll}</option>
          {USE_KINDS.map((k) => (
            <option key={k} value={k}>
              {t.useKindLabels[k]}
            </option>
          ))}
        </select>
        <input
          className="nb-input"
          placeholder={t.genrePlaceholder}
          value={filterGenre}
          onChange={(e) => setFilterGenre(e.target.value)}
        />
      </div>

      {listings === null && <div className={styles.empty}>{t.loading}</div>}
      {listings !== null && listings.length === 0 && (
        <div className={styles.empty}>{t.empty}</div>
      )}

      <div className={styles.list}>
        {listings?.map((listing) => (
          <div key={listing.id} className={`nb-card ${styles.card}`}>
            <div className={styles.cardName}>
              {listing.artist} — {listing.title}
            </div>
            {(listing.genres || listing.mood) && (
              <div className={styles.tagRow}>
                {listing.genres && <span className="nb-chip">{listing.genres}</span>}
                {listing.mood && <span className="nb-chip">{listing.mood}</span>}
              </div>
            )}
            {listing.description && (
              <p className={styles.description}>{listing.description}</p>
            )}
            <div className={styles.priceRow}>
              {priceEntries(listing).map(([key, value]) => (
                <span key={key} className={styles.priceChip}>
                  {t.priceLabels[key]}: {value} TL
                </span>
              ))}
            </div>
            <button
              type="button"
              className={`nb-btn ${styles.requestBtn}`}
              onClick={() => openModal(listing)}
            >
              {t.requestBtn}
            </button>
          </div>
        ))}
      </div>

      {activeListing && (
        <div className={styles.modalOverlay} onClick={closeModal}>
          <div
            className={`nb-card ${styles.modalBox}`}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className={styles.modalClose}
              aria-label={t.modalClose}
              onClick={closeModal}
            >
              ✕
            </button>
            <h2 className="nb-h">
              {activeListing.artist} — {activeListing.title}
            </h2>

            {successListingId === activeListing.id ? (
              <div className={styles.successBox}>{t.successMsg}</div>
            ) : (
              <form onSubmit={handleSubmit} className={styles.form}>
                <input
                  className="nb-input"
                  placeholder={t.formName}
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  required
                />
                <input
                  className="nb-input"
                  type="email"
                  placeholder={t.formEmail}
                  value={formEmail}
                  onChange={(e) => setFormEmail(e.target.value)}
                  required
                />
                <select
                  className="nb-input"
                  value={formUseKind}
                  onChange={(e) => setFormUseKind(e.target.value as UseKind)}
                  aria-label={t.formUseKind}
                >
                  {availableUseKinds(activeListing).map((k) => (
                    <option key={k} value={k}>
                      {t.useKindLabels[k]}
                    </option>
                  ))}
                </select>
                <textarea
                  className={`nb-input ${styles.textarea}`}
                  placeholder={t.formMessage}
                  value={formMessage}
                  onChange={(e) => setFormMessage(e.target.value)}
                />
                {formError && <div className={styles.error}>{formError}</div>}
                <button type="submit" className="nb-btn" disabled={busy}>
                  {busy ? t.formBusy : t.formSubmit}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
