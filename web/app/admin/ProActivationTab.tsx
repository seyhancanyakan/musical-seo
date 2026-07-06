"use client";

import { useState } from "react";
import { activatePro, type User } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";
import { formatDate } from "./utils";

type DurationKey = "1m" | "3m" | "12m";

const DURATIONS: { key: DurationKey; months: number }[] = [
  { key: "1m", months: 1 },
  { key: "3m", months: 3 },
  { key: "12m", months: 12 },
];

const T = {
  tr: {
    durationLabels: {
      "1m": "1 ay",
      "3m": "3 ay",
      "12m": "12 ay",
    } as Record<DurationKey, string>,
    userIdLabel: "Kullanıcı ID",
    userIdPlaceholder: "Örn. 42",
    durationLabel: "Süre",
    activatingBtn: "Aktifleştiriliyor...",
    activateBtn: "Aktifleştir",
    errorMissing: "Kullanıcı ID gerekli.",
    errorFailed: "Aktivasyon başarısız — kullanıcı bulunamadı olabilir.",
    resultText: (name: string, until: string) =>
      `${name} için Pro aktifleştirildi — bitiş: ${until}`,
  },
  en: {
    durationLabels: {
      "1m": "1 month",
      "3m": "3 months",
      "12m": "12 months",
    } as Record<DurationKey, string>,
    userIdLabel: "User ID",
    userIdPlaceholder: "e.g. 42",
    durationLabel: "Duration",
    activatingBtn: "Activating...",
    activateBtn: "Activate",
    errorMissing: "User ID is required.",
    errorFailed: "Activation failed — the user may not exist.",
    resultText: (name: string, until: string) =>
      `Pro activated for ${name} — ends: ${until}`,
  },
} as const;

function monthsFromNowIso(months: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() + months);
  return d.toISOString();
}

/** Admin: kullanicinin Artist Pro'sunu bugunden itibaren N ay aktif eder. */
export default function ProActivationTab() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [userId, setUserId] = useState("");
  const [duration, setDuration] = useState<DurationKey>(DURATIONS[0].key);
  const [isSaving, setIsSaving] = useState(false);
  const [result, setResult] = useState<{ user: User; untilIso: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const idNum = Number(userId);
    if (!idNum) {
      setError(t.errorMissing);
      setResult(null);
      return;
    }
    const months = DURATIONS.find((d) => d.key === duration)?.months ?? 1;
    const untilIso = monthsFromNowIso(months);
    setError(null);
    setResult(null);
    setIsSaving(true);
    const updated = await activatePro(idNum, untilIso);
    setIsSaving(false);
    if (updated) {
      setResult({ user: updated, untilIso });
    } else {
      setError(t.errorFailed);
    }
  }

  return (
    <div className={styles.formCard}>
      <div className={styles.formGrid}>
        <label className={styles.formLabel}>
          {t.userIdLabel}
          <input
            className="nb-input"
            type="number"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder={t.userIdPlaceholder}
          />
        </label>
        <label className={styles.formLabel}>
          {t.durationLabel}
          <select
            className="nb-input"
            value={duration}
            onChange={(e) => setDuration(e.target.value as DurationKey)}
          >
            {DURATIONS.map((d) => (
              <option key={d.key} value={d.key}>
                {t.durationLabels[d.key]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className={styles.formActions}>
        <button type="button" className="nb-btn" onClick={submit} disabled={isSaving}>
          {isSaving ? t.activatingBtn : t.activateBtn}
        </button>
      </div>
      {error && <div className={styles.errorBanner}>{error}</div>}
      {result && (
        <div className={styles.resultBanner}>
          {t.resultText(result.user.name, formatDate(result.untilIso))}
        </div>
      )}
    </div>
  );
}
