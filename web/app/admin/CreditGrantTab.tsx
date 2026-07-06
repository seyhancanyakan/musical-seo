"use client";

import { useState } from "react";
import { adminGrantCredits, type User } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";

type ReasonKey = "purchase" | "grant" | "bonus";

const REASON_KEYS: ReasonKey[] = ["purchase", "grant", "bonus"];

const T = {
  tr: {
    reasons: {
      purchase: "Satın alma",
      grant: "Hediye",
      bonus: "Bonus",
    } as Record<ReasonKey, string>,
    userIdLabel: "Kullanıcı ID",
    userIdPlaceholder: "Örn. 42",
    amountLabel: "Miktar (kredi)",
    amountPlaceholder: "Örn. 10",
    reasonLabel: "Sebep",
    loadingBtn: "Yükleniyor...",
    submitBtn: "Yükle",
    errorMissing: "Kullanıcı ID ve miktar gerekli.",
    errorFailed: "Yükleme başarısız — kullanıcı bulunamadı olabilir.",
    resultText: (name: string, credits: number) =>
      `${name} — yeni bakiye: ${credits} kredi`,
  },
  en: {
    reasons: {
      purchase: "Purchase",
      grant: "Gift",
      bonus: "Bonus",
    } as Record<ReasonKey, string>,
    userIdLabel: "User ID",
    userIdPlaceholder: "e.g. 42",
    amountLabel: "Amount (credits)",
    amountPlaceholder: "e.g. 10",
    reasonLabel: "Reason",
    loadingBtn: "Granting...",
    submitBtn: "Grant",
    errorMissing: "User ID and amount are required.",
    errorFailed: "Grant failed — the user may not exist.",
    resultText: (name: string, credits: number) =>
      `${name} — new balance: ${credits} credits`,
  },
} as const;

/** Admin: manuel kredi yukleme formu (odeme pilotta elden alinir). */
export default function CreditGrantTab() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [userId, setUserId] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState<ReasonKey>(REASON_KEYS[0]);
  const [isSaving, setIsSaving] = useState(false);
  const [result, setResult] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const idNum = Number(userId);
    const amountNum = Number(amount);
    if (!idNum || !amountNum) {
      setError(t.errorMissing);
      setResult(null);
      return;
    }
    setError(null);
    setResult(null);
    setIsSaving(true);
    const updated = await adminGrantCredits(idNum, amountNum, reason);
    setIsSaving(false);
    if (updated) {
      setResult(updated);
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
          {t.amountLabel}
          <input
            className="nb-input"
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder={t.amountPlaceholder}
          />
        </label>
        <label className={styles.formLabel}>
          {t.reasonLabel}
          <select
            className="nb-input"
            value={reason}
            onChange={(e) => setReason(e.target.value as ReasonKey)}
          >
            {REASON_KEYS.map((key) => (
              <option key={key} value={key}>
                {t.reasons[key]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className={styles.formActions}>
        <button type="button" className="nb-btn" onClick={submit} disabled={isSaving}>
          {isSaving ? t.loadingBtn : t.submitBtn}
        </button>
      </div>
      {error && <div className={styles.errorBanner}>{error}</div>}
      {result && (
        <div className={styles.resultBanner}>
          {t.resultText(result.name, result.credits)}
        </div>
      )}
    </div>
  );
}
