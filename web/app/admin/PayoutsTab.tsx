"use client";

import { useEffect, useState } from "react";
import { listAdminPayouts, markPayoutPaid, type AdminPayout } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";
import { formatDate } from "./utils";

type PayoutFilter = "requested" | "paid";

const T = {
  tr: {
    requested: "Bekleyen",
    paid: "Ödenenler",
    loading: "Yükleniyor...",
    emptyRequested: "Bekleyen ödeme yok.",
    emptyPaid: "Ödenmiş kayıt yok.",
    columns: {
      curator: "Küratör",
      amount: "Tutar",
      fee: "Kesinti",
      instant: "Anında mı",
      date: "Tarih",
      action: "İşlem",
    },
    yes: "Evet",
    no: "Hayır",
    markPaid: "Havale Yapıldı",
  },
  en: {
    requested: "Pending",
    paid: "Paid",
    loading: "Loading...",
    emptyRequested: "No pending payouts.",
    emptyPaid: "No paid records.",
    columns: {
      curator: "Curator",
      amount: "Amount",
      fee: "Fee",
      instant: "Instant",
      date: "Date",
      action: "Action",
    },
    yes: "Yes",
    no: "No",
    markPaid: "Transfer Sent",
  },
} as const;

/** Admin: kurator payout kuyrugu — havale sonrasi elle "odendi" olarak isaretlenir. */
export default function PayoutsTab() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [subFilter, setSubFilter] = useState<PayoutFilter>("requested");
  const [payouts, setPayouts] = useState<AdminPayout[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    listAdminPayouts(subFilter).then((data) => {
      if (cancelled) return;
      setPayouts(data ?? []);
      setIsLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [subFilter]);

  async function markPaid(id: number) {
    setBusyId(id);
    const updated = await markPayoutPaid(id);
    if (updated) {
      setPayouts((prev) => prev.filter((p) => p.id !== id));
    }
    setBusyId(null);
  }

  const emptyMessage = subFilter === "requested" ? t.emptyRequested : t.emptyPaid;

  return (
    <div>
      <div className={styles.filters}>
        <button
          type="button"
          className={
            subFilter === "requested"
              ? `${styles.filterBtn} ${styles.filterActive}`
              : styles.filterBtn
          }
          onClick={() => setSubFilter("requested")}
        >
          {t.requested}
        </button>
        <button
          type="button"
          className={
            subFilter === "paid" ? `${styles.filterBtn} ${styles.filterActive}` : styles.filterBtn
          }
          onClick={() => setSubFilter("paid")}
        >
          {t.paid}
        </button>
      </div>

      {isLoading && <div className={styles.loading}>{t.loading}</div>}

      {!isLoading && payouts.length === 0 && (
        <div className={styles.empty}>{emptyMessage}</div>
      )}

      {!isLoading && payouts.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t.columns.curator}</th>
                <th className={styles.num}>{t.columns.amount}</th>
                <th className={styles.num}>{t.columns.fee}</th>
                <th>{t.columns.instant}</th>
                <th>{t.columns.date}</th>
                {subFilter === "requested" && <th>{t.columns.action}</th>}
              </tr>
            </thead>
            <tbody>
              {payouts.map((p) => {
                const isBusy = busyId === p.id;
                return (
                  <tr key={p.id}>
                    <td>
                      <div className={styles.name}>{p.curator_name}</div>
                      <a className={styles.email} href={`mailto:${p.curator_email}`}>
                        {p.curator_email}
                      </a>
                    </td>
                    <td className={styles.num}>${p.amount_usd.toFixed(2)}</td>
                    <td className={styles.num}>${p.fee_usd.toFixed(2)}</td>
                    <td>{p.instant ? t.yes : t.no}</td>
                    <td className={styles.sub}>{formatDate(p.created_at)}</td>
                    {subFilter === "requested" && (
                      <td>
                        <button
                          type="button"
                          className={`${styles.act} ${styles.actApprove}`}
                          onClick={() => markPaid(p.id)}
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
