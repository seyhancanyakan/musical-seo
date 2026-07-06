"use client";

import { useState } from "react";
import { adminGrantCredits, type User } from "@/lib/api";
import styles from "./page.module.css";

const CREDIT_REASONS: { key: string; label: string }[] = [
  { key: "purchase", label: "Satın alma" },
  { key: "grant", label: "Hediye" },
  { key: "bonus", label: "Bonus" },
];

/** Admin: manuel kredi yukleme formu (odeme pilotta elden alinir). */
export default function CreditGrantTab() {
  const [userId, setUserId] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState(CREDIT_REASONS[0].key);
  const [isSaving, setIsSaving] = useState(false);
  const [result, setResult] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const idNum = Number(userId);
    const amountNum = Number(amount);
    if (!idNum || !amountNum) {
      setError("Kullanıcı ID ve miktar gerekli.");
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
      setError("Yükleme başarısız — kullanıcı bulunamadı olabilir.");
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
          Miktar (kredi)
          <input
            className="nb-input"
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Örn. 10"
          />
        </label>
        <label className={styles.formLabel}>
          Sebep
          <select
            className="nb-input"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          >
            {CREDIT_REASONS.map((r) => (
              <option key={r.key} value={r.key}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className={styles.formActions}>
        <button type="button" className="nb-btn" onClick={submit} disabled={isSaving}>
          {isSaving ? "Yükleniyor..." : "Yükle"}
        </button>
      </div>
      {error && <div className={styles.errorBanner}>{error}</div>}
      {result && (
        <div className={styles.resultBanner}>
          {result.name} — yeni bakiye: {result.credits} kredi
        </div>
      )}
    </div>
  );
}
