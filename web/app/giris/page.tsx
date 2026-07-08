"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authLogin, authRegister, setToken, type CuratorType } from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type Mode = "login" | "register";
type Role = "artist" | "curator";

/** Groover paritesi: playlist kuratoru + 8 profesyonel tur. */
const CURATOR_TYPE_VALUES: CuratorType[] = [
  "playlist",
  "radyo",
  "medya",
  "label",
  "menajer",
  "booker",
  "dj",
  "mentor",
  "sync",
];

const T = {
  tr: {
    tabLogin: "Giriş",
    tabRegister: "Kayıt Ol",
    roleArtist: "🎤 Sanatçıyım",
    roleCurator: "🎧 Küratörüm",
    namePlaceholderCurator: "Küratör adı",
    namePlaceholderArtist: "Sanatçı adı",
    curatorTypeAria: "Küratör türü",
    curatorTypes: {
      playlist: "🎧 Playlist Küratörü",
      radyo: "📻 Radyo",
      medya: "📰 Medya / Blog",
      label: "💿 Label",
      menajer: "🧑‍💼 Menajer",
      booker: "🎪 Booker",
      dj: "🎛️ DJ",
      mentor: "🎓 Mentor",
      sync: "🎬 Sync Uzmanı",
    } as Record<CuratorType, string>,
    playlistUrlPlaceholder:
      "Deezer veya Spotify playlist linki (opsiyonel — sonra da eklenebilir)",
    referralPlaceholder: "Referans kodu (varsa)",
    referralNote:
      "Davet kodun ile gelirsen ilk gönderiminde ikiniz de +1 kredi kazanırsınız.",
    emailPlaceholder: "E-posta",
    passwordPlaceholder: "Parola (en az 8 karakter)",
    errorLogin: "Giriş başarısız — e-posta/parolayı kontrol et.",
    errorRegister:
      "Kayıt başarısız — bilgileri kontrol et (parola en az 8 karakter).",
    busy: "...",
    submitLogin: "Giriş Yap",
    submitRegister: "Hesap Aç",
    noteCuratorBase:
      "Kaç şarkı dinleyeceğini sen seç. Her nitelikli geri bildirimden kazan. Şarkıyı ekleme zorunluluğun yok.",
    noteCuratorNonPlaylist: " Playlist dışı başvurular ekip onayından sonra açılır.",
    noteArtist:
      "Şarkını doğru küratörlere gönder. 72 saatte gerçek dinleme ve yazılı geri bildirim al. Cevap yoksa kredin geri. Bot yok, playlist garantisi yok.",
  },
  en: {
    tabLogin: "Login",
    tabRegister: "Sign Up",
    roleArtist: "🎤 I'm an Artist",
    roleCurator: "🎧 I'm a Curator",
    namePlaceholderCurator: "Curator name",
    namePlaceholderArtist: "Artist name",
    curatorTypeAria: "Curator type",
    curatorTypes: {
      playlist: "🎧 Playlist Curator",
      radyo: "📻 Radio",
      medya: "📰 Media / Blog",
      label: "💿 Label",
      menajer: "🧑‍💼 Manager",
      booker: "🎪 Booker",
      dj: "🎛️ DJ",
      mentor: "🎓 Mentor",
      sync: "🎬 Sync Specialist",
    } as Record<CuratorType, string>,
    playlistUrlPlaceholder:
      "Deezer or Spotify playlist link (optional — can be added later)",
    referralPlaceholder: "Referral code (if any)",
    referralNote:
      "If you sign up with a referral code, you both earn +1 credit on your first submission.",
    emailPlaceholder: "Email",
    passwordPlaceholder: "Password (at least 8 characters)",
    errorLogin: "Login failed — check your email/password.",
    errorRegister:
      "Registration failed — check your details (password must be at least 8 characters).",
    busy: "...",
    submitLogin: "Log In",
    submitRegister: "Create Account",
    noteCuratorBase:
      "You choose how many songs to listen to. Earn from every qualified feedback. You're not required to add the song.",
    noteCuratorNonPlaylist: " Non-playlist applications open after team approval.",
    noteArtist:
      "Send your song to the right curators. Get real listening and written feedback within 72 hours. No response, your credit is refunded. No bots, no playlist guarantees.",
  },
} as const;

export default function GirisPage() {
  const router = useRouter();
  const { locale } = useLocale();
  const t = pick(T, locale);
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
      setError(mode === "login" ? t.errorLogin : t.errorRegister);
      return;
    }

    setToken(result.token);
    // Admin sifresiyle giren dogrudan admin paneline; kurator inbox'a; digeri gonder.
    const dest =
      result.user.role === "admin"
        ? "/admin"
        : result.user.role === "curator"
          ? "/curator/inbox"
          : "/gonder";
    router.push(dest);
  }

  return (
    <div className={styles.wrap}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Link href="/" className={styles.logo}>Songdeck</Link>
        <LangToggle />
      </div>

      <div className={`nb-card ${styles.card}`}>
        <div className={styles.tabs}>
          <button
            type="button"
            className={`${styles.tab} ${mode === "login" ? styles.tabOn : ""}`}
            onClick={() => setMode("login")}
          >
            {t.tabLogin}
          </button>
          <button
            type="button"
            className={`${styles.tab} ${mode === "register" ? styles.tabOn : ""}`}
            onClick={() => setMode("register")}
          >
            {t.tabRegister}
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
                  {t.roleArtist}
                </button>
                <button
                  type="button"
                  className={`${styles.roleBtn} ${role === "curator" ? styles.roleOn : ""}`}
                  onClick={() => setRole("curator")}
                >
                  {t.roleCurator}
                </button>
              </div>
              <input
                className="nb-input"
                placeholder={role === "curator" ? t.namePlaceholderCurator : t.namePlaceholderArtist}
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
                    aria-label={t.curatorTypeAria}
                  >
                    {CURATOR_TYPE_VALUES.map((v) => (
                      <option key={v} value={v}>
                        {t.curatorTypes[v]}
                      </option>
                    ))}
                  </select>
                  {(curatorType === "playlist" || curatorType === "dj") && (
                    <input
                      className="nb-input"
                      placeholder={t.playlistUrlPlaceholder}
                      value={playlistUrl}
                      onChange={(e) => setPlaylistUrl(e.target.value)}
                    />
                  )}
                </>
              )}
              <input
                className="nb-input"
                placeholder={t.referralPlaceholder}
                value={referralCode}
                onChange={(e) => setReferralCode(e.target.value)}
              />
              <p className={styles.referralNote}>{t.referralNote}</p>
            </>
          )}

          <input
            className="nb-input"
            type="email"
            placeholder={t.emailPlaceholder}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            className="nb-input"
            type="password"
            placeholder={t.passwordPlaceholder}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />

          {error && <div className={styles.error}>{error}</div>}

          <button type="submit" className="nb-btn" disabled={busy}>
            {busy ? t.busy : mode === "login" ? t.submitLogin : t.submitRegister}
          </button>
        </form>

        {mode === "register" && role === "curator" && (
          <p className={styles.note}>
            {t.noteCuratorBase}
            {curatorType !== "playlist" && t.noteCuratorNonPlaylist}
          </p>
        )}
        {mode === "register" && role === "artist" && (
          <p className={styles.note}>{t.noteArtist}</p>
        )}
      </div>
    </div>
  );
}
