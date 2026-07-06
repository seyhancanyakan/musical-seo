"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  activateSyncListing,
  createSyncListing,
  getMe,
  getToken,
  mySyncListings,
  mySyncRequests,
  pauseSyncListing,
  respondSyncRequest,
  type SyncListing,
  type SyncRequest,
  type User,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type UseKind = "youtube" | "reklam" | "film" | "podcast" | "diger";

const USE_KIND_LABELS = {
  tr: {
    youtube: "YouTube",
    reklam: "Reklam",
    film: "Film / Dizi",
    podcast: "Podcast",
    diger: "Diğer",
  } as Record<string, string>,
  en: {
    youtube: "YouTube",
    reklam: "Ad",
    film: "Film / TV",
    podcast: "Podcast",
    diger: "Other",
  } as Record<string, string>,
} as const;

/** Giris kutusundaki metni sayiya cevirir; gecersizse 0 doner. */
function parsePrice(raw: string): number {
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

const T = {
  tr: {
    logo: "MuzikSEO",
    gateTitle: "Giriş gerekli",
    gateText: "Sync ilanlarını yönetmek için sanatçı hesabınla giriş yap.",
    gateLink: "Giriş / Kayıt",
    userChip: (name: string) => `👤 ${name} — Sanatçı Paneli`,
    heading: "Sync İlanlarını Yönet",
    createHeading: "Yeni İlan Oluştur",
    artistPlaceholder: "Sanatçı",
    titlePlaceholder: "Şarkı",
    genresPlaceholder: "Tür (ör. pop, lo-fi, akustik)",
    moodPlaceholder: "Mood (ör. melankolik, enerjik)",
    descriptionPlaceholder: "Açıklama — şarkı hakkında kısa bilgi",
    priceYoutubeLabel: "YouTube (TL)",
    priceReklamLabel: "Reklam (TL)",
    priceFilmLabel: "Film/Dizi (TL)",
    priceHint: "En az bir kullanım türü için fiyat girmelisin (0'dan büyük).",
    fieldsRequiredError: "Sanatçı ve şarkı adı zorunlu.",
    priceRequiredError: "En az bir kullanım türü için geçerli fiyat girmelisin.",
    createFailedError: "İlan oluşturulamadı — bilgileri kontrol et ve tekrar dene.",
    createBtn: "İlan Oluştur",
    createBusy: "...",
    myListingsHeading: "İlanlarım",
    emptyListings: "Henüz ilanın yok — yukarıdan ilk ilanını oluştur.",
    statusActive: "Aktif",
    statusPaused: "Duraklatıldı",
    pauseBtn: "Duraklat",
    activateBtn: "Aktifleştir",
    incomingHeading: "Gelen Talepler",
    emptyRequests: "Henüz gelen talep yok.",
    useKindLabels: USE_KIND_LABELS.tr,
    priceLine: (price: number, commission: number) =>
      `${price} TL (komisyon: ${commission} TL)`,
    statusPending: "Bekliyor",
    statusAccepted: "Kabul edildi",
    statusRejected: "Reddedildi",
    statusPaid: "Ödendi",
    acceptBtn: "Kabul Et",
    rejectBtn: "Reddet",
    respondBusy: "...",
    showLicenseBtn: "Lisans Metnini Göster",
    hideLicenseBtn: "Lisans Metnini Gizle",
    copyBtn: "Kopyala",
    copiedBtn: "✓ Kopyalandı",
    messageLabel: "Mesaj",
  },
  en: {
    logo: "MuzikSEO",
    gateTitle: "Login required",
    gateText: "Log in with your artist account to manage your sync listings.",
    gateLink: "Login / Sign Up",
    userChip: (name: string) => `👤 ${name} — Artist Panel`,
    heading: "Manage Sync Listings",
    createHeading: "Create New Listing",
    artistPlaceholder: "Artist",
    titlePlaceholder: "Song title",
    genresPlaceholder: "Genre (e.g. pop, lo-fi, acoustic)",
    moodPlaceholder: "Mood (e.g. melancholic, energetic)",
    descriptionPlaceholder: "Description — short info about the song",
    priceYoutubeLabel: "YouTube (TRY)",
    priceReklamLabel: "Ad (TRY)",
    priceFilmLabel: "Film/TV (TRY)",
    priceHint: "You must set a price greater than 0 for at least one use type.",
    fieldsRequiredError: "Artist and song title are required.",
    priceRequiredError: "You must set a valid price for at least one use type.",
    createFailedError: "Couldn't create the listing — check your details and try again.",
    createBtn: "Create Listing",
    createBusy: "...",
    myListingsHeading: "My Listings",
    emptyListings: "You don't have any listings yet — create your first one above.",
    statusActive: "Active",
    statusPaused: "Paused",
    pauseBtn: "Pause",
    activateBtn: "Activate",
    incomingHeading: "Incoming Requests",
    emptyRequests: "No incoming requests yet.",
    useKindLabels: USE_KIND_LABELS.en,
    priceLine: (price: number, commission: number) =>
      `${price} TRY (commission: ${commission} TRY)`,
    statusPending: "Pending",
    statusAccepted: "Accepted",
    statusRejected: "Rejected",
    statusPaid: "Paid",
    acceptBtn: "Accept",
    rejectBtn: "Reject",
    respondBusy: "...",
    showLicenseBtn: "Show License Text",
    hideLicenseBtn: "Hide License Text",
    copyBtn: "Copy",
    copiedBtn: "✓ Copied",
    messageLabel: "Message",
  },
} as const;

function statusBadgeClass(status: SyncRequest["status"]): string {
  if (status === "paid") return styles.badgePaid;
  if (status === "accepted") return styles.badgeAccepted;
  if (status === "rejected") return styles.badgeRejected;
  return styles.badgePending;
}

function listingBadgeClass(status: SyncListing["status"]): string {
  return status === "active" ? styles.badgeAccepted : styles.badgePending;
}

/** Sanatci sync ilan yonetimi — ilan olustur/duraklat, gelen lisans taleplerine yanit ver. */
export default function SyncManagePage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);

  const [listings, setListings] = useState<SyncListing[]>([]);
  const [requests, setRequests] = useState<SyncRequest[]>([]);

  const [artist, setArtist] = useState("");
  const [title, setTitle] = useState("");
  const [genres, setGenres] = useState("");
  const [mood, setMood] = useState("");
  const [description, setDescription] = useState("");
  const [priceYoutube, setPriceYoutube] = useState("");
  const [priceReklam, setPriceReklam] = useState("");
  const [priceFilm, setPriceFilm] = useState("");
  const [createError, setCreateError] = useState("");
  const [createBusy, setCreateBusy] = useState(false);

  const [toggleBusyId, setToggleBusyId] = useState<number | null>(null);
  const [respondBusyId, setRespondBusyId] = useState<number | null>(null);
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
      setChecked(true);
      if (!me || me.user.role !== "artist") return;
      setUser(me.user);
      const [listingsRes, requestsRes] = await Promise.all([
        mySyncListings(),
        mySyncRequests(),
      ]);
      if (cancelled) return;
      if (listingsRes) setListings(listingsRes);
      if (requestsRes) setRequests(requestsRes);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function resetForm() {
    setArtist("");
    setTitle("");
    setGenres("");
    setMood("");
    setDescription("");
    setPriceYoutube("");
    setPriceReklam("");
    setPriceFilm("");
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (createBusy) return;
    setCreateError("");
    if (!artist.trim() || !title.trim()) {
      setCreateError(t.fieldsRequiredError);
      return;
    }
    const py = parsePrice(priceYoutube);
    const pr = parsePrice(priceReklam);
    const pf = parsePrice(priceFilm);
    if (py <= 0 && pr <= 0 && pf <= 0) {
      setCreateError(t.priceRequiredError);
      return;
    }
    setCreateBusy(true);
    const listing = await createSyncListing({
      artist: artist.trim(),
      title: title.trim(),
      genres: genres.trim() || undefined,
      mood: mood.trim() || undefined,
      description: description.trim() || undefined,
      price_youtube: py > 0 ? py : undefined,
      price_reklam: pr > 0 ? pr : undefined,
      price_film: pf > 0 ? pf : undefined,
    });
    setCreateBusy(false);
    if (!listing) {
      setCreateError(t.createFailedError);
      return;
    }
    setListings((prev) => [listing, ...prev]);
    resetForm();
  }

  async function handleToggleStatus(listing: SyncListing) {
    setToggleBusyId(listing.id);
    const updated =
      listing.status === "active"
        ? await pauseSyncListing(listing.id)
        : await activateSyncListing(listing.id);
    setToggleBusyId(null);
    if (updated) {
      setListings((prev) => prev.map((l) => (l.id === listing.id ? updated : l)));
    }
  }

  async function handleRespond(id: number, action: "accepted" | "rejected") {
    setRespondBusyId(id);
    const updated = await respondSyncRequest(id, action);
    setRespondBusyId(null);
    if (updated) {
      setRequests((prev) => prev.map((r) => (r.id === id ? updated : r)));
      if (action === "accepted") setExpandedId(id);
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
    return listing ? `${listing.artist} — ${listing.title}` : `#${listingId}`;
  }

  function statusLabel(status: SyncRequest["status"]): string {
    if (status === "paid") return t.statusPaid;
    if (status === "accepted") return t.statusAccepted;
    if (status === "rejected") return t.statusRejected;
    return t.statusPending;
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
          <Link href="/" className={styles.logo}>{t.logo}</Link>
          <LangToggle />
        </div>
        {user && <div className={styles.userChip}>{t.userChip(user.name)}</div>}
      </div>

      <h1 className="nb-h">{t.heading}</h1>

      <div className={`nb-card ${styles.createSection}`}>
        <h2 className="nb-h">{t.createHeading}</h2>
        <form onSubmit={handleCreate} className={styles.form}>
          <div className={styles.row2}>
            <input
              className="nb-input"
              placeholder={t.artistPlaceholder}
              value={artist}
              onChange={(e) => setArtist(e.target.value)}
              required
            />
            <input
              className="nb-input"
              placeholder={t.titlePlaceholder}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>
          <div className={styles.row2}>
            <input
              className="nb-input"
              placeholder={t.genresPlaceholder}
              value={genres}
              onChange={(e) => setGenres(e.target.value)}
            />
            <input
              className="nb-input"
              placeholder={t.moodPlaceholder}
              value={mood}
              onChange={(e) => setMood(e.target.value)}
            />
          </div>
          <textarea
            className={`nb-input ${styles.textarea}`}
            placeholder={t.descriptionPlaceholder}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className={styles.row3}>
            <div className={styles.priceField}>
              <label className={styles.fieldLabel} htmlFor="price-youtube">
                {t.priceYoutubeLabel}
              </label>
              <input
                id="price-youtube"
                className="nb-input"
                type="number"
                min={0}
                value={priceYoutube}
                onChange={(e) => setPriceYoutube(e.target.value)}
              />
            </div>
            <div className={styles.priceField}>
              <label className={styles.fieldLabel} htmlFor="price-reklam">
                {t.priceReklamLabel}
              </label>
              <input
                id="price-reklam"
                className="nb-input"
                type="number"
                min={0}
                value={priceReklam}
                onChange={(e) => setPriceReklam(e.target.value)}
              />
            </div>
            <div className={styles.priceField}>
              <label className={styles.fieldLabel} htmlFor="price-film">
                {t.priceFilmLabel}
              </label>
              <input
                id="price-film"
                className="nb-input"
                type="number"
                min={0}
                value={priceFilm}
                onChange={(e) => setPriceFilm(e.target.value)}
              />
            </div>
          </div>
          <p className={styles.hint}>{t.priceHint}</p>
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
                  {listing.artist} — {listing.title}{" "}
                  <span className={`${styles.badge} ${listingBadgeClass(listing.status)}`}>
                    {listing.status === "active" ? t.statusActive : t.statusPaused}
                  </span>
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
        {requests.length === 0 && <div className={styles.empty}>{t.emptyRequests}</div>}
        <div className={styles.list}>
          {requests.map((req) => {
            const isExpanded = expandedId === req.id;
            const canRespond = req.status === "pending";
            const canShowLicense = req.license_text && req.status !== "pending";
            return (
              <div
                key={req.id}
                className={`nb-card ${styles.requestCard} ${
                  req.status === "paid" ? styles.requestCardPaid : ""
                }`}
              >
                <div className={styles.requestHeader}>
                  <div>
                    <div className={styles.requestListing}>
                      {listingLabelFor(req.listing_id)}
                    </div>
                    <div className={styles.requestBuyer}>
                      {req.buyer_name} · {req.buyer_email} ·{" "}
                      {t.useKindLabels[req.use_kind] ?? req.use_kind}
                    </div>
                    <div className={styles.requestPrice}>
                      {t.priceLine(req.price_try, req.commission_try)}
                    </div>
                    {req.message && (
                      <div className={styles.requestMessage}>
                        <strong>{t.messageLabel}:</strong> {req.message}
                      </div>
                    )}
                  </div>
                  <span className={`${styles.badge} ${statusBadgeClass(req.status)}`}>
                    {statusLabel(req.status)}
                  </span>
                </div>

                {canRespond && (
                  <div className={styles.requestActions}>
                    <button
                      type="button"
                      className={`nb-btn ${styles.acceptBtn}`}
                      disabled={respondBusyId === req.id}
                      onClick={() => handleRespond(req.id, "accepted")}
                    >
                      {respondBusyId === req.id ? t.respondBusy : t.acceptBtn}
                    </button>
                    <button
                      type="button"
                      className={`nb-btn ${styles.rejectBtn}`}
                      disabled={respondBusyId === req.id}
                      onClick={() => handleRespond(req.id, "rejected")}
                    >
                      {respondBusyId === req.id ? t.respondBusy : t.rejectBtn}
                    </button>
                  </div>
                )}

                {canShowLicense && (
                  <div className={styles.licenseSection}>
                    <button
                      type="button"
                      className={styles.licenseToggle}
                      onClick={() => setExpandedId(isExpanded ? null : req.id)}
                    >
                      {isExpanded ? t.hideLicenseBtn : t.showLicenseBtn}
                    </button>
                    {isExpanded && req.license_text && (
                      <div className={styles.licensePanel}>
                        <pre className={styles.licenseText}>{req.license_text}</pre>
                        <button
                          type="button"
                          className="nb-btn"
                          onClick={() => handleCopy(req.id, req.license_text ?? "")}
                        >
                          {copiedId === req.id ? t.copiedBtn : t.copyBtn}
                        </button>
                      </div>
                    )}
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
