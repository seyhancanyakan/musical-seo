"use client";

import { useEffect, useState } from "react";
import { listAdminSubmissions, type AdminSubmission } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";
import { formatDate } from "./utils";

type StatusFilter = "all" | AdminSubmission["status"];

const T = {
  tr: {
    filters: {
      all: "Tümü",
      pending: "Bekleyen",
      accepted: "Kabul Edilen",
      rejected: "Reddedilen",
      expired: "Süresi Dolan",
    } as Record<StatusFilter, string>,
    statusLabels: {
      pending: "Bekliyor",
      accepted: "Kabul Edildi",
      rejected: "Reddedildi",
      expired: "Süresi Doldu",
    } as Record<AdminSubmission["status"], string>,
    loading: "Yükleniyor...",
    empty: "Gönderim yok.",
    columns: {
      id: "ID",
      date: "Tarih",
      song: "Şarkı",
      sender: "Gönderen",
      curator: "Kurator",
      cost: "Maliyet",
      status: "Durum",
      sla: "SLA Bitişi",
      verified: "Yerleşim Doğrulandı",
    },
    guaranteed: "Garantili",
    priority: "Öne Çıkan",
    unknown: "Bilinmiyor",
  },
  en: {
    filters: {
      all: "All",
      pending: "Pending",
      accepted: "Accepted",
      rejected: "Rejected",
      expired: "Expired",
    } as Record<StatusFilter, string>,
    statusLabels: {
      pending: "Pending",
      accepted: "Accepted",
      rejected: "Rejected",
      expired: "Expired",
    } as Record<AdminSubmission["status"], string>,
    loading: "Loading...",
    empty: "No submissions.",
    columns: {
      id: "ID",
      date: "Date",
      song: "Song",
      sender: "Sender",
      curator: "Curator",
      cost: "Cost",
      status: "Status",
      sla: "SLA Deadline",
      verified: "Placement Verified",
    },
    guaranteed: "Guaranteed",
    priority: "Featured",
    unknown: "Unknown",
  },
} as const;

const STATUS_BADGE: Record<AdminSubmission["status"], string> = {
  pending: "badgePending",
  accepted: "badgeApproved",
  rejected: "badgeRejected",
  expired: "badgeExpired",
};

/** Admin: gonderim denetim kuyrugu — durum filtresi, sanatci/kurator baglami, SLA ve yerlesim dogrulama bilgisi. */
export default function SubmissionsTab() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [submissions, setSubmissions] = useState<AdminSubmission[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    listAdminSubmissions(statusFilter === "all" ? undefined : statusFilter).then((data) => {
      if (cancelled) return;
      setSubmissions(data ?? []);
      setIsLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [statusFilter]);

  const filterKeys: StatusFilter[] = ["all", "pending", "accepted", "rejected", "expired"];

  return (
    <div>
      <div className={styles.filters}>
        {filterKeys.map((key) => (
          <button
            key={key}
            type="button"
            className={
              statusFilter === key
                ? `${styles.filterBtn} ${styles.filterActive}`
                : styles.filterBtn
            }
            onClick={() => setStatusFilter(key)}
          >
            {t.filters[key]}
          </button>
        ))}
      </div>

      {isLoading && <div className={styles.loading}>{t.loading}</div>}

      {!isLoading && submissions.length === 0 && (
        <div className={styles.empty}>{t.empty}</div>
      )}

      {!isLoading && submissions.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t.columns.id}</th>
                <th>{t.columns.date}</th>
                <th>{t.columns.song}</th>
                <th>{t.columns.sender}</th>
                <th>{t.columns.curator}</th>
                <th className={styles.num}>{t.columns.cost}</th>
                <th>{t.columns.status}</th>
                <th>{t.columns.sla}</th>
                <th>{t.columns.verified}</th>
              </tr>
            </thead>
            <tbody>
              {submissions.map((s) => (
                <tr key={s.id}>
                  <td className={styles.sub}>#{s.id}</td>
                  <td className={styles.sub}>{formatDate(s.created_at)}</td>
                  <td className={styles.name}>
                    {s.artist} — {s.title}
                  </td>
                  <td>
                    <div className={styles.name}>{s.artist_account ?? t.unknown}</div>
                    {s.artist_email && (
                      <a className={styles.email} href={`mailto:${s.artist_email}`}>
                        {s.artist_email}
                      </a>
                    )}
                  </td>
                  <td>
                    <div className={styles.name}>{s.curator_name}</div>
                    <div className={styles.sub}>{s.playlist_title}</div>
                  </td>
                  <td className={styles.num}>
                    <div>{s.cost_credits ?? "—"}</div>
                    <div className={styles.badgeGroup}>
                      {!!s.guaranteed && (
                        <span className={`${styles.badge} ${styles.badgeLead} ${styles.badgeMini}`}>
                          {t.guaranteed}
                        </span>
                      )}
                      {!!s.priority && (
                        <span
                          className={`${styles.badge} ${styles.badgeSponsored} ${styles.badgeMini}`}
                        >
                          {t.priority}
                        </span>
                      )}
                    </div>
                  </td>
                  <td>
                    <span className={`${styles.badge} ${styles[STATUS_BADGE[s.status]]}`}>
                      {t.statusLabels[s.status]}
                    </span>
                  </td>
                  <td className={styles.sub}>{formatDate(s.deadline)}</td>
                  <td>
                    {s.placement_verified ? (
                      <span className={styles.checkYes}>✓</span>
                    ) : (
                      <span className={styles.dash}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
