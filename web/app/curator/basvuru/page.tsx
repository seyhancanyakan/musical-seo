"use client";

import { useState, type FormEvent } from "react";
import { applyCurator, type Curator } from "@/lib/api";
import styles from "./page.module.css";

/** Mockup'taki demo sonucu birebir yansitir (API'ye ulasilamadiginda gosterilir). */
const DEMO_RESULT: Curator = {
  id: 0,
  created_at: "2026-07-04T10:30:00+00:00",
  name: "Demo Küratör",
  email: "demo@curator.example",
  deezer_playlist_id: "7841203955",
  playlist_title: "Türk",
  playlist_url: "https://deezer.com/playlist/7841203955",
  fans: 0,
  track_count: 47,
  diversity: 0.28,
  quality_score: 25.6,
  status: "approved",
};

const CHECKLIST_ITEMS = [
  "Playlist herkese açık ve aktif olarak güncelleniyor",
  "Takipçi/fan oranı bot davranışı sınırının altında",
  "Sanatçı çeşitliliği minimum eşiği karşılıyor",
];

export default function CuratorBasvuruPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [playlistUrl, setPlaylistUrl] = useState(
    "https://deezer.com/playlist/7841203955"
  );
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Curator | null>(null);
  const [isDemo, setIsDemo] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);

    const response = await applyCurator({
      name,
      email,
      playlist_url: playlistUrl,
    });

    if (response) {
      setResult(response);
      setIsDemo(false);
    } else {
      setResult(DEMO_RESULT);
      setIsDemo(true);
    }

    setLoading(false);
  }

  const stampClass =
    result?.status === "approved"
      ? `${styles.stamp} ${styles.stampApproved}`
      : result?.status === "pending"
        ? `${styles.stamp} ${styles.stampPending}`
        : `${styles.stamp} ${styles.stampNeutral}`;

  return (
    <>
      <nav className={styles.topbar}>
        <div className={styles.topbarInner}>
          <div className={styles.logo}>MuzikSEO</div>
        </div>
      </nav>

      <div className={styles.centerWrap}>
        <h1 className={styles.pageTitle}>LİSTENLE PARA KAZAN</h1>
        <p className={styles.sub}>
          Deezer playlist&apos;ini bağla, otomatik doğrulama sonucunu 30
          saniyede gör.
        </p>

        <form className={styles.form} onSubmit={handleSubmit}>
          <input
            className={styles.input}
            type="text"
            required
            placeholder="Adın Soyadın"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <input
            className={styles.input}
            type="email"
            required
            placeholder="E-posta adresin"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <div className={styles.urlRow}>
            <input
              className={styles.input}
              type="text"
              required
              placeholder="Deezer playlist URL'ini yapıştır"
              value={playlistUrl}
              onChange={(event) => setPlaylistUrl(event.target.value)}
            />
            <button className={styles.btn} type="submit" disabled={loading}>
              {loading ? "Doğrulanıyor…" : "Doğrula"}
            </button>
          </div>
        </form>
        <div className={styles.note}>
          Not: Listeni botlara karşı otomatik doğruluyoruz.
        </div>

        {isDemo && (
          <div className={styles.demoBanner}>
            API&apos;ye ulaşılamadı — demo sonuç gösteriliyor.
          </div>
        )}

        {result && (
          <div className={styles.resultCard}>
            <div className={stampClass}>
              {result.status === "approved" ? (
                <>
                  Otomatik
                  <br />
                  Onaylandı
                </>
              ) : result.status === "pending" ? (
                "İncelemede"
              ) : (
                result.status
              )}
            </div>
            <div className={styles.resultTop}>
              <div>
                <div className={styles.resultName}>
                  &ldquo;{result.playlist_title}&rdquo;
                </div>
                <div className={styles.resultMeta}>
                  {result.track_count} parça · Çeşitlilik{" "}
                  {result.diversity.toFixed(2)} · Kalite{" "}
                  {result.quality_score.toFixed(1)} / 100
                </div>
              </div>
            </div>
            <div className={styles.checklist}>
              {CHECKLIST_ITEMS.map((item, index) => (
                <div className={styles.checkItem} key={item}>
                  <div className={styles.checkBox}>{index + 1}</div> {item}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className={styles.footnote}>
          Doğrulama sonrası listenle eşleşen pitch&apos;ler gelen kutuna
          düşmeye başlar. Her kabul ettiğin yerleşim için kazanç panelinden
          ödeme takip edebilirsin.
        </div>
      </div>
    </>
  );
}
