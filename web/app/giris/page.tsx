"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authLogin, authRegister, setToken, type CuratorType } from "@/lib/api";
import styles from "./page.module.css";

type Mode = "login" | "register";
type Role = "artist" | "curator";

/** Groover paritesi: playlist kuratoru + 8 profesyonel tur. */
const CURATOR_TYPES: { value: CuratorType; label: string }[] = [
  { value: "playlist", label: "🎧 Playlist Küratörü" },
  { value: "radyo", label: "📻 Radyo" },
  { value: "medya", label: "📰 Medya / Blog" },
  { value: "label", label: "💿 Label" },
  { value: "menajer", label: "🧑‍💼 Menajer" },
  { value: "booker", label: "🎪 Booker" },
  { value: "dj", label: "🎛️ DJ" },
  { value: "mentor", label: "🎓 Mentor" },
  { value: "sync", label: "🎬 Sync Uzmanı" },
];

export default function GirisPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [role, setRole] = useState<Role>("artist");
  const [curatorType, setCuratorType] = useState<CuratorType>("playlist");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [playlistUrl, setPlaylistUrl] = useState("");
  const [referralCode, setReferralCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // URL'de ?ref=KOD varsa referans kodu inputunu otomatik doldur.
  useEffect(() => {
    const ref = new URLSearchParams(window.location.search).get("ref");
    if (ref) setReferralCode(ref);
  }, []);

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
            curator_type: role === "curator" ? curatorType : undefined,
            referral_code: referralCode.trim() || undefined,
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
                <>
                  <select
                    className="nb-input"
                    value={curatorType}
                    onChange={(e) => setCuratorType(e.target.value as CuratorType)}
                    aria-label="Küratör türü"
                  >
                    {CURATOR_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                  {(curatorType === "playlist" || curatorType === "dj") && (
                    <input
                      className="nb-input"
                      placeholder="Deezer veya Spotify playlist linki (opsiyonel — sonra da eklenebilir)"
                      value={playlistUrl}
                      onChange={(e) => setPlaylistUrl(e.target.value)}
                    />
                  )}
                </>
              )}
              <input
                className="nb-input"
                placeholder="Referans kodu (varsa)"
                value={referralCode}
                onChange={(e) => setReferralCode(e.target.value)}
              />
              <p className={styles.referralNote}>
                Davet kodun ile gelirsen ilk gönderiminde ikiniz de +1 kredi
                kazanırsınız.
              </p>
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
            {curatorType !== "playlist" &&
              " Playlist dışı başvurular ekip onayından sonra açılır."}
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
