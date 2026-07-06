"use client";

import { useEffect, useState } from "react";
import { listAdminPayouts, markPayoutPaid, type AdminPayout } from "@/lib/api";
import styles from "./page.module.css";
import { formatDate } from "./utils";

type PayoutFilter = "requested" | "paid";

/** Admin: kurator payout kuyrugu — havale sonrasi elle "odendi" olarak isaretlenir. */
export default function PayoutsTab() {
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

  const emptyMessage =
    subFilter === "requested" ? "Bekleyen ödeme yok." : "Ödenmiş kayıt yok.";

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
          Bekleyen
        </button>
        <button
          type="button"
          className={
            subFilter === "paid" ? `${styles.filterBtn} ${styles.filterActive}` : styles.filterBtn
          }
          onClick={() => setSubFilter("paid")}
        >
          Ödenenler
        </button>
      </div>

      {isLoading && <div className={styles.loading}>Yükleniyor...</div>}

      {!isLoading && payouts.length === 0 && (
        <div className={styles.empty}>{emptyMessage}</div>
      )}

      {!isLoading && payouts.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Küratör</th>
                <th className={styles.num}>Tutar</th>
                <th className={styles.num}>Kesinti</th>
                <th>Anında mı</th>
                <th>Tarih</th>
                {subFilter === "requested" && <th>İşlem</th>}
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
                    <td>{p.instant ? "Evet" : "Hayır"}</td>
                    <td className={styles.sub}>{formatDate(p.created_at)}</td>
                    {subFilter === "requested" && (
                      <td>
                        <button
                          type="button"
                          className={`${styles.act} ${styles.actApprove}`}
                          onClick={() => markPaid(p.id)}
                          disabled={isBusy}
                        >
                          Havale Yapıldı
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
