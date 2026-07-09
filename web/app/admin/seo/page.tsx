"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  buildSeoBatch,
  getAdminKey,
  getSeoPages,
  seedTurkishArtists,
  seedTurkishArtistsAll,
  setAdminKey,
  type SeoPageRow,
  type SeoPageType,
  type SeoQueueStats,
  type SeoQueueStatus,
} from "@/lib/api";
import styles from "./page.module.css";

const PAGE_TYPES: SeoPageType[] = ["artist", "song", "playlist"];
const STATUS_FILTERS: (SeoQueueStatus | "")[] = ["", "pending", "done", "thin", "failed"];
const PAGE_SIZE = 50;

const PAGE_TYPE_LABELS: Record<SeoPageType, string> = {
  artist: "Sanatçı",
  song: "Şarkı",
  playlist: "Playlist",
};

const STATUS_LABELS: Record<SeoQueueStatus | "", string> = {
  "": "Tümü",
  pending: "Bekliyor",
  done: "Yayında",
  thin: "İnce İçerik",
  failed: "Başarısız",
};

const STATUS_BADGE: Record<SeoQueueStatus, string> = {
  pending: "badgePending",
  done: "badgeDone",
  thin: "badgeThin",
  failed: "badgeFailed",
};

const PUBLIC_PREFIX: Record<SeoPageType, string> = {
  artist: "/artist/",
  song: "/song/",
  playlist: "/playlist/",
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" });
}

/** Admin: kuyruktaki + yayindaki tum programatik SEO sayfalarini goruntuler
 *  (build_queue + seo_*_pages, bkz. marketplace/api_seo.py GET /seo/pages).
 *  Operator canli sayfaya tiklayip gidebilir ve kuyrugu buradan isleyebilir. */
export default function AdminSeoPage() {
  const [needsKey, setNeedsKey] = useState(false);
  const [keyDraft, setKeyDraft] = useState("");

  const [pageType, setPageType] = useState<SeoPageType>("artist");
  const [statusFilter, setStatusFilter] = useState<SeoQueueStatus | "">("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [offset, setOffset] = useState(0);

  const [rows, setRows] = useState<SeoPageRow[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<SeoQueueStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [reloadTick, setReloadTick] = useState(0);

  const [buildLimit, setBuildLimit] = useState("20");
  const [buildBusy, setBuildBusy] = useState(false);
  const [buildResult, setBuildResult] = useState<string | null>(null);

  const [seedBusy, setSeedBusy] = useState<"tr" | "tr-all" | null>(null);
  const [seedResult, setSeedResult] = useState<string | null>(null);

  // Arama kutusu debounce — her tus vurusunda istek atmasin.
  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(id);
  }, [search]);

  // Filtre degisince ilk sayfaya don.
  useEffect(() => {
    setOffset(0);
  }, [pageType, statusFilter, debouncedSearch]);

  useEffect(() => {
    if (!getAdminKey()) {
      setNeedsKey(true);
      setIsLoading(false);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    getSeoPages({
      pageType,
      status: statusFilter,
      search: debouncedSearch,
      limit: PAGE_SIZE,
      offset,
    }).then((data) => {
      if (cancelled) return;
      if (data === null) {
        // Anahtar yok/yanlis ya da API kapali — anahtar iste.
        setNeedsKey(true);
        setRows([]);
        setTotal(0);
        setStats(null);
      } else {
        setNeedsKey(false);
        setRows(data.items ?? []);
        setTotal(data.total ?? 0);
        setStats(data.stats ?? null);
      }
      setIsLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [pageType, statusFilter, debouncedSearch, offset, reloadTick]);

  function handleSaveKey() {
    setAdminKey(keyDraft.trim());
    setReloadTick((t) => t + 1);
  }

  async function handleBuild() {
    const limit = Number(buildLimit);
    if (!limit || limit <= 0) return;
    setBuildBusy(true);
    setBuildResult(null);
    const result = await buildSeoBatch(limit);
    if (result) {
      setBuildResult(
        `İşlendi: ${result.processed} · Yayına girdi: ${result.built} · İnce içerik: ${result.thin} · Başarısız: ${result.failed}`
      );
      setReloadTick((t) => t + 1);
    } else {
      setBuildResult("Kuyruk işlenemedi — admin anahtarını kontrol edin.");
    }
    setBuildBusy(false);
  }

  async function handleSeedTurkish() {
    setSeedBusy("tr");
    setSeedResult(null);
    const result = await seedTurkishArtists();
    setSeedResult(result ? "Türk sanatçılar kuyruğa eklendi." : "Ekleme başarısız.");
    setSeedBusy(null);
    setReloadTick((t) => t + 1);
  }

  async function handleSeedTurkishAll() {
    setSeedBusy("tr-all");
    setSeedResult(null);
    const result = await seedTurkishArtistsAll();
    setSeedResult(
      result
        ? "MusicBrainz'den tüm Türk sanatçılar arka planda kuyruğa ekleniyor."
        : "Başlatılamadı."
    );
    setSeedBusy(null);
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div>
      <nav className={styles.topbar}>
        <div className={styles.topbarInner}>
          <Link href="/" className={styles.logo}>
            Sozy Echo
          </Link>
          <Link href="/admin" className={styles.backLink}>
            ← Admin Paneli
          </Link>
          <div className={styles.userChip}>🛡️ Admin — SEO Sayfaları</div>
        </div>
      </nav>

      <div className={styles.wrap}>
        <h1 className={styles.pageTitle}>Programatik SEO Sayfaları</h1>

        {needsKey && (
          <div className={styles.apiBanner} role="status">
            <strong>Admin anahtarı gerekli</strong> — .env&apos;deki MARKETPLACE_ADMIN_KEY
            değerini gir:
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

        {stats && (
          <div className={styles.statRow}>
            <div className={`${styles.statCard} ${styles.statCardPending}`}>
              <div className={styles.statLabel}>Bekliyor</div>
              <div className={styles.statValue}>{stats.pending ?? 0}</div>
            </div>
            <div className={`${styles.statCard} ${styles.statCardDone}`}>
              <div className={styles.statLabel}>Yayında</div>
              <div className={styles.statValue}>{stats.done ?? 0}</div>
            </div>
            <div className={`${styles.statCard} ${styles.statCardThin}`}>
              <div className={styles.statLabel}>İnce İçerik</div>
              <div className={styles.statValue}>{stats.thin ?? 0}</div>
            </div>
            <div className={`${styles.statCard} ${styles.statCardFailed}`}>
              <div className={styles.statLabel}>Başarısız</div>
              <div className={styles.statValue}>{stats.failed ?? 0}</div>
            </div>
          </div>
        )}

        <div className={styles.actionPanel}>
          <div className={styles.buildGroup}>
            <input
              className={styles.limitInput}
              type="number"
              min={1}
              value={buildLimit}
              onChange={(e) => setBuildLimit(e.target.value)}
            />
            <button type="button" className="nb-btn" onClick={handleBuild} disabled={buildBusy}>
              {buildBusy ? "İşleniyor..." : "Kuyruğu İşle"}
            </button>
          </div>
          <button
            type="button"
            className="nb-btn nb-btn--outline"
            onClick={handleSeedTurkish}
            disabled={seedBusy !== null}
          >
            {seedBusy === "tr" ? "..." : "Türk sanatçıları ekle"}
          </button>
          <button
            type="button"
            className="nb-btn nb-btn--outline"
            onClick={handleSeedTurkishAll}
            disabled={seedBusy !== null}
          >
            {seedBusy === "tr-all" ? "..." : "Tümünü ekle (MusicBrainz)"}
          </button>
          {buildResult && <span className={styles.resultChip}>{buildResult}</span>}
          {seedResult && <span className={styles.resultChip}>{seedResult}</span>}
        </div>

        <div className={styles.controls}>
          <div className={styles.filters}>
            {PAGE_TYPES.map((pt) => (
              <button
                key={pt}
                type="button"
                className={
                  pageType === pt
                    ? `${styles.filterBtn} ${styles.filterActive}`
                    : styles.filterBtn
                }
                onClick={() => setPageType(pt)}
              >
                {PAGE_TYPE_LABELS[pt]}
              </button>
            ))}
          </div>
          <div className={styles.filters}>
            {STATUS_FILTERS.map((s) => (
              <button
                key={s || "all"}
                type="button"
                className={
                  statusFilter === s
                    ? `${styles.filterBtn} ${styles.filterActive}`
                    : styles.filterBtn
                }
                onClick={() => setStatusFilter(s)}
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>
          <input
            className={`nb-input ${styles.searchInput}`}
            type="text"
            placeholder="Ara (sanatçı/referans)..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {isLoading && <div className={styles.loading}>Yükleniyor...</div>}

        {!isLoading && !needsKey && rows.length === 0 && (
          <div className={styles.empty}>Bu filtreye uyan sayfa yok.</div>
        )}

        {!isLoading && rows.length > 0 && (
          <>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Referans</th>
                    <th>Durum</th>
                    <th className={styles.num}>Öncelik</th>
                    <th className={styles.num}>Skor</th>
                    <th className={styles.num}>Platform</th>
                    <th>Son Yenileme</th>
                    <th>İşlem</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <div className={styles.name}>{row.ref}</div>
                        <div className={styles.sub}>Kuyruk #{row.id}</div>
                      </td>
                      <td>
                        <span className={`${styles.badge} ${styles[STATUS_BADGE[row.status]]}`}>
                          {STATUS_LABELS[row.status]}
                        </span>
                      </td>
                      <td className={styles.num}>{row.priority}</td>
                      <td className={styles.num}>
                        {row.score != null ? (
                          row.score.toFixed(1)
                        ) : (
                          <span className={styles.dash}>—</span>
                        )}
                      </td>
                      <td className={styles.num}>
                        {row.platform_count != null ? (
                          row.platform_count
                        ) : (
                          <span className={styles.dash}>—</span>
                        )}
                      </td>
                      <td className={styles.sub}>{formatDate(row.last_refreshed_at)}</td>
                      <td>
                        {row.slug ? (
                          <a
                            className={`${styles.act} ${styles.actView}`}
                            href={`${PUBLIC_PREFIX[pageType]}${encodeURIComponent(row.slug)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            Sayfayı Gör ↗
                          </a>
                        ) : (
                          <button type="button" className={styles.act} disabled>
                            Henüz yayında değil
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className={styles.pagination}>
              <button
                type="button"
                className="nb-btn nb-btn--outline"
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                disabled={offset === 0}
              >
                ← Önceki
              </button>
              <span className={styles.pageInfo}>
                Sayfa {currentPage} / {totalPages} · Toplam {total}
              </span>
              <button
                type="button"
                className="nb-btn nb-btn--outline"
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= total}
              >
                Sonraki →
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
