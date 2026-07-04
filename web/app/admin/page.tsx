"use client";

import { useEffect, useMemo, useState } from "react";
import {
  listAllCurators,
  setCuratorStatus,
  type Curator,
  type CuratorStatus,
} from "@/lib/api";
import styles from "./page.module.css";

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

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("tr-TR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function AdminPage() {
  const [curators, setCurators] = useState<Curator[]>([]);
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    listAllCurators().then((data) => {
      if (cancelled) return;
      if (data === null) {
        setIsDemoMode(true);
        setCurators(DEMO_CURATORS);
      } else {
        setIsDemoMode(false);
        setCurators(data);
      }
      setIsLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const counts = useMemo(() => {
    const base = { all: curators.length, lead: 0, pending: 0, approved: 0, rejected: 0 };
    for (const c of curators) base[c.status] += 1;
    return base;
  }, [curators]);

  const visible = useMemo(
    () => (filter === "all" ? curators : curators.filter((c) => c.status === filter)),
    [curators, filter]
  );

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

  return (
    <div>
      <nav className={styles.topbar}>
        <div className={styles.topbarInner}>
          <div className={styles.logo}>MuzikSEO</div>
          <div className={styles.userChip}>🛡️ Admin — Küratör Yönetimi</div>
        </div>
      </nav>

      <div className={styles.wrap}>
        <h1 className={styles.pageTitle}>Küratör Paneli</h1>

        {isDemoMode && (
          <div className={styles.apiBanner} role="status">
            <strong>API&apos;ye ulaşılamadı</strong> — demo veri gösteriliyor.
          </div>
        )}

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
                        <a className={styles.email} href={`mailto:${c.email}`}>
                          {c.email}
                        </a>
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
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
