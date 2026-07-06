"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getImpact,
  getMe,
  getToken,
  mySubmissions,
  openCertificate,
  openShareCard,
  verifyPlacementSelf,
  type ImpactReport,
  type Submission,
  type User,
} from "@/lib/api";
import styles from "./page.module.css";

/** Etki raporu paneli: once/sonra skor + delta (pozitifse yesil). */
function ImpactPanel({ data }: { data: ImpactReport | null | undefined }) {
  if (data === undefined) return <div className={styles.impactMsg}>Yükleniyor...</div>;
  if (data === null) return <div className={styles.impactMsg}>Etki raporu yüklenemedi — tekrar dene.</div>;

  const delta = data.score_delta;
  const deltaCls =
    delta !== null && delta > 0 ? styles.deltaUp : delta !== null && delta < 0 ? styles.deltaDown : "";

  return (
    <div className={styles.impactPanel}>
      <div className={styles.impactGrid}>
        <div className={styles.impactBox}>
          <div className={styles.impactLabel}>Önce</div>
          <div className={styles.impactScore}>{data.before.score ?? "—"}</div>
        </div>
        <div className={styles.impactArrow}>→</div>
        <div className={styles.impactBox}>
          <div className={styles.impactLabel}>Sonra</div>
          <div className={styles.impactScore}>{data.after.score ?? "—"}</div>
        </div>
        {delta !== null && (
          <div className={`${styles.impactDelta} ${deltaCls}`}>
            {delta > 0 ? "+" : ""}
            {delta}
          </div>
        )}
      </div>
      {!data.placement_verified && (
        <div className={styles.impactMsg}>
          Yerleşim henüz doğrulanmadı — rapor ön veriyle gösteriliyor.
        </div>
      )}
    </div>
  );
}

const READINESS_READY_MIN = 70;

/** Sanatci kampanya gecmisi: gonderim durumu + kurator geri bildirimi + SLA. */
export default function KampanyalarPage() {
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [subs, setSubs] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);

  // Yerlesim self-servis dogrulama
  const [verifyBusyId, setVerifyBusyId] = useState<number | null>(null);
  const [verifyMsgs, setVerifyMsgs] = useState<Record<number, string>>({});

  // Sertifika / kanit karti / etki raporu
  const [certBusyId, setCertBusyId] = useState<number | null>(null);
  const [shareBusyId, setShareBusyId] = useState<number | null>(null);
  const [certMsgs, setCertMsgs] = useState<Record<number, string>>({});
  const [expandedImpactId, setExpandedImpactId] = useState<number | null>(null);
  const [impactData, setImpactData] = useState<Record<number, ImpactReport | null | undefined>>({});

  function updateSub(id: number, patch: Partial<Submission>) {
    setSubs((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  async function handleVerify(id: number) {
    setVerifyBusyId(id);
    setVerifyMsgs((prev) => ({ ...prev, [id]: "" }));
    const updated = await verifyPlacementSelf(id);
    setVerifyBusyId(null);
    if (!updated) {
      setVerifyMsgs((prev) => ({ ...prev, [id]: "Doğrulama başarısız — tekrar dene." }));
      return;
    }
    updateSub(id, updated);
    setVerifyMsgs((prev) => ({
      ...prev,
      [id]:
        updated.placement_verified === 1
          ? "🎉 Doğrulandı! Şarkın playlistte yerini aldı."
          : "Henüz playlistte görünmüyor — kürator eklemesi 1-2 gün sürebilir.",
    }));
  }

  async function handleCertificate(id: number) {
    setCertBusyId(id);
    setCertMsgs((prev) => ({ ...prev, [id]: "" }));
    const url = await openCertificate(id);
    setCertBusyId(null);
    if (url) {
      window.open(url, "_blank");
    } else {
      setCertMsgs((prev) => ({ ...prev, [id]: "Sertifika açılamadı — tekrar dene." }));
    }
  }

  async function handleShareCard(id: number) {
    setShareBusyId(id);
    setCertMsgs((prev) => ({ ...prev, [id]: "" }));
    const url = await openShareCard(id);
    setShareBusyId(null);
    if (url) {
      window.open(url, "_blank");
    } else {
      setCertMsgs((prev) => ({ ...prev, [id]: "Kanıt kartı açılamadı — tekrar dene." }));
    }
  }

  async function handleImpact(id: number) {
    if (expandedImpactId === id) {
      setExpandedImpactId(null);
      return;
    }
    setExpandedImpactId(id);
    if (impactData[id] === undefined) {
      const data = await getImpact(id);
      setImpactData((prev) => ({ ...prev, [id]: data }));
    }
  }

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
        const readinessReady =
          typeof s.readiness_score === "number" && s.readiness_score >= READINESS_READY_MIN;

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
                <div className={styles.badgeRow}>
                  {typeof s.cost_credits === "number" && (
                    <span className="nb-pill nb-pill--blue">{s.cost_credits} kredi</span>
                  )}
                  {s.guaranteed === 1 && (
                    <span className="nb-pill nb-pill--green">Garantili (2x iade)</span>
                  )}
                  {s.priority === 1 && (
                    <span className="nb-pill nb-pill--purple">Öne çıkan</span>
                  )}
                  {readinessReady && (
                    <span className="nb-pill nb-pill--green">Yayına Hazır</span>
                  )}
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

            {s.status === "accepted" && s.placement_verified === 0 && (
              <div className={styles.verifyBlock}>
                <button
                  type="button"
                  className="nb-btn nb-btn--outline"
                  disabled={verifyBusyId === s.id}
                  onClick={() => handleVerify(s.id)}
                >
                  {verifyBusyId === s.id ? "Kontrol ediliyor..." : "Yerleşimi Doğrula"}
                </button>
                {verifyMsgs[s.id] && (
                  <div
                    className={
                      verifyMsgs[s.id].startsWith("🎉") ? styles.verifyOk : styles.verifyInfo
                    }
                  >
                    {verifyMsgs[s.id]}
                  </div>
                )}
              </div>
            )}

            {s.placement_verified === 1 && (
              <>
                <div className={styles.placement}>✅ Playlist yerleşimi doğrulandı</div>
                <div className={styles.provenActions}>
                  <button
                    type="button"
                    className="nb-btn"
                    disabled={certBusyId === s.id}
                    onClick={() => handleCertificate(s.id)}
                  >
                    {certBusyId === s.id ? "Hazırlanıyor..." : "Sertifika"}
                  </button>
                  <button
                    type="button"
                    className="nb-btn"
                    disabled={shareBusyId === s.id}
                    onClick={() => handleShareCard(s.id)}
                  >
                    {shareBusyId === s.id ? "Hazırlanıyor..." : "Kanıt Kartı (Story)"}
                  </button>
                  <button
                    type="button"
                    className="nb-btn nb-btn--purple"
                    onClick={() => handleImpact(s.id)}
                  >
                    {expandedImpactId === s.id ? "Etki Raporunu Kapat" : "Etki Raporu"}
                  </button>
                  {!s.certificate_token && (
                    <span className={styles.hint}>İlk üretim 1 kredi düşer</span>
                  )}
                </div>
                {certMsgs[s.id] && <div className={styles.verifyInfo}>{certMsgs[s.id]}</div>}
                {expandedImpactId === s.id && <ImpactPanel data={impactData[s.id]} />}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
