"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getMe,
  getToken,
  listCurators,
  submitToCurator,
  type Curator,
  type User,
} from "@/lib/api";
import styles from "./page.module.css";

/** Sanatci gonderim ekrani — cekirdek dongunun panel ayagi:
 *  kredi bakiyesi + onayli kurator katalogu + 1 kredilik gercek gonderim. */
export default function GonderPage() {
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [curators, setCurators] = useState<Curator[]>([]);
  const [song, setSong] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [sentIds, setSentIds] = useState<Record<number, boolean>>({});
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      if (getToken()) {
        const me = await getMe();
        if (me) setUser(me.user);
      }
      setChecked(true);
      const list = await listCurators();
      if (list) setCurators(list.filter((c) => c.status === "approved"));
    })();
  }, []);

  function parseSong(): { artist: string; title: string } | null {
    const raw = song.trim();
    if (!raw.includes(" - ")) return null;
    const [artist, ...rest] = raw.split(" - ");
    const title = rest.join(" - ").trim();
    if (!artist.trim() || !title) return null;
    return { artist: artist.trim(), title };
  }

  async function handleSubmit(curator: Curator) {
    setError("");
    const parsed = parseSong();
    if (!parsed) {
      setError('Şarkıyı "Sanatçı - Şarkı" formatında yaz (ör. Seyhan Canyakan - Serenity).');
      return;
    }
    if (!user || user.credits < 1) {
      setError("Kredin yok — pilot döneminde kredi için bize ulaş.");
      return;
    }
    setBusyId(curator.id);
    const sub = await submitToCurator(parsed.artist, parsed.title, curator.id);
    setBusyId(null);
    if (!sub) {
      setError("Gönderim başarısız — şarkı Deezer'da bulunamadı ya da kredi yetersiz.");
      return;
    }
    setSentIds((prev) => ({ ...prev, [curator.id]: true }));
    setUser((prev) => (prev ? { ...prev, credits: prev.credits - 1 } : prev));
  }

  if (checked && !user) {
    return (
      <div className={styles.gate}>
        <div className="nb-card" style={{ padding: 28, maxWidth: 460 }}>
          <h2 className="nb-h">Giriş gerekli</h2>
          <p className={styles.gateText}>
            Şarkı göndermek için sanatçı hesabınla giriş yap.
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
          <div className={styles.wallet}>
            💳 {user.credits} kredi · {user.name}
          </div>
        )}
      </div>

      <h1 className="nb-h">Şarkını Küratörlere Gönder</h1>
      <p className={styles.promise}>
        72 saatte gerçek dinleme ve yazılı geri bildirim. Cevap yoksa kredin
        geri. Playlist garantisi satmıyoruz — Spotify kuralları gereği zaten
        kimse satamaz.
      </p>

      <input
        className={`nb-input ${styles.songInput}`}
        placeholder='Şarkın: "Sanatçı - Şarkı" (ör. Seyhan Canyakan - Serenity)'
        value={song}
        onChange={(e) => setSong(e.target.value)}
      />

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.list}>
        {curators.length === 0 && (
          <div className={styles.empty}>
            Henüz onaylı küratör yok — başvurular değerlendiriliyor.
          </div>
        )}
        {curators.map((c) => (
          <div key={c.id} className={`nb-card ${styles.curatorCard}`}>
            <div>
              <div className={styles.curatorName}>{c.playlist_title}</div>
              <div className={styles.curatorMeta}>
                {c.name} · {c.fans.toLocaleString("tr-TR")} fan ·{" "}
                {c.track_count} parça · kalite {c.quality_score}
              </div>
            </div>
            <button
              type="button"
              className={`nb-btn ${styles.sendBtn}`}
              disabled={busyId === c.id || sentIds[c.id]}
              onClick={() => handleSubmit(c)}
            >
              {sentIds[c.id]
                ? "✓ Gönderildi"
                : busyId === c.id
                  ? "..."
                  : "Gönder (1 kredi)"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
