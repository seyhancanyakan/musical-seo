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
import styles from "./page.module.css";
import { formatDate } from "./utils";
import PurchaseRequestsTab from "./PurchaseRequestsTab";
import CreditGrantTab from "./CreditGrantTab";
import ProActivationTab from "./ProActivationTab";
import PayoutsTab from "./PayoutsTab";

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

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "Tümü" },
  { key: "lead", label: "Lead" },
  { key: "pending", label: "Bekleyen" },
  { key: "approved", label: "Onaylı" },
  { key: "rejected", label: "Reddedilen" },
];

type SourceKey = "all" | "spotify" | "deezer";

const SOURCE_FILTERS: { key: SourceKey; label: string }[] = [
  { key: "all", label: "Tüm Kaynaklar" },
  { key: "spotify", label: "Spotify" },
  { key: "deezer", label: "Deezer" },
];

function curatorSource(c: Curator): Exclude<SourceKey, "all"> {
  const id = c.deezer_playlist_id || "";
  if (id.startsWith("sp_")) return "spotify";
  return "deezer";
}

function statusLabel(status: CuratorStatus): string {
  if (status === "approved") return "Onaylı";
  if (status === "rejected") return "Reddedildi";
  if (status === "lead") return "Lead";
  return "Bekliyor";
}

function statusClass(status: CuratorStatus): string {
  if (status === "approved") return styles.badgeApproved;
  if (status === "rejected") return styles.badgeRejected;
  if (status === "lead") return styles.badgeLead;
  return styles.badgePending;
}

const SOURCE_LABELS: Record<string, string> = {
  deezer_owner_name: "Deezer görünen adı",
  deezer_desc_email: "Deezer açıklama (email)",
  deezer_desc_link: "Deezer açıklama (link)",
  deezer_desc_instagram: "Deezer açıklama (IG)",
  hermes_web: "Hermes AI web",
};

function sourceLabel(source?: string | null): string {
  if (!source) return "—";
  return SOURCE_LABELS[source] ?? source;
}

type TabKey = "curators" | "purchases" | "credits" | "pro" | "payouts";

const TABS: { key: TabKey; label: string }[] = [
  { key: "curators", label: "Küratörler" },
  { key: "purchases", label: "Kredi Talepleri" },
  { key: "credits", label: "Kredi Yükle" },
  { key: "pro", label: "Pro Aktivasyon" },
  { key: "payouts", label: "Ödemeler" },
];

export default function AdminPage() {
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

  return (
    <div>
      <nav className={styles.topbar}>
        <div className={styles.topbarInner}>
          <Link href="/" className={styles.logo}>MuzikSEO</Link>
          <div className={styles.userChip}>🛡️ Admin — Küratör Yönetimi</div>
        </div>
      </nav>

      <div className={styles.wrap}>
        <h1 className={styles.pageTitle}>Admin Paneli</h1>

        {needsKey && (
          <div className={styles.apiBanner} role="status">
            <strong>Admin anahtarı gerekli</strong> — .env&apos;deki
            MARKETPLACE_ADMIN_KEY değerini gir:
            <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
              <input
                className="nb-input"
                type="password"
                placeholder="Admin anahtarı"
                value={keyDraft}
                onChange={(e) => setKeyDraft(e.target.value)}
                style={{ maxWidth: 320 }}
              />
              <button type="button" className="nb-btn" onClick={handleSaveKey}>
                Bağlan
              </button>
            </div>
          </div>
        )}

        <div className={styles.tabBar}>
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={
                tab === t.key ? `${styles.tabBtn} ${styles.tabActive}` : styles.tabBtn
              }
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "curators" && (
        <>
        <div className={styles.filters}>
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              className={
                filter === f.key ? `${styles.filterBtn} ${styles.filterActive}` : styles.filterBtn
              }
              onClick={() => setFilter(f.key)}
            >
              {f.label} <span className={styles.count}>{counts[f.key]}</span>
            </button>
          ))}
        </div>

        <div className={styles.filters}>
          {SOURCE_FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              className={
                sourceFilter === f.key
                  ? `${styles.filterBtn} ${styles.filterActive}`
                  : styles.filterBtn
              }
              onClick={() => setSourceFilter(f.key)}
            >
              {f.label} <span className={styles.count}>{sourceCounts[f.key]}</span>
            </button>
          ))}
        </div>

        {isLoading && <div className={styles.loading}>Yükleniyor...</div>}

        {!isLoading && visible.length === 0 && (
          <div className={styles.empty}>Bu filtreye uyan küratör yok.</div>
        )}

        {!isLoading && visible.length > 0 && (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Küratör</th>
                  <th>İletişim</th>
                  <th>Kaynak</th>
                  <th>Playlist</th>
                  <th className={styles.num}>Fan</th>
                  <th className={styles.num}>Kalite</th>
                  <th>Başvuru</th>
                  <th>Durum</th>
                  <th>İşlem</th>
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
                          <span className={styles.sub}>iletişim yok</span>
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
                            kaynağı aç ↗
                          </a>
                        )}
                        {typeof c.contact_confidence === "number" && (
                          <div className={styles.sub}>
                            güven %{Math.round(c.contact_confidence * 100)}
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
                        <div className={styles.sub}>{c.track_count} parça</div>
                      </td>
                      <td className={styles.num}>{c.fans.toLocaleString("tr-TR")}</td>
                      <td className={styles.num}>
                        <span className={styles.score}>{c.quality_score.toFixed(1)}</span>
                      </td>
                      <td className={styles.sub}>{formatDate(c.created_at)}</td>
                      <td>
                        <span className={`${styles.badge} ${statusClass(c.status)}`}>
                          {statusLabel(c.status)}
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
                              Onayla
                            </button>
                          )}
                          {c.status !== "rejected" && (
                            <button
                              type="button"
                              className={`${styles.act} ${styles.actReject}`}
                              onClick={() => changeStatus(c.id, "rejected")}
                              disabled={isBusy}
                            >
                              Reddet
                            </button>
                          )}
                          {c.status !== "pending" && (
                            <button
                              type="button"
                              className={`${styles.act} ${styles.actPending}`}
                              onClick={() => changeStatus(c.id, "pending")}
                              disabled={isBusy}
                            >
                              Beklet
                            </button>
                          )}
                          {c.sponsored && (
                            <span className={`${styles.badge} ${styles.badgeSponsored}`}>
                              Sponsorlu
                            </span>
                          )}
                          <button
                            type="button"
                            className={`${styles.act} ${styles.actSponsor}`}
                            onClick={() => sponsorForWeek(c.id)}
                            disabled={sponsorBusyId === c.id}
                          >
                            Sponsor 7g
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
      </div>
    </div>
  );
}
