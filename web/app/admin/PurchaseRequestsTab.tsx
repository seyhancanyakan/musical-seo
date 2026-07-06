"use client";

import { useEffect, useState } from "react";
import {
  grantPurchaseRequest,
  listPurchaseRequests,
  type PurchaseRequest,
} from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";
import { formatDate } from "./utils";

const T = {
  tr: {
    loading: "Yükleniyor...",
    empty: "Bekleyen talep yok.",
    columns: {
      request: "Talep",
      user: "Kullanıcı",
      pkg: "Paket",
      credits: "Kredi",
      amount: "Tutar",
      date: "Tarih",
      action: "İşlem",
    },
    grantAction: "Ödeme Alındı → Krediyi Yükle",
    grantedMessage: (credits: number) => `${credits} kredi yüklendi`,
  },
  en: {
    loading: "Loading...",
    empty: "No pending requests.",
    columns: {
      request: "Request",
      user: "User",
      pkg: "Package",
      credits: "Credits",
      amount: "Amount",
      date: "Date",
      action: "Action",
    },
    grantAction: "Payment Received → Grant Credits",
    grantedMessage: (credits: number) => `${credits} credits granted`,
  },
} as const;

/** Admin: bekleyen kredi paketi taleplerini listeler ve manuel odeme sonrasi
 *  krediyi kullaniciya yukler (pilotta odeme havale/Papara ile elden alinir). */
export default function PurchaseRequestsTab() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    listPurchaseRequests("pending").then((data) => {
      if (cancelled) return;
      setRequests(data ?? []);
      setIsLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function grant(req: PurchaseRequest) {
    setBusyId(req.id);
    const updated = await grantPurchaseRequest(req.id);
    if (updated) {
      setRequests((prev) => prev.filter((r) => r.id !== req.id));
      setMessage(t.grantedMessage(req.credits));
    }
    setBusyId(null);
  }

  return (
    <div>
      {message && <div className={styles.resultBanner}>{message}</div>}

      {isLoading && <div className={styles.loading}>{t.loading}</div>}

      {!isLoading && requests.length === 0 && (
        <div className={styles.empty}>{t.empty}</div>
      )}

      {!isLoading && requests.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t.columns.request}</th>
                <th>{t.columns.user}</th>
                <th>{t.columns.pkg}</th>
                <th className={styles.num}>{t.columns.credits}</th>
                <th className={styles.num}>{t.columns.amount}</th>
                <th>{t.columns.date}</th>
                <th>{t.columns.action}</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => {
                const isBusy = busyId === r.id;
                return (
                  <tr key={r.id}>
                    <td className={styles.sub}>#{r.id}</td>
                    <td>#{r.user_id}</td>
                    <td>{r.package_key}</td>
                    <td className={styles.num}>{r.credits}</td>
                    <td className={styles.num}>
                      {r.price_try.toLocaleString(locale === "tr" ? "tr-TR" : "en-US")} TL
                    </td>
                    <td className={styles.sub}>{formatDate(r.created_at)}</td>
                    <td>
                      <button
                        type="button"
                        className={`${styles.act} ${styles.actApprove}`}
                        onClick={() => grant(r)}
                        disabled={isBusy}
                      >
                        {t.grantAction}
                      </button>
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
