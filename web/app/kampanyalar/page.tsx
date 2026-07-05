"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getMe, getToken, mySubmissions, type Submission, type User } from "@/lib/api";
import styles from "./page.module.css";

/** Sanatci kampanya gecmisi: gonderim durumu + kurator geri bildirimi + SLA. */
export default function KampanyalarPage() {
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [subs, setSubs] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      if (getToken()) {
        const me = await getMe();
        if (me && me.user.role === "artist") {
          setUser(me.user);
          const list = await mySubmissions();
          if (list) setSubs(list.reverse()); // en yeni ustte
        }
      }
      setChecked(true);
      setLoading(false);
    })();
  }, []);

  function statusInfo(s: Submission): { label: string; cls: string } {
    if (s.status === "accepted") return { label: "Kabul edildi", cls: styles.ok };
    if (s.status === "rejected") return { label: "Reddedildi (geri bildirim geldi)", cls: styles.warn };
    if (s.status === "expired") return { label: "Süre doldu — kredi iade edildi", cls: styles.refund };
    return { label: "Bekliyor (72 saat SLA)", cls: styles.pending };
  }

  if (checked && !user) {
    return (
      <div className={styles.gate}>
        <div className="nb-card" style={{ padding: 28, maxWidth: 460 }}>
          <h2 className="nb-h">Giriş gerekli</h2>
          <p style={{ fontWeight: 600, margin: "12px 0 20px" }}>
            Kampanya geçmişin için sanatçı hesabınla giriş yap.
          </p>
          <Link href="/giris" className="nb-btn">Giriş / Kayıt</Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <Link href="/" className={styles.logo}>MuzikSEO</Link>
        {user && (
          <div className={styles.wallet}>💳 {user.credits} kredi · {user.name}</div>
        )}
      </div>

      <h1 className="nb-h">Kampanya Geçmişi</h1>
      <div className={styles.subline}>
        <Link href="/gonder" className="nb-btn nb-btn--purple">+ Yeni Gönderim</Link>
      </div>

      {loading && <div className={styles.empty}>Yükleniyor...</div>}
      {!loading && subs.length === 0 && (
        <div className={styles.empty}>
          Henüz gönderim yok — <Link href="/gonder">ilk şarkını gönder</Link>.
        </div>
      )}

      {subs.map((s) => {
        const info = statusInfo(s);
        return (
          <div key={s.id} className={`nb-card ${styles.subCard}`}>
            <div className={styles.subHead}>
              <div>
                <div className={styles.subTitle}>
                  {s.artist} — {s.title}
                </div>
                <div className={styles.subMeta}>
                  Gönderim #{s.id} · {new Date(s.created_at).toLocaleString("tr-TR")}
                </div>
              </div>
              <span className={`${styles.pill} ${info.cls}`}>{info.label}</span>
            </div>
            {s.feedback && (
              <div className={styles.feedback}>
                <div className={styles.feedbackLabel}>Küratör geri bildirimi</div>
                {s.feedback}
              </div>
            )}
            {s.placement_verified === 1 && (
              <div className={styles.placement}>
                ✅ Playlist yerleşimi doğrulandı
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
