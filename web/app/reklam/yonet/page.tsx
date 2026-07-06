"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  activateRadioAdListing,
  createRadioAdListing,
  getMe,
  getToken,
  myCurator,
  myRadioAdListings,
  myRadioAdOrders,
  pauseRadioAdListing,
  recordRadioAdAir,
  respondRadioAdOrder,
  type RadioAdListing,
  type RadioAdOrder,
  type User,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type Daypart = "sabah" | "gunduz" | "drive" | "aksam" | "gece";

const DAYPARTS: Daypart[] = ["sabah", "gunduz", "drive", "aksam", "gece"];
const SLOT_SECONDS = [15, 30, 60] as const;

const DAYPART_LABELS = {
  tr: {
    sabah: "Sabah",
    gunduz: "Gündüz",
    drive: "Drive-Time",
    aksam: "Akşam",
    gece: "Gece",
  } as Record<string, string>,
  en: {
    sabah: "Morning",
    gunduz: "Daytime",
    drive: "Drive-Time",
    aksam: "Evening",
    gece: "Night",
  } as Record<string, string>,
} as const;

const BUYER_KIND_LABELS = {
  tr: { artist: "Sanatçı", business: "İşletme" } as Record<string, string>,
  en: { artist: "Artist", business: "Business" } as Record<string, string>,
} as const;

/** Giris kutusundaki metni sayiya cevirir; gecersizse 0 doner. */
function parseNumber(raw: string): number {
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

const T = {
  tr: {
    logo: "MuzikSEO",
    gateTitle: "Giriş gerekli",
    gateText: "Radyo envanterini yönetmek için küratör hesabınla giriş yap.",
    gateLink: "Giriş / Kayıt",
    wrongTypeTitle: "Radyo türü küratör hesabı gerekli",
    wrongTypeText:
      "Reklam envanteri sadece radyo türü küratör hesaplarında yönetilebilir. Kayıt sırasında küratör türünü \"📻 Radyo\" olarak seçmen gerekir.",
    wrongTypeLink: "Giriş / Kayıt",
    userChip: (name: string) => `📻 ${name} — Radyo Paneli`,
    heading: "Radyo Envanterini Yönet",
    createHeading: "Yeni İlan Oluştur",
    stationPlaceholder: "İstasyon adı",
    slotLabel: "Spot süresi",
    daypartLabel: "Kuşak",
    weeklySpotsPlaceholder: "Haftalık tekrar",
    priceWeekPlaceholder: "Haftalık fiyat (TL)",
    descriptionPlaceholder: "Açıklama (opsiyonel) — istasyon/kuşak hakkında kısa bilgi",
    fieldsRequiredError: "İstasyon adı, haftalık tekrar ve haftalık fiyat zorunlu.",
    createFailedError: "İlan oluşturulamadı — bilgileri kontrol et ve tekrar dene.",
    createBtn: "İlan Oluştur",
    createBusy: "...",
    myListingsHeading: "İlanlarım",
    emptyListings: "Henüz ilanın yok — yukarıdan ilk ilanını oluştur.",
    statusActive: "Aktif",
    statusPaused: "Duraklatıldı",
    pauseBtn: "Duraklat",
    activateBtn: "Aktifleştir",
    incomingHeading: "Gelen Siparişler",
    emptyOrders: "Henüz gelen sipariş yok.",
    daypartLabels: DAYPART_LABELS.tr,
    buyerKindLabels: BUYER_KIND_LABELS.tr,
    weeksLabel: "hafta",
    priceLine: (price: number, commission: number) =>
      `${price} TL (komisyon: ${commission} TL)`,
    statusPending: "Bekliyor",
    statusAccepted: "Kabul edildi",
    statusRejected: "Reddedildi",
    statusPaid: "Ödendi",
    statusAiring: "Yayında",
    acceptBtn: "Kabul Et",
    rejectBtn: "Reddet",
    respondBusy: "...",
    showContractBtn: "Sözleşme Metnini Göster",
    hideContractBtn: "Sözleşme Metnini Gizle",
    copyBtn: "Kopyala",
    copiedBtn: "✓ Kopyalandı",
    messageLabel: "Mesaj",
    airedBtn: "Yayınlandı +1",
    airedBusy: "...",
    verifiedPlaysLabel: "Doğrulanan yayın",
  },
  en: {
    logo: "MuzikSEO",
    gateTitle: "Login required",
    gateText: "Log in with your curator account to manage your radio inventory.",
    gateLink: "Login / Sign Up",
    wrongTypeTitle: "Radio-type curator account required",
    wrongTypeText:
      "Ad inventory can only be managed by radio-type curator accounts. During sign-up, pick \"📻 Radio\" as your curator type.",
    wrongTypeLink: "Login / Sign Up",
    userChip: (name: string) => `📻 ${name} — Radio Panel`,
    heading: "Manage Radio Inventory",
    createHeading: "Create New Listing",
    stationPlaceholder: "Station name",
    slotLabel: "Spot length",
    daypartLabel: "Daypart",
    weeklySpotsPlaceholder: "Weekly repeats",
    priceWeekPlaceholder: "Weekly price (TRY)",
    descriptionPlaceholder: "Description (optional) — short info about the station/daypart",
    fieldsRequiredError: "Station name, weekly repeats, and weekly price are required.",
    createFailedError: "Couldn't create the listing — check your details and try again.",
    createBtn: "Create Listing",
    createBusy: "...",
    myListingsHeading: "My Listings",
    emptyListings: "You don't have any listings yet — create your first one above.",
    statusActive: "Active",
    statusPaused: "Paused",
    pauseBtn: "Pause",
    activateBtn: "Activate",
    incomingHeading: "Incoming Orders",
    emptyOrders: "No incoming orders yet.",
    daypartLabels: DAYPART_LABELS.en,
    buyerKindLabels: BUYER_KIND_LABELS.en,
    weeksLabel: "weeks",
    priceLine: (price: number, commission: number) =>
      `${price} TRY (commission: ${commission} TRY)`,
    statusPending: "Pending",
    statusAccepted: "Accepted",
    statusRejected: "Rejected",
    statusPaid: "Paid",
    statusAiring: "Airing",
    acceptBtn: "Accept",
    rejectBtn: "Reject",
    respondBusy: "...",
    showContractBtn: "Show Contract Text",
    hideContractBtn: "Hide Contract Text",
    copyBtn: "Copy",
    copiedBtn: "✓ Copied",
    messageLabel: "Message",
    airedBtn: "Aired +1",
    airedBusy: "...",
    verifiedPlaysLabel: "Verified plays",
  },
} as const;

function statusBadgeClass(status: RadioAdOrder["status"]): string {
  if (status === "paid" || status === "airing") return styles.badgePaid;
  if (status === "accepted") return styles.badgeAccepted;
  if (status === "rejected") return styles.badgeRejected;
  return styles.badgePending;
}

function listingBadgeClass(status: RadioAdListing["status"]): string {
  return status === "active" ? styles.badgeAccepted : styles.badgePending;
}

/** Radyo kuratoru envanter yonetimi — ilan olustur/duraklat, gelen siparislere yanit ver. */
export default function RadioAdsManagePage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [user, setUser] = useState<User | null>(null);
  const [isRadioCurator, setIsRadioCurator] = useState(false);
  const [checked, setChecked] = useState(false);

  const [listings, setListings] = useState<RadioAdListing[]>([]);
  const [orders, setOrders] = useState<RadioAdOrder[]>([]);

  const [stationName, setStationName] = useState("");
  const [slotSeconds, setSlotSeconds] = useState<number>(30);
  const [daypart, setDaypart] = useState<Daypart>("gunduz");
  const [weeklySpots, setWeeklySpots] = useState("");
  const [priceWeek, setPriceWeek] = useState("");
  const [description, setDescription] = useState("");
  const [createError, setCreateError] = useState("");
  const [createBusy, setCreateBusy] = useState(false);

  const [toggleBusyId, setToggleBusyId] = useState<number | null>(null);
  const [respondBusyId, setRespondBusyId] = useState<number | null>(null);
  const [airBusyId, setAirBusyId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!getToken()) {
        setChecked(true);
        return;
      }
      const me = await getMe();
      if (cancelled) return;
      if (!me || me.user.role !== "curator") {
        setChecked(true);
        return;
      }
      const curator = await myCurator();
      if (cancelled) return;
      setChecked(true);
      setUser(me.user);
      if (!curator || curator.curator_type !== "radyo") {
        setIsRadioCurator(false);
        return;
      }
      setIsRadioCurator(true);
      const [listingsRes, ordersRes] = await Promise.all([
        myRadioAdListings(),
        myRadioAdOrders(),
      ]);
      if (cancelled) return;
      if (listingsRes) setListings(listingsRes);
      if (ordersRes) setOrders(ordersRes);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function resetForm() {
    setStationName("");
    setSlotSeconds(30);
    setDaypart("gunduz");
    setWeeklySpots("");
    setPriceWeek("");
    setDescription("");
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (createBusy) return;
    setCreateError("");
    const spots = parseNumber(weeklySpots);
    const price = parseNumber(priceWeek);
    if (!stationName.trim() || spots <= 0 || price <= 0) {
      setCreateError(t.fieldsRequiredError);
      return;
    }
    setCreateBusy(true);
    const result = await createRadioAdListing({
      station_name: stationName.trim(),
      slot_seconds: slotSeconds,
      daypart,
      weekly_spots: spots,
      price_week_try: price,
      description: description.trim() || undefined,
    });
    setCreateBusy(false);
    if (result.error || !result.data) {
      setCreateError(result.error ?? t.createFailedError);
      return;
    }
    setListings((prev) => [result.data as RadioAdListing, ...prev]);
    resetForm();
  }

  async function handleToggleStatus(listing: RadioAdListing) {
    setToggleBusyId(listing.id);
    const updated =
      listing.status === "active"
        ? await pauseRadioAdListing(listing.id)
        : await activateRadioAdListing(listing.id);
    setToggleBusyId(null);
    if (updated) {
      setListings((prev) => prev.map((l) => (l.id === listing.id ? updated : l)));
    }
  }

  async function handleRespond(id: number, action: "accepted" | "rejected") {
    setRespondBusyId(id);
    const result = await respondRadioAdOrder(id, action);
    setRespondBusyId(null);
    if (result.data) {
      const updated = result.data;
      setOrders((prev) => prev.map((o) => (o.id === id ? updated : o)));
      if (action === "accepted") setExpandedId(id);
    }
  }

  async function handleAir(id: number) {
    setAirBusyId(id);
    const result = await recordRadioAdAir(id);
    setAirBusyId(null);
    if (result.data) {
      const updated = result.data;
      setOrders((prev) => prev.map((o) => (o.id === id ? updated : o)));
    }
  }

  async function handleCopy(id: number, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId((cur) => (cur === id ? null : cur)), 2000);
    } catch {
      // Panoya erisim engellenmis olabilir — sessizce yoksay, buton devrede kalir.
    }
  }

  function listingLabelFor(listingId: number): string {
    const listing = listings.find((l) => l.id === listingId);
    return listing ? listing.station_name : `#${listingId}`;
  }

  function statusLabel(status: RadioAdOrder["status"]): string {
    if (status === "paid") return t.statusPaid;
    if (status === "airing") return t.statusAiring;
    if (status === "accepted") return t.statusAccepted;
    if (status === "rejected") return t.statusRejected;
    return t.statusPending;
  }

  if (checked && (!user || !isRadioCurator)) {
    const wrongType = Boolean(user) && !isRadioCurator;
    return (
      <div className={styles.gate}>
        <div className="nb-card" style={{ padding: 28, maxWidth: 460 }}>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
            <LangToggle />
          </div>
          <h2 className="nb-h">{wrongType ? t.wrongTypeTitle : t.gateTitle}</h2>
          <p className={styles.gateText}>{wrongType ? t.wrongTypeText : t.gateText}</p>
          <Link href="/giris" className="nb-btn">
            {wrongType ? t.wrongTypeLink : t.gateLink}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" className={styles.logo}>{t.logo}</Link>
          <LangToggle />
        </div>
        {user && <div className={styles.userChip}>{t.userChip(user.name)}</div>}
      </div>

      <h1 className="nb-h">{t.heading}</h1>

      <div className={`nb-card ${styles.createSection}`}>
        <h2 className="nb-h">{t.createHeading}</h2>
        <form onSubmit={handleCreate} className={styles.form}>
          <input
            className="nb-input"
            placeholder={t.stationPlaceholder}
            value={stationName}
            onChange={(e) => setStationName(e.target.value)}
            required
          />
          <div className={styles.row2}>
            <div className={styles.priceField}>
              <label className={styles.fieldLabel} htmlFor="slot-seconds">
                {t.slotLabel}
              </label>
              <select
                id="slot-seconds"
                className="nb-input"
                value={slotSeconds}
                onChange={(e) => setSlotSeconds(Number(e.target.value))}
              >
                {SLOT_SECONDS.map((s) => (
                  <option key={s} value={s}>
                    {s} sn
                  </option>
                ))}
              </select>
            </div>
            <div className={styles.priceField}>
              <label className={styles.fieldLabel} htmlFor="daypart">
                {t.daypartLabel}
              </label>
              <select
                id="daypart"
                className="nb-input"
                value={daypart}
                onChange={(e) => setDaypart(e.target.value as Daypart)}
              >
                {DAYPARTS.map((d) => (
                  <option key={d} value={d}>
                    {t.daypartLabels[d]}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className={styles.row2}>
            <input
              className="nb-input"
              type="number"
              min={1}
              placeholder={t.weeklySpotsPlaceholder}
              value={weeklySpots}
              onChange={(e) => setWeeklySpots(e.target.value)}
            />
            <input
              className="nb-input"
              type="number"
              min={0}
              placeholder={t.priceWeekPlaceholder}
              value={priceWeek}
              onChange={(e) => setPriceWeek(e.target.value)}
            />
          </div>
          <textarea
            className={`nb-input ${styles.textarea}`}
            placeholder={t.descriptionPlaceholder}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          {createError && <div className={styles.error}>{createError}</div>}
          <button type="submit" className="nb-btn" disabled={createBusy}>
            {createBusy ? t.createBusy : t.createBtn}
          </button>
        </form>
      </div>

      <div className={styles.section}>
        <h2 className="nb-h">{t.myListingsHeading}</h2>
        {listings.length === 0 && <div className={styles.empty}>{t.emptyListings}</div>}
        <div className={styles.list}>
          {listings.map((listing) => (
            <div key={listing.id} className={`nb-card ${styles.listingCard}`}>
              <div>
                <div className={styles.listingName}>
                  {listing.station_name}{" "}
                  <span className={`${styles.badge} ${listingBadgeClass(listing.status)}`}>
                    {listing.status === "active" ? t.statusActive : t.statusPaused}
                  </span>
                </div>
                <div className={styles.listingSub}>
                  {t.daypartLabels[listing.daypart]} · {listing.slot_seconds} sn ·{" "}
                  {listing.weekly_spots}× · {listing.price_week_try} TL
                </div>
              </div>
              <button
                type="button"
                className="nb-btn"
                disabled={toggleBusyId === listing.id}
                onClick={() => handleToggleStatus(listing)}
              >
                {toggleBusyId === listing.id
                  ? t.createBusy
                  : listing.status === "active"
                  ? t.pauseBtn
                  : t.activateBtn}
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className={styles.section}>
        <h2 className="nb-h">{t.incomingHeading}</h2>
        {orders.length === 0 && <div className={styles.empty}>{t.emptyOrders}</div>}
        <div className={styles.list}>
          {orders.map((order) => {
            const isExpanded = expandedId === order.id;
            const canRespond = order.status === "pending";
            const canShowContract = order.contract_text && order.status !== "pending";
            const canAir = order.status === "paid" || order.status === "airing";
            return (
              <div
                key={order.id}
                className={`nb-card ${styles.requestCard} ${
                  order.status === "paid" || order.status === "airing"
                    ? styles.requestCardPaid
                    : ""
                }`}
              >
                <div className={styles.requestHeader}>
                  <div>
                    <div className={styles.requestListing}>
                      {listingLabelFor(order.listing_id)}
                    </div>
                    <div className={styles.requestBuyer}>
                      {order.buyer_name} · {order.buyer_email} ·{" "}
                      <span className={styles.buyerKindBadge}>
                        {t.buyerKindLabels[order.buyer_kind] ?? order.buyer_kind}
                      </span>
                    </div>
                    <div className={styles.requestPrice}>
                      {order.weeks} {t.weeksLabel} ·{" "}
                      {t.priceLine(order.price_try, order.commission_try)}
                    </div>
                    {order.message && (
                      <div className={styles.requestMessage}>
                        <strong>{t.messageLabel}:</strong> {order.message}
                      </div>
                    )}
                  </div>
                  <span className={`${styles.badge} ${statusBadgeClass(order.status)}`}>
                    {statusLabel(order.status)}
                  </span>
                </div>

                {canRespond && (
                  <div className={styles.requestActions}>
                    <button
                      type="button"
                      className={`nb-btn ${styles.acceptBtn}`}
                      disabled={respondBusyId === order.id}
                      onClick={() => handleRespond(order.id, "accepted")}
                    >
                      {respondBusyId === order.id ? t.respondBusy : t.acceptBtn}
                    </button>
                    <button
                      type="button"
                      className={`nb-btn ${styles.rejectBtn}`}
                      disabled={respondBusyId === order.id}
                      onClick={() => handleRespond(order.id, "rejected")}
                    >
                      {respondBusyId === order.id ? t.respondBusy : t.rejectBtn}
                    </button>
                  </div>
                )}

                {canShowContract && (
                  <div className={styles.contractSection}>
                    <button
                      type="button"
                      className={styles.contractToggle}
                      onClick={() => setExpandedId(isExpanded ? null : order.id)}
                    >
                      {isExpanded ? t.hideContractBtn : t.showContractBtn}
                    </button>
                    {isExpanded && order.contract_text && (
                      <div className={styles.contractPanel}>
                        <pre className={styles.contractText}>{order.contract_text}</pre>
                        <button
                          type="button"
                          className="nb-btn"
                          onClick={() => handleCopy(order.id, order.contract_text ?? "")}
                        >
                          {copiedId === order.id ? t.copiedBtn : t.copyBtn}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {canAir && (
                  <div className={styles.airRow}>
                    <button
                      type="button"
                      className="nb-btn"
                      disabled={airBusyId === order.id}
                      onClick={() => handleAir(order.id)}
                    >
                      {airBusyId === order.id ? t.airedBusy : t.airedBtn}
                    </button>
                    <span className={styles.verifiedPlays}>
                      {t.verifiedPlaysLabel}: {order.verified_plays}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
