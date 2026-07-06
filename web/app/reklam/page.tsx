"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  orderRadioAd,
  publicRadioAds,
  type RadioAdListing,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type Daypart = "sabah" | "gunduz" | "drive" | "aksam" | "gece";
type BuyerKind = "artist" | "business";

/** Backend enum sirasi ile ayni — filtre + form select'lerinde kullanilir. */
const DAYPARTS: Daypart[] = ["sabah", "gunduz", "drive", "aksam", "gece"];

const T = {
  tr: {
    logo: "MuzikSEO",
    manageLink: "Radyo işletmecisi misin? Envanterini listele",
    heading: "Radyo Reklam Pazarı",
    intro:
      "700+ yerel radyoya tek panelden reklam ver — açık fiyat, standart sözleşme, her yayın bağımsız doğrulanır. Beyan değil, kanıt.",
    daypartLabels: {
      sabah: "Sabah",
      gunduz: "Gündüz",
      drive: "Drive-Time",
      aksam: "Akşam",
      gece: "Gece",
    } as Record<Daypart, string>,
    daypartFilterAll: "Tüm kuşaklar",
    maxPricePlaceholder: "Maks. haftalık fiyat (TL)",
    loading: "Yükleniyor...",
    empty: "Bu filtrelerle eşleşen ilan yok.",
    slotSuffix: "sn spot",
    weeklySpotsSuffix: "kez/hafta",
    priceSuffix: "TL / hafta",
    orderBtn: "Reklam Ver",
    modalClose: "Kapat",
    formName: "Adın / Şirket adın",
    formEmail: "E-posta",
    formBuyerKind: "Alıcı türü",
    buyerKindLabels: { artist: "Sanatçı", business: "İşletme" } as Record<
      BuyerKind,
      string
    >,
    formWeeks: "Hafta sayısı (1-12)",
    formMessage: "Mesaj (opsiyonel)",
    formSubmit: "Gönder",
    formBusy: "...",
    totalLabel: "Toplam",
    commissionNote: "%18 komisyon dahil",
    successMsg: "Talebin radyoya iletildi — onay sonrası ödeme bilgisi e-postana gelir",
    nameRequiredError: "Ad ve e-posta zorunlu.",
    wizardCta: "🚀 Kampanya Başlat — şehrini seç, AI spotunu üret",
  },
  en: {
    logo: "MuzikSEO",
    manageLink: "Are you a radio operator? List your inventory",
    heading: "Radio Ad Marketplace",
    intro:
      "Advertise on 700+ local radio stations from one dashboard — transparent pricing, standard contract, every broadcast independently verified. Proof, not claims.",
    daypartLabels: {
      sabah: "Morning",
      gunduz: "Daytime",
      drive: "Drive-Time",
      aksam: "Evening",
      gece: "Night",
    } as Record<Daypart, string>,
    daypartFilterAll: "All dayparts",
    maxPricePlaceholder: "Max weekly price (TRY)",
    loading: "Loading...",
    empty: "No listings match these filters.",
    slotSuffix: "sec spot",
    weeklySpotsSuffix: "x/week",
    priceSuffix: "TRY / week",
    orderBtn: "Advertise",
    modalClose: "Close",
    formName: "Your name / Company",
    formEmail: "Email",
    formBuyerKind: "Buyer type",
    buyerKindLabels: { artist: "Artist", business: "Business" } as Record<
      BuyerKind,
      string
    >,
    formWeeks: "Number of weeks (1-12)",
    formMessage: "Message (optional)",
    formSubmit: "Send",
    formBusy: "...",
    totalLabel: "Total",
    commissionNote: "18% commission included",
    successMsg: "Your request has been sent to the station — payment details arrive by email after approval",
    nameRequiredError: "Name and email are required.",
    wizardCta: "🚀 Start a Campaign — pick your city, generate your AI spot",
  },
} as const;

/** Public radyo reklam kataloğu — sanatçı/işletme spot arayanlar için. */
export default function RadioAdsCatalogPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [listings, setListings] = useState<RadioAdListing[] | null>(null);
  const [filterDaypart, setFilterDaypart] = useState<Daypart | "">("");
  const [filterMaxPrice, setFilterMaxPrice] = useState("");

  const [activeListing, setActiveListing] = useState<RadioAdListing | null>(null);
  const [formName, setFormName] = useState("");
  const [formEmail, setFormEmail] = useState("");
  const [formBuyerKind, setFormBuyerKind] = useState<BuyerKind>("artist");
  const [formWeeks, setFormWeeks] = useState(1);
  const [formMessage, setFormMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [successListingId, setSuccessListingId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const maxPrice = Number(filterMaxPrice);
    const id = setTimeout(async () => {
      const list = await publicRadioAds({
        daypart: filterDaypart || undefined,
        max_price: Number.isFinite(maxPrice) && maxPrice > 0 ? maxPrice : undefined,
      });
      if (!cancelled) setListings(list ?? []);
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [filterDaypart, filterMaxPrice]);

  function openModal(listing: RadioAdListing) {
    setActiveListing(listing);
    setFormName("");
    setFormEmail("");
    setFormBuyerKind("artist");
    setFormWeeks(1);
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
    const result = await orderRadioAd(activeListing.id, {
      buyer_name: formName.trim(),
      buyer_email: formEmail.trim(),
      buyer_kind: formBuyerKind,
      weeks: formWeeks,
      message: formMessage.trim() || undefined,
    });
    setBusy(false);
    if (result.error || !result.data) {
      setFormError(result.error ?? "");
      return;
    }
    setSuccessListingId(activeListing.id);
  }

  const totalPrice = activeListing ? formWeeks * activeListing.price_week_try : 0;

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" className={styles.logo}>{t.logo}</Link>
          <LangToggle />
        </div>
        <Link href="/reklam/yonet" className={styles.manageLink}>
          {t.manageLink}
        </Link>
      </div>

      <h1 className="nb-h">{t.heading}</h1>
      <p className={styles.intro}>{t.intro}</p>

      <Link href="/reklam/kampanya" className="nb-btn nb-btn--purple">
        {t.wizardCta}
      </Link>

      <div className={styles.filters}>
        <select
          className="nb-input"
          value={filterDaypart}
          onChange={(e) => setFilterDaypart(e.target.value as Daypart | "")}
          aria-label={t.daypartFilterAll}
        >
          <option value="">{t.daypartFilterAll}</option>
          {DAYPARTS.map((d) => (
            <option key={d} value={d}>
              {t.daypartLabels[d]}
            </option>
          ))}
        </select>
        <input
          className="nb-input"
          type="number"
          min={0}
          placeholder={t.maxPricePlaceholder}
          value={filterMaxPrice}
          onChange={(e) => setFilterMaxPrice(e.target.value)}
        />
      </div>

      {listings === null && <div className={styles.empty}>{t.loading}</div>}
      {listings !== null && listings.length === 0 && (
        <div className={styles.empty}>{t.empty}</div>
      )}

      <div className={styles.list}>
        {listings?.map((listing) => (
          <div key={listing.id} className={`nb-card ${styles.card}`}>
            <div className={styles.cardName}>{listing.station_name}</div>
            <div className={styles.tagRow}>
              <span className="nb-chip">{t.daypartLabels[listing.daypart]}</span>
              <span className="nb-chip">
                {listing.slot_seconds} {t.slotSuffix}
              </span>
              <span className="nb-chip">
                {listing.weekly_spots} {t.weeklySpotsSuffix}
              </span>
            </div>
            {listing.description && (
              <p className={styles.description}>{listing.description}</p>
            )}
            <div className={styles.priceRow}>
              <span className={styles.priceChip}>
                {listing.price_week_try} {t.priceSuffix}
              </span>
            </div>
            <button
              type="button"
              className={`nb-btn ${styles.orderBtn}`}
              onClick={() => openModal(listing)}
            >
              {t.orderBtn}
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
            <h2 className="nb-h">{activeListing.station_name}</h2>

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
                  value={formBuyerKind}
                  onChange={(e) => setFormBuyerKind(e.target.value as BuyerKind)}
                  aria-label={t.formBuyerKind}
                >
                  <option value="artist">{t.buyerKindLabels.artist}</option>
                  <option value="business">{t.buyerKindLabels.business}</option>
                </select>
                <div className={styles.weeksField}>
                  <label className={styles.fieldLabel} htmlFor="weeks">
                    {t.formWeeks}
                  </label>
                  <input
                    id="weeks"
                    className="nb-input"
                    type="number"
                    min={1}
                    max={12}
                    value={formWeeks}
                    onChange={(e) =>
                      setFormWeeks(
                        Math.min(12, Math.max(1, Number(e.target.value) || 1))
                      )
                    }
                  />
                </div>
                <div className={styles.totalBox}>
                  <span>
                    {t.totalLabel}: <strong>{totalPrice} TL</strong>
                  </span>
                  <span className={styles.commissionNote}>{t.commissionNote}</span>
                </div>
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
