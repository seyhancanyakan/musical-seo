"use client";

import { useEffect, useState } from "react";
import { adminLabels, approveLabel, rejectLabel, type LabelLead } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";
import { formatDate } from "./utils";

type LabelFilter = "pending" | "approved" | "rejected";

const T = {
  tr: {
    filters: {
      pending: "Bekleyen",
      approved: "Onaylı",
      rejected: "Reddedilen",
    } as Record<LabelFilter, string>,
    loading: "Yükleniyor...",
    empty: {
      pending: "Bekleyen label başvurusu yok.",
      approved: "Onaylı label yok.",
      rejected: "Reddedilmiş label yok.",
    } as Record<LabelFilter, string>,
    columns: {
      company: "Şirket",
      contact: "İletişim",
      note: "Not",
      applied: "Başvuru",
      status: "Durum",
      action: "İşlem",
    },
    noNote: "not yok",
    approve: "Onayla",
    reject: "Reddet",
    statusLabels: {
      pending: "Bekliyor",
      approved: "Onaylı",
      rejected: "Reddedildi",
    } as Record<LabelLead["status"], string>,
    copy: "Kopyala",
    copied: "Kopyalandı ✓",
    tokenNote: "30 günlük erişim token'ı — e-postayla ilet.",
    expiresLabel: "Son geçerlilik",
  },
  en: {
    filters: {
      pending: "Pending",
      approved: "Approved",
      rejected: "Rejected",
    } as Record<LabelFilter, string>,
    loading: "Loading...",
    empty: {
      pending: "No pending label applications.",
      approved: "No approved labels.",
      rejected: "No rejected labels.",
    } as Record<LabelFilter, string>,
    columns: {
      company: "Company",
      contact: "Contact",
      note: "Note",
      applied: "Applied",
      status: "Status",
      action: "Action",
    },
    noNote: "no note",
    approve: "Approve",
    reject: "Reject",
    statusLabels: {
      pending: "Pending",
      approved: "Approved",
      rejected: "Rejected",
    } as Record<LabelLead["status"], string>,
    copy: "Copy",
    copied: "Copied ✓",
    tokenNote: "30-day access token — send it by email.",
    expiresLabel: "Expires",
  },
} as const;

const FILTER_KEYS: LabelFilter[] = ["pending", "approved", "rejected"];

function statusClass(status: LabelLead["status"]): string {
  if (status === "approved") return styles.badgeApproved;
  if (status === "rejected") return styles.badgeRejected;
  return styles.badgePending;
}

/** Admin: label/A&R basvuru kuyrugu — onaylananin access_token'i kopyalanabilir gosterilir
 *  (e-posta iletimi pilot doneminde elle yapilir). */
export default function LabelsTab() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [filter, setFilter] = useState<LabelFilter>("pending");
  const [leads, setLeads] = useState<LabelLead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    adminLabels(filter).then((data) => {
      if (cancelled) return;
      setLeads(data ?? []);
      setIsLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  async function handleApprove(id: number) {
    setBusyId(id);
    const updated = await approveLabel(id);
    if (updated) {
      setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)));
    }
    setBusyId(null);
  }

  async function handleReject(id: number) {
    setBusyId(id);
    const updated = await rejectLabel(id);
    if (updated) {
      setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)));
    }
    setBusyId(null);
  }

  async function copyToken(id: number, token: string) {
    try {
      await navigator.clipboard.writeText(token);
      setCopiedId(id);
      setTimeout(() => setCopiedId((cur) => (cur === id ? null : cur)), 2000);
    } catch {
      // panosuz ortamlarda sessiz gec — token yine de secilip elle kopyalanabilir
    }
  }

  const emptyMessage = t.empty[filter];

  return (
    <div>
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
            {t.filters[key]}
          </button>
        ))}
      </div>

      {isLoading && <div className={styles.loading}>{t.loading}</div>}

      {!isLoading && leads.length === 0 && <div className={styles.empty}>{emptyMessage}</div>}

      {!isLoading && leads.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t.columns.company}</th>
                <th>{t.columns.contact}</th>
                <th>{t.columns.note}</th>
                <th>{t.columns.applied}</th>
                <th>{t.columns.status}</th>
                <th>{t.columns.action}</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((l) => {
                const isBusy = busyId === l.id;
                return (
                  <tr key={l.id}>
                    <td>
                      <div className={styles.name}>{l.company}</div>
                      <div className={styles.sub}>{l.contact_name}</div>
                    </td>
                    <td>
                      <a className={styles.email} href={`mailto:${l.email}`}>
                        {l.email}
                      </a>
                    </td>
                    <td>
                      {l.note ? (
                        <div className={styles.note}>{l.note}</div>
                      ) : (
                        <span className={styles.sub}>{t.noNote}</span>
                      )}
                    </td>
                    <td className={styles.sub}>{formatDate(l.created_at)}</td>
                    <td>
                      <span className={`${styles.badge} ${statusClass(l.status)}`}>
                        {t.statusLabels[l.status]}
                      </span>
                    </td>
                    <td>
                      {l.status === "approved" && l.access_token ? (
                        <div className={styles.tokenBox}>
                          <div className={styles.tokenRow}>
                            <span className={styles.tokenValue}>{l.access_token}</span>
                            <button
                              type="button"
                              className={styles.copyBtn}
                              onClick={() => copyToken(l.id, l.access_token as string)}
                            >
                              {copiedId === l.id ? t.copied : t.copy}
                            </button>
                          </div>
                          <div className={styles.tokenMeta}>{t.tokenNote}</div>
                          {l.expires_at && (
                            <div className={styles.tokenMeta}>
                              {t.expiresLabel}: {formatDate(l.expires_at)}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className={styles.actions}>
                          {l.status !== "approved" && (
                            <button
                              type="button"
                              className={`${styles.act} ${styles.actApprove}`}
                              onClick={() => handleApprove(l.id)}
                              disabled={isBusy}
                            >
                              {t.approve}
                            </button>
                          )}
                          {l.status !== "rejected" && (
                            <button
                              type="button"
                              className={`${styles.act} ${styles.actReject}`}
                              onClick={() => handleReject(l.id)}
                              disabled={isBusy}
                            >
                              {t.reject}
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
