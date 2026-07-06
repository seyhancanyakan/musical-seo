"use client";

import { useEffect, useState } from "react";
import { adminRadioAdMarkPaid, adminRadioAdOrders, type RadioAdOrder } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";
import { formatDate } from "./utils";

type OrderFilter = "accepted" | "paid" | "airing";

const BUYER_KIND_LABELS = {
  tr: { artist: "Sanatçı", business: "İşletme" } as Record<string, string>,
  en: { artist: "Artist", business: "Business" } as Record<string, string>,
} as const;

const T = {
  tr: {
    accepted: "Kabul Edilen",
    paid: "Ödenen",
    airing: "Yayında",
    loading: "Yükleniyor...",
    emptyAccepted: "Kabul edilmiş sipariş yok.",
    emptyPaid: "Ödenmiş sipariş yok.",
    emptyAiring: "Yayında sipariş yok.",
    columns: {
      listing: "İlan",
      buyer: "Alıcı",
      weeks: "Hafta",
      amount: "Tutar",
      commission: "Komisyon",
      verifiedPlays: "Doğrulanan Yayın",
      date: "Tarih",
      action: "İşlem",
    },
    buyerKindLabels: BUYER_KIND_LABELS.tr,
    markPaid: "Ödeme Alındı",
  },
  en: {
    accepted: "Accepted",
    paid: "Paid",
    airing: "Airing",
    loading: "Loading...",
    emptyAccepted: "No accepted orders.",
    emptyPaid: "No paid orders.",
    emptyAiring: "No airing orders.",
    columns: {
      listing: "Listing",
      buyer: "Buyer",
      weeks: "Weeks",
      amount: "Amount",
      commission: "Commission",
      verifiedPlays: "Verified Plays",
      date: "Date",
      action: "Action",
    },
    buyerKindLabels: BUYER_KIND_LABELS.en,
    markPaid: "Payment Received",
  },
} as const;

const FILTER_KEYS: OrderFilter[] = ["accepted", "paid", "airing"];

function emptyMessageFor(
  filter: OrderFilter,
  t: { emptyAccepted: string; emptyPaid: string; emptyAiring: string }
): string {
  if (filter === "paid") return t.emptyPaid;
  if (filter === "airing") return t.emptyAiring;
  return t.emptyAccepted;
}

/** Admin: radyo reklam siparis kuyrugu — kabul edilenler icin odeme onayi. */
export default function RadioAdsTab() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [filter, setFilter] = useState<OrderFilter>("accepted");
  const [orders, setOrders] = useState<RadioAdOrder[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    adminRadioAdOrders(filter).then((data) => {
      if (cancelled) return;
      setOrders(data ?? []);
      setIsLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  async function markPaid(id: number) {
    setBusyId(id);
    const updated = await adminRadioAdMarkPaid(id);
    if (updated) {
      setOrders((prev) => prev.filter((o) => o.id !== id));
    }
    setBusyId(null);
  }

  const emptyMessage = emptyMessageFor(filter, t);

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
            {t[key]}
          </button>
        ))}
      </div>

      {isLoading && <div className={styles.loading}>{t.loading}</div>}

      {!isLoading && orders.length === 0 && (
        <div className={styles.empty}>{emptyMessage}</div>
      )}

      {!isLoading && orders.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t.columns.listing}</th>
                <th>{t.columns.buyer}</th>
                <th className={styles.num}>{t.columns.weeks}</th>
                <th className={styles.num}>{t.columns.amount}</th>
                <th className={styles.num}>{t.columns.commission}</th>
                <th className={styles.num}>{t.columns.verifiedPlays}</th>
                <th>{t.columns.date}</th>
                {filter === "accepted" && <th>{t.columns.action}</th>}
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => {
                const isBusy = busyId === o.id;
                return (
                  <tr key={o.id}>
                    <td>
                      <div className={styles.sub}>#{o.listing_id}</div>
                    </td>
                    <td>
                      <div className={styles.name}>{o.buyer_name}</div>
                      <a className={styles.email} href={`mailto:${o.buyer_email}`}>
                        {o.buyer_email}
                      </a>
                      <div className={styles.sub}>
                        {t.buyerKindLabels[o.buyer_kind] ?? o.buyer_kind}
                      </div>
                    </td>
                    <td className={styles.num}>{o.weeks}</td>
                    <td className={styles.num}>{o.price_try} TL</td>
                    <td className={styles.num}>{o.commission_try} TL</td>
                    <td className={styles.num}>{o.verified_plays}</td>
                    <td className={styles.sub}>{formatDate(o.created_at)}</td>
                    {filter === "accepted" && (
                      <td>
                        <button
                          type="button"
                          className={`${styles.act} ${styles.actApprove}`}
                          onClick={() => markPaid(o.id)}
                          disabled={isBusy}
                        >
                          {t.markPaid}
                        </button>
                      </td>
                    )}
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
