"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  listAllCurators,
  setAdminKey,
  setCuratorStatus,
  sponsorCurator,
  type Curator,
  type CuratorStatus,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";
import { formatDate } from "./utils";
import PurchaseRequestsTab from "./PurchaseRequestsTab";
import CreditGrantTab from "./CreditGrantTab";
import ProActivationTab from "./ProActivationTab";
import PayoutsTab from "./PayoutsTab";
import AirplayTab from "./AirplayTab";
import LabelsTab from "./LabelsTab";

const DEMO_CURATORS: Curator[] = [
  {
    id: 1,
    created_at: "2026-07-01T09:12:00+00:00",
    name: "Türk İndie Radar",
    email: "radar@indie.example",
    deezer_playlist_id: "7841203955",
    playlist_title: "Türkçe İndie 2026",
    playlist_url: "https://deezer.com/playlist/7841203955",
    fans: 18420,
    track_count: 94,
    diversity: 0.61,
    quality_score: 82.4,
    status: "approved",
  },
  {
    id: 2,
    created_at: "2026-07-03T14:47:00+00:00",
    name: "Rock Cephesi",
    email: "hello@rockcephesi.example",
    deezer_playlist_id: "9903117744",
    playlist_title: "Anadolu Rock Klasik",
    playlist_url: "https://deezer.com/playlist/9903117744",
    fans: 7310,
    track_count: 120,
    diversity: 0.34,
    quality_score: 47.9,
    status: "pending",
  },
  {
    id: 3,
    created_at: "2026-07-04T08:05:00+00:00",
    name: "Lo-Fi Köşe",
    email: "curator@lofikose.example",
    deezer_playlist_id: "5521009988",
    playlist_title: "Gece Çalışma Lo-Fi",
    playlist_url: "https://deezer.com/playlist/5521009988",
    fans: 402,
    track_count: 31,
    diversity: 0.12,
    quality_score: 19.3,
    status: "rejected",
  },
];

type Filter = "all" | CuratorStatus;
type SourceKey = "all" | "spotify" | "deezer";
type TabKey =
  | "curators" | "purchases" | "credits" | "pro" | "payouts"
  | "airplay" | "labels";

const T = {
  tr: {
    adminChip: "🛡️ Admin — Küratör Yönetimi",
    pageTitle: "Admin Paneli",
    keyBannerTitle: "Admin anahtarı gerekli",
    keyBannerText: ".env'deki MARKETPLACE_ADMIN_KEY değerini gir:",
    keyPlaceholder: "Admin anahtarı",
    connect: "Bağlan",
    tabs: {
      curators: "Küratörler",
      purchases: "Kredi Talepleri",
      credits: "Kredi Yükle",
      pro: "Pro Aktivasyon",
      payouts: "Ödemeler",
      airplay: "Radyo İstasyonları",
      labels: "Label Başvuruları",
    } as Record<TabKey, string>,
    filters: {
      all: "Tümü",
      lead: "Lead",
      pending: "Bekleyen",
      approved: "Onaylı",
      rejected: "Reddedilen",
    } as Record<Filter, string>,
    sourceFilters: {
      all: "Tüm Kaynaklar",
      spotify: "Spotify",
      deezer: "Deezer",
    } as Record<SourceKey, string>,
    loading: "Yükleniyor...",
    empty: "Bu filtreye uyan küratör yok.",
    columns: {
      curator: "Küratör",
      contact: "İletişim",
      source: "Kaynak",
      playlist: "Playlist",
      fans: "Fan",
      quality: "Kalite",
      applied: "Başvuru",
      status: "Durum",
      action: "İşlem",
    },
    noContact: "iletişim yok",
    openSource: "kaynağı aç ↗",
    confidence: "güven",
    tracksSuffix: "parça",
    statusLabels: {
      approved: "Onaylı",
      rejected: "Reddedildi",
      lead: "Lead",
      pending: "Bekliyor",
    } as Record<CuratorStatus, string>,
    sourceLabels: {
      deezer_owner_name: "Deezer görünen adı",
      deezer_desc_email: "Deezer açıklama (email)",
      deezer_desc_link: "Deezer açıklama (link)",
      deezer_desc_instagram: "Deezer açıklama (IG)",
      hermes_web: "Hermes AI web",
    } as Record<string, string>,
    approve: "Onayla",
    reject: "Reddet",
    hold: "Beklet",
    sponsored: "Sponsorlu",
    sponsorWeek: "Sponsor 7g",
  },
  en: {
    adminChip: "🛡️ Admin — Curator Management",
    pageTitle: "Admin Panel",
    keyBannerTitle: "Admin key required",
    keyBannerText: "Enter the MARKETPLACE_ADMIN_KEY value from .env:",
    keyPlaceholder: "Admin key",
    connect: "Connect",
    tabs: {
      curators: "Curators",
      purchases: "Credit Requests",
      credits: "Grant Credits",
      pro: "Pro Activation",
      payouts: "Payouts",
      airplay: "Radio Stations",
      labels: "Label Applications",
    } as Record<TabKey, string>,
    filters: {
      all: "All",
      lead: "Lead",
      pending: "Pending",
      approved: "Approved",
      rejected: "Rejected",
    } as Record<Filter, string>,
    sourceFilters: {
      all: "All Sources",
      spotify: "Spotify",
      deezer: "Deezer",
    } as Record<SourceKey, string>,
    loading: "Loading...",
    empty: "No curators match this filter.",
    columns: {
      curator: "Curator",
      contact: "Contact",
      source: "Source",
      playlist: "Playlist",
      fans: "Fans",
      quality: "Quality",
      applied: "Applied",
      status: "Status",
      action: "Action",
    },
    noContact: "no contact",
    openSource: "open source ↗",
    confidence: "confidence",
    tracksSuffix: "tracks",
    statusLabels: {
      approved: "Approved",
      rejected: "Rejected",
      lead: "Lead",
      pending: "Pending",
    } as Record<CuratorStatus, string>,
    sourceLabels: {
      deezer_owner_name: "Deezer display name",
      deezer_desc_email: "Deezer description (email)",
      deezer_desc_link: "Deezer description (link)",
      deezer_desc_instagram: "Deezer description (IG)",
      hermes_web: "Hermes AI web",
    } as Record<string, string>,
    approve: "Approve",
    reject: "Reject",
    hold: "Hold",
    sponsored: "Sponsored",
    sponsorWeek: "Sponsor 7d",
  },
} as const;

const FILTER_KEYS: Filter[] = ["all", "lead", "pending", "approved", "rejected"];
const SOURCE_KEYS: SourceKey[] = ["all", "spotify", "deezer"];
const TAB_KEYS: TabKey[] = [
  "curators", "purchases", "credits", "pro", "payouts", "airplay", "labels",
];

function curatorSource(c: Curator): Exclude<SourceKey, "all"> {
  const id = c.deezer_playlist_id || "";
  if (id.startsWith("sp_")) return "spotify";
  return "deezer";
}

function statusClass(status: CuratorStatus): string {
  if (status === "approved") return styles.badgeApproved;
  if (status === "rejected") return styles.badgeRejected;
  if (status === "lead") return styles.badgeLead;
  return styles.badgePending;
}

export default function AdminPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [curators, setCurators] = useState<Curator[]>([]);
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");
  const [sourceFilter, setSourceFilter] = useState<SourceKey>("all");
  const [busyId, setBusyId] = useState<number | null>(null);
  // /admin/curators X-Admin-Key ister; anahtar girilene kadar liste bos doner.
  const [keyDraft, setKeyDraft] = useState("");
  const [needsKey, setNeedsKey] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);
  const [tab, setTab] = useState<TabKey>("curators");
  const [sponsorBusyId, setSponsorBusyId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);

    listAllCurators().then((data) => {
      if (cancelled) return;
      if (data === null) {
        // Anahtar yok/yanlis ya da API kapali — anahtar iste, demoya DUSME.
        setNeedsKey(true);
        setCurators([]);
      } else {
        setNeedsKey(false);
        setIsDemoMode(false);
        setCurators(data);
      }
      setIsLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [reloadTick]);

  function handleSaveKey() {
    setAdminKey(keyDraft.trim());
    setReloadTick((t) => t + 1);
  }

  const counts = useMemo(() => {
    const base = { all: curators.length, lead: 0, pending: 0, approved: 0, rejected: 0 };
    for (const c of curators) base[c.status] += 1;
    return base;
  }, [curators]);

  const visible = useMemo(() => {
    let base = filter === "all" ? curators : curators.filter((c) => c.status === filter);
    if (sourceFilter !== "all") {
      base = base.filter((c) => curatorSource(c) === sourceFilter);
    }
    // Abone/fan sayisina gore azalan sirala — en cok erisimli curator en ustte.
    return [...base].sort((a, b) => b.fans - a.fans);
  }, [curators, filter, sourceFilter]);

  const sourceCounts = useMemo(() => {
    const base = { all: curators.length, spotify: 0, deezer: 0 };
    for (const c of curators) base[curatorSource(c)] += 1;
    return base;
  }, [curators]);

  async function changeStatus(id: number, status: CuratorStatus) {
    setBusyId(id);
    // Demo modda API yok — yerel iyimser güncelleme.
    if (!isDemoMode) {
      const updated = await setCuratorStatus(id, status);
      if (updated) {
        setCurators((prev) => prev.map((c) => (c.id === id ? updated : c)));
        setBusyId(null);
        return;
      }
    }
    setCurators((prev) => prev.map((c) => (c.id === id ? { ...c, status } : c)));
    setBusyId(null);
  }

  /** Kuratoru 7 gunlugune vitrinde one cikar (sponsored=true). */
  async function sponsorForWeek(id: number) {
    setSponsorBusyId(id);
    const untilIso = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
    const updated = await sponsorCurator(id, untilIso);
    if (updated) {
      setCurators((prev) => prev.map((c) => (c.id === id ? updated : c)));
    }
    setSponsorBusyId(null);
  }

  function sourceLabel(source?: string | null): string {
    if (!source) return "—";
    return t.sourceLabels[source] ?? source;
  }

  return (
    <div>
      <nav className={styles.topbar}>
        <div className={styles.topbarInner}>
          <Link href="/" className={styles.logo}>MuzikSEO</Link>
          <div className={styles.userChip}>{t.adminChip}</div>
          <LangToggle />
        </div>
      </nav>

      <div className={styles.wrap}>
        <h1 className={styles.pageTitle}>{t.pageTitle}</h1>

        {needsKey && (
          <div className={styles.apiBanner} role="status">
            <strong>{t.keyBannerTitle}</strong> — {t.keyBannerText}
            <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
              <input
                className="nb-input"
                type="password"
                placeholder={t.keyPlaceholder}
                value={keyDraft}
                onChange={(e) => setKeyDraft(e.target.value)}
                style={{ maxWidth: 320 }}
              />
              <button type="button" className="nb-btn" onClick={handleSaveKey}>
                {t.connect}
              </button>
            </div>
          </div>
        )}

        <div className={styles.tabBar}>
          {TAB_KEYS.map((key) => (
            <button
              key={key}
              type="button"
              className={
                tab === key ? `${styles.tabBtn} ${styles.tabActive}` : styles.tabBtn
              }
              onClick={() => setTab(key)}
            >
              {t.tabs[key]}
            </button>
          ))}
        </div>

        {tab === "curators" && (
        <>
        <div className={styles.filters}>
          {FILTER_KEYS.map((key) => (
            <button
              key={key}
              type="button"
              className={
                filter === key ? `${styles.filterBtn} ${styles.filterActive}` : styles.filterBtn
              }
              onClick={() => setFilter(key)}
            >
              {t.filters[key]} <span className={styles.count}>{counts[key]}</span>
            </button>
          ))}
        </div>

        <div className={styles.filters}>
          {SOURCE_KEYS.map((key) => (
            <button
              key={key}
              type="button"
              className={
                sourceFilter === key
                  ? `${styles.filterBtn} ${styles.filterActive}`
                  : styles.filterBtn
              }
              onClick={() => setSourceFilter(key)}
            >
              {t.sourceFilters[key]} <span className={styles.count}>{sourceCounts[key]}</span>
            </button>
          ))}
        </div>

        {isLoading && <div className={styles.loading}>{t.loading}</div>}

        {!isLoading && visible.length === 0 && (
          <div className={styles.empty}>{t.empty}</div>
        )}

        {!isLoading && visible.length > 0 && (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>{t.columns.curator}</th>
                  <th>{t.columns.contact}</th>
                  <th>{t.columns.source}</th>
                  <th>{t.columns.playlist}</th>
                  <th className={styles.num}>{t.columns.fans}</th>
                  <th className={styles.num}>{t.columns.quality}</th>
                  <th>{t.columns.applied}</th>
                  <th>{t.columns.status}</th>
                  <th>{t.columns.action}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((c) => {
                  const isBusy = busyId === c.id;
                  return (
                    <tr key={c.id}>
                      <td>
                        <div className={styles.name}>{c.name}</div>
                        <div className={styles.sub}>#{c.id}</div>
                      </td>
                      <td>
                        {c.email ? (
                          <a className={styles.email} href={`mailto:${c.email}`}>
                            {c.email}
                          </a>
                        ) : (
                          <span className={styles.sub}>{t.noContact}</span>
                        )}
                      </td>
                      <td>
                        <div className={styles.sub}>{sourceLabel(c.contact_source)}</div>
                        {c.source_url && (
                          <a
                            className={styles.link}
                            href={c.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {t.openSource}
                          </a>
                        )}
                        {typeof c.contact_confidence === "number" && (
                          <div className={styles.sub}>
                            {t.confidence} %{Math.round(c.contact_confidence * 100)}
                          </div>
                        )}
                      </td>
                      <td>
                        <a
                          className={styles.link}
                          href={c.playlist_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {c.playlist_title}
                        </a>
                        <div className={styles.sub}>{c.track_count} {t.tracksSuffix}</div>
                      </td>
                      <td className={styles.num}>
                        {c.fans.toLocaleString(locale === "tr" ? "tr-TR" : "en-US")}
                      </td>
                      <td className={styles.num}>
                        <span className={styles.score}>{c.quality_score.toFixed(1)}</span>
                      </td>
                      <td className={styles.sub}>{formatDate(c.created_at)}</td>
                      <td>
                        <span className={`${styles.badge} ${statusClass(c.status)}`}>
                          {t.statusLabels[c.status]}
                        </span>
                      </td>
                      <td>
                        <div className={styles.actions}>
                          {c.status !== "approved" && (
                            <button
                              type="button"
                              className={`${styles.act} ${styles.actApprove}`}
                              onClick={() => changeStatus(c.id, "approved")}
                              disabled={isBusy}
                            >
                              {t.approve}
                            </button>
                          )}
                          {c.status !== "rejected" && (
                            <button
                              type="button"
                              className={`${styles.act} ${styles.actReject}`}
                              onClick={() => changeStatus(c.id, "rejected")}
                              disabled={isBusy}
                            >
                              {t.reject}
                            </button>
                          )}
                          {c.status !== "pending" && (
                            <button
                              type="button"
                              className={`${styles.act} ${styles.actPending}`}
                              onClick={() => changeStatus(c.id, "pending")}
                              disabled={isBusy}
                            >
                              {t.hold}
                            </button>
                          )}
                          {c.sponsored && (
                            <span className={`${styles.badge} ${styles.badgeSponsored}`}>
                              {t.sponsored}
                            </span>
                          )}
                          <button
                            type="button"
                            className={`${styles.act} ${styles.actSponsor}`}
                            onClick={() => sponsorForWeek(c.id)}
                            disabled={sponsorBusyId === c.id}
                          >
                            {t.sponsorWeek}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        </>
        )}

        {tab === "purchases" && <PurchaseRequestsTab />}
        {tab === "credits" && <CreditGrantTab />}
        {tab === "pro" && <ProActivationTab />}
        {tab === "payouts" && <PayoutsTab />}
        {tab === "airplay" && <AirplayTab />}
        {tab === "labels" && <LabelsTab />}
      </div>
    </div>
  );
}
