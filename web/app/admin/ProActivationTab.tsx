"use client";

import { useState } from "react";
import { activatePro, type User } from "@/lib/api";
import styles from "./page.module.css";
import { formatDate } from "./utils";

const PRO_DURATIONS: { key: string; label: string; months: number }[] = [
  { key: "1m", label: "1 ay", months: 1 },
  { key: "3m", label: "3 ay", months: 3 },
  { key: "12m", label: "12 ay", months: 12 },
];

function monthsFromNowIso(months: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() + months);
  return d.toISOString();
}

/** Admin: kullanicinin Artist Pro'sunu bugunden itibaren N ay aktif eder. */
export default function ProActivationTab() {
  const [userId, setUserId] = useState("");
  const [duration, setDuration] = useState(PRO_DURATIONS[0].key);
  const [isSaving, setIsSaving] = useState(false);
  const [result, setResult] = useState<{ user: User; untilIso: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const idNum = Number(userId);
    if (!idNum) {
      setError("Kullanıcı ID gerekli.");
      setResult(null);
      return;
    }
    const months = PRO_DURATIONS.find((d) => d.key === duration)?.months ?? 1;
    const untilIso = monthsFromNowIso(months);
    setError(null);
    setResult(null);
    setIsSaving(true);
    const updated = await activatePro(idNum, untilIso);
    setIsSaving(false);
    if (updated) {
      setResult({ user: updated, untilIso });
    } else {
      setError("Aktivasyon başarısız — kullanıcı bulunamadı olabilir.");
    }
  }

  return (
    <div className={styles.formCard}>
      <div className={styles.formGrid}>
        <label className={styles.formLabel}>
          Kullanıcı ID
          <input
            className="nb-input"
            type="number"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="Örn. 42"
          />
        </label>
        <label className={styles.formLabel}>
          Süre
          <select
            className="nb-input"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
          >
            {PRO_DURATIONS.map((d) => (
              <option key={d.key} value={d.key}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className={styles.formActions}>
        <button type="button" className="nb-btn" onClick={submit} disabled={isSaving}>
          {isSaving ? "Aktifleştiriliyor..." : "Aktifleştir"}
        </button>
      </div>
      {error && <div className={styles.errorBanner}>{error}</div>}
      {result && (
        <div className={styles.resultBanner}>
          {result.user.name} için Pro aktifleştirildi — bitiş: {formatDate(result.untilIso)}
        </div>
      )}
    </div>
  );
}
