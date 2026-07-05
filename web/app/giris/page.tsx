"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authLogin, authRegister, setToken } from "@/lib/api";
import styles from "./page.module.css";

type Mode = "login" | "register";
type Role = "artist" | "curator";

export default function GirisPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [role, setRole] = useState<Role>("artist");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [playlistUrl, setPlaylistUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");

    const result =
      mode === "login"
        ? await authLogin(email, password)
        : await authRegister({
            email,
            password,
            name,
            role,
            playlist_url: role === "curator" && playlistUrl ? playlistUrl : undefined,
          });

    setBusy(false);
    if (!result) {
      setError(
        mode === "login"
          ? "Giriş başarısız — e-posta/parolayı kontrol et."
          : "Kayıt başarısız — bilgileri kontrol et (parola en az 8 karakter)."
      );
      return;
    }

    setToken(result.token);
    router.push(result.user.role === "curator" ? "/curator/inbox" : "/gonder");
  }

  return (
    <div className={styles.wrap}>
      <Link href="/" className={styles.logo}>MuzikSEO</Link>

      <div className={`nb-card ${styles.card}`}>
        <div className={styles.tabs}>
          <button
            type="button"
            className={`${styles.tab} ${mode === "login" ? styles.tabOn : ""}`}
            onClick={() => setMode("login")}
          >
            Giriş
          </button>
          <button
            type="button"
            className={`${styles.tab} ${mode === "register" ? styles.tabOn : ""}`}
            onClick={() => setMode("register")}
          >
            Kayıt Ol
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          {mode === "register" && (
            <>
              <div className={styles.roleRow}>
                <button
                  type="button"
                  className={`${styles.roleBtn} ${role === "artist" ? styles.roleOn : ""}`}
                  onClick={() => setRole("artist")}
                >
                  🎤 Sanatçıyım
                </button>
                <button
                  type="button"
                  className={`${styles.roleBtn} ${role === "curator" ? styles.roleOn : ""}`}
                  onClick={() => setRole("curator")}
                >
                  🎧 Küratörüm
                </button>
              </div>
              <input
                className="nb-input"
                placeholder={role === "curator" ? "Küratör adı" : "Sanatçı adı"}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
              {role === "curator" && (
                <input
                  className="nb-input"
                  placeholder="Deezer playlist linki (opsiyonel — sonra da eklenebilir)"
                  value={playlistUrl}
                  onChange={(e) => setPlaylistUrl(e.target.value)}
                />
              )}
            </>
          )}

          <input
            className="nb-input"
            type="email"
            placeholder="E-posta"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            className="nb-input"
            type="password"
            placeholder="Parola (en az 8 karakter)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />

          {error && <div className={styles.error}>{error}</div>}

          <button type="submit" className="nb-btn" disabled={busy}>
            {busy ? "..." : mode === "login" ? "Giriş Yap" : "Hesap Aç"}
          </button>
        </form>

        {mode === "register" && role === "curator" && (
          <p className={styles.note}>
            Kaç şarkı dinleyeceğini sen seç. Her nitelikli geri bildirimden
            kazan. Şarkıyı ekleme zorunluluğun yok.
          </p>
        )}
        {mode === "register" && role === "artist" && (
          <p className={styles.note}>
            Şarkını doğru küratörlere gönder. 72 saatte gerçek dinleme ve
            yazılı geri bildirim al. Cevap yoksa kredin geri. Bot yok,
            playlist garantisi yok.
          </p>
        )}
      </div>
    </div>
  );
}
