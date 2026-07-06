"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getMe,
  getPackages,
  getToken,
  listCurators,
  requestPackage,
  startAutopilot,
  submitToCurator,
  type Curator,
  type CuratorTier,
  type CuratorType,
  type CreditPackage,
  type User,
} from "@/lib/api";
import styles from "./page.module.css";

const TYPE_LABELS: Record<CuratorType, string> = {
  playlist: "🎧 Playlist",
  radyo: "📻 Radyo",
  medya: "📰 Medya",
  label: "💿 Label",
  menajer: "🧑‍💼 Menajer",
  booker: "🎪 Booker",
  dj: "🎛️ DJ",
  mentor: "🎓 Mentor",
  sync: "🎬 Sync",
};

/** Kademe rozeti — reach bazli fiyatlandirmayi gorsellestirir. */
const TIER_COLORS: Record<CuratorTier, string> = {
  bronze: "#cd7f32",
  silver: "#c0c0c0",
  gold: "#d4a017",
  platinum: "#7de2d1",
};

const TIER_LABELS: Record<CuratorTier, string> = {
  bronze: "Bronz",
  silver: "Gümüş",
  gold: "Altın",
  platinum: "Platin",
};

type SubmitOpts = { guaranteed: boolean; priority: boolean };

const DEFAULT_OPTS: SubmitOpts = { guaranteed: false, priority: false };

/** guaranteed → +%50 (min 1 kredi), priority → +1 kredi — backend'le ayni formul. */
function computeCost(baseCost: number, opts: SubmitOpts): number {
  let total = baseCost;
  if (opts.guaranteed) total += Math.max(1, Math.ceil(baseCost * 0.5));
  if (opts.priority) total += 1;
  return total;
}

/** "yanıt %92 · kabul %38 · fırsat %41" — veri yoksa parça atlanır. */
function statsLine(c: Curator): string {
  const s = c.stats;
  if (!s) return "";
  const parts: string[] = [];
  if (s.response_rate !== null) parts.push(`yanıt %${s.response_rate}`);
  if (s.success_rate !== null) parts.push(`kabul %${s.success_rate}`);
  if (s.opportunity_rate !== null) parts.push(`fırsat %${s.opportunity_rate}`);
  return parts.join(" · ");
}

/** "Sanatçı - Şarkı" ayrıştırıcısı — hem tekli gönderim hem otopilot kullanır. */
function parseSongText(raw: string): { artist: string; title: string } | null {
  const trimmed = raw.trim();
  if (!trimmed.includes(" - ")) return null;
  const [artist, ...rest] = trimmed.split(" - ");
  const title = rest.join(" - ").trim();
  if (!artist.trim() || !title) return null;
  return { artist: artist.trim(), title };
}

/** Sanatci gonderim ekrani — cekirdek dongunun panel ayagi:
 *  kredi bakiyesi + onayli kurator katalogu + gercek gonderim (garanti/oncelik eklentili). */
export default function GonderPage() {
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [curators, setCurators] = useState<Curator[]>([]);
  const [song, setSong] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [sentIds, setSentIds] = useState<Record<number, boolean>>({});
  const [error, setError] = useState("");
  const [optsMap, setOptsMap] = useState<Record<number, SubmitOpts>>({});
  const [highlightId, setHighlightId] = useState<number | null>(null);

  // Kredi paketi modali (dusuk kredi uyarisindan veya elle acilir)
  const [showPackageModal, setShowPackageModal] = useState(false);
  const [packages, setPackages] = useState<CreditPackage[] | null>(null);
  const [packageMsg, setPackageMsg] = useState("");
  const [requestingKey, setRequestingKey] = useState<string | null>(null);

  // Otopilot: sarki + butce -> uygun kuratorlere otomatik gonderim
  const [autopilotSong, setAutopilotSong] = useState("");
  const [autopilotBudget, setAutopilotBudget] = useState(2);
  const [autopilotBusy, setAutopilotBusy] = useState(false);
  const [autopilotError, setAutopilotError] = useState("");
  const [autopilotResult, setAutopilotResult] = useState<{ created: number; spent: number } | null>(
    null
  );

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

    // ?curator=ID -> playlistler sayfasindan gelen koprude ilgili karti vurgula
    if (typeof window !== "undefined") {
      const raw = new URLSearchParams(window.location.search).get("curator");
      const id = raw ? Number(raw) : NaN;
      if (!Number.isNaN(id)) setHighlightId(id);
    }
  }, []);

  useEffect(() => {
    if (highlightId === null || curators.length === 0) return;
    document
      .getElementById(`curator-${highlightId}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightId, curators]);

  function parseSong(): { artist: string; title: string } | null {
    return parseSongText(song);
  }

  function toggleOpt(curatorId: number, key: keyof SubmitOpts) {
    setOptsMap((prev) => {
      const current = prev[curatorId] ?? DEFAULT_OPTS;
      return { ...prev, [curatorId]: { ...current, [key]: !current[key] } };
    });
  }

  async function openPackageModal() {
    setPackageMsg("");
    setShowPackageModal(true);
    if (!packages) {
      const data = await getPackages();
      if (data) setPackages(data.packages);
    }
  }

  async function handleRequestPackage(key: string) {
    setRequestingKey(key);
    setPackageMsg("");
    const res = await requestPackage(key);
    setRequestingKey(null);
    if (!res) {
      setPackageMsg("Talep gönderilemedi — tekrar dene.");
      return;
    }
    setPackageMsg(
      "Talebin alındı — ödeme bilgisi e-postana gelecek, admin onayıyla kredin yüklenecek (pilot dönem)."
    );
  }

  async function handleSubmit(curator: Curator) {
    setError("");
    const parsed = parseSong();
    if (!parsed) {
      setError('Şarkıyı "Sanatçı - Şarkı" formatında yaz (ör. Seyhan Canyakan - Serenity).');
      return;
    }
    const opts = optsMap[curator.id] ?? DEFAULT_OPTS;
    const cost = computeCost(curator.base_cost ?? 1, opts);
    if (!user || user.credits < cost) {
      setError("Kredin yetersiz — paket al.");
      openPackageModal();
      return;
    }
    setBusyId(curator.id);
    const sub = await submitToCurator(parsed.artist, parsed.title, curator.id, opts);
    setBusyId(null);
    if (!sub) {
      setError("Gönderim başarısız — şarkı Deezer'da bulunamadı ya da kredi yetersiz.");
      return;
    }
    setSentIds((prev) => ({ ...prev, [curator.id]: true }));
    const spent = sub.cost_credits ?? cost;
    setUser((prev) => (prev ? { ...prev, credits: prev.credits - spent } : prev));
  }

  async function handleAutopilotStart() {
    setAutopilotError("");
    setAutopilotResult(null);
    const parsed = parseSongText(autopilotSong);
    if (!parsed) {
      setAutopilotError('Şarkıyı "Sanatçı - Şarkı" formatında yaz (ör. Seyhan Canyakan - Serenity).');
      return;
    }
    if (autopilotBudget < 2) {
      setAutopilotError("Bütçe en az 2 kredi olmalı.");
      return;
    }
    if (!user || user.credits < autopilotBudget) {
      setAutopilotError("Kredin yetersiz — paket al.");
      openPackageModal();
      return;
    }
    setAutopilotBusy(true);
    const res = await startAutopilot(parsed.artist, parsed.title, autopilotBudget);
    setAutopilotBusy(false);
    if (!res) {
      setAutopilotError("Otopilot başarısız — tekrar dene.");
      return;
    }
    setAutopilotResult({ created: res.created.length, spent: res.spent });
    setUser((prev) => (prev ? { ...prev, credits: prev.credits - res.spent } : prev));
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
        {curators.map((c) => {
          const opts = optsMap[c.id] ?? DEFAULT_OPTS;
          const baseCost = c.base_cost ?? 1;
          const cost = computeCost(baseCost, opts);
          const sent = !!sentIds[c.id];
          const insufficient = !sent && (!user || user.credits < cost);
          const isHighlighted = highlightId === c.id;

          return (
            <div
              key={c.id}
              id={`curator-${c.id}`}
              className={`nb-card ${styles.curatorCard} ${
                isHighlighted ? styles.curatorCardHighlighted : ""
              }`}
            >
              <div>
                <div className={styles.curatorName}>
                  {c.playlist_title}{" "}
                  <span
                    style={{
                      fontSize: 11, fontWeight: 900, background: "#f4ecff",
                      border: "2px solid #000", padding: "1px 6px",
                      verticalAlign: "middle", whiteSpace: "nowrap",
                    }}
                  >
                    {TYPE_LABELS[c.curator_type ?? "playlist"]}
                  </span>{" "}
                  {c.tier && (
                    <span
                      style={{
                        fontSize: 11, fontWeight: 900, color: "#fff",
                        background: TIER_COLORS[c.tier], border: "2px solid #000",
                        padding: "1px 6px", verticalAlign: "middle",
                        whiteSpace: "nowrap", textTransform: "uppercase",
                      }}
                    >
                      {TIER_LABELS[c.tier]}
                    </span>
                  )}{" "}
                  {c.sponsored && (
                    <span
                      style={{
                        fontSize: 11, fontWeight: 900, color: "#fff",
                        background: "var(--purple)", border: "2px solid #000",
                        padding: "1px 6px", verticalAlign: "middle",
                        whiteSpace: "nowrap",
                      }}
                    >
                      Sponsorlu
                    </span>
                  )}
                </div>
                <div className={styles.curatorMeta}>
                  {c.name} · {c.fans.toLocaleString("tr-TR")} fan ·{" "}
                  {c.track_count} parça · kalite {c.quality_score}
                  {statsLine(c) && <> · {statsLine(c)}</>}
                </div>

                {!sent && (
                  <div className={styles.optsRow}>
                    <label className={styles.optLabel}>
                      <input
                        type="checkbox"
                        checked={opts.guaranteed}
                        onChange={() => toggleOpt(c.id, "guaranteed")}
                      />
                      Garanti (+%50 kredi): 72 saatte yanıt gelmezse 2x kredi iadesi
                    </label>
                    <label className={styles.optLabel}>
                      <input
                        type="checkbox"
                        checked={opts.priority}
                        onChange={() => toggleOpt(c.id, "priority")}
                      />
                      Öne çıkan (+1 kredi): 48 saat SLA + kurator kutusunda üst sıra
                    </label>
                  </div>
                )}
              </div>

              {sent ? (
                <button type="button" className={`nb-btn ${styles.sendBtn}`} disabled>
                  ✓ Gönderildi
                </button>
              ) : insufficient ? (
                <button
                  type="button"
                  className={`nb-btn ${styles.sendBtn}`}
                  onClick={openPackageModal}
                >
                  Kredin yetersiz — paket al
                </button>
              ) : (
                <button
                  type="button"
                  className={`nb-btn ${styles.sendBtn}`}
                  disabled={busyId === c.id}
                  onClick={() => handleSubmit(c)}
                >
                  {busyId === c.id ? "..." : `Gönder (${cost} kredi)`}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <div className={`nb-card ${styles.autopilotSection}`}>
        <h2 className="nb-h">Otopilot</h2>
        <p className={styles.promise}>
          Bir şarkı ve bütçe belirle — sistem uygun küratörlere otomatik
          gönderim yapsın.
        </p>
        <div className={styles.autopilotRow}>
          <div className={styles.autopilotField}>
            <label className={styles.fieldLabel} htmlFor="autopilot-song">
              Şarkı
            </label>
            <input
              id="autopilot-song"
              className="nb-input"
              placeholder='"Sanatçı - Şarkı" (ör. Seyhan Canyakan - Serenity)'
              value={autopilotSong}
              onChange={(e) => setAutopilotSong(e.target.value)}
            />
          </div>
          <div className={`${styles.autopilotField} ${styles.autopilotBudgetField}`}>
            <label className={styles.fieldLabel} htmlFor="autopilot-budget">
              Bütçe (kredi)
            </label>
            <input
              id="autopilot-budget"
              className="nb-input"
              type="number"
              min={2}
              value={autopilotBudget}
              onChange={(e) => {
                const v = Number(e.target.value);
                setAutopilotBudget(Number.isNaN(v) ? 2 : v);
              }}
            />
          </div>
          <button
            type="button"
            className="nb-btn"
            disabled={autopilotBusy}
            onClick={handleAutopilotStart}
          >
            {autopilotBusy ? "..." : "Başlat"}
          </button>
        </div>
        {autopilotError && <div className={styles.error}>{autopilotError}</div>}
        {autopilotResult && (
          <div className={styles.autopilotResult}>
            ✓ {autopilotResult.created} gönderim oluştu · {autopilotResult.spent} kredi
            harcandı.
          </div>
        )}
      </div>

      {showPackageModal && (
        <div className={styles.modalOverlay} onClick={() => setShowPackageModal(false)}>
          <div
            className={`nb-card ${styles.modalBox}`}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className={styles.modalClose}
              aria-label="Kapat"
              onClick={() => setShowPackageModal(false)}
            >
              ✕
            </button>
            <h2 className="nb-h">Kredi Paketleri</h2>
            {!packages && <div className={styles.empty}>Yükleniyor...</div>}
            {packages && (
              <div className={styles.packageGrid}>
                {packages.map((p) => (
                  <div key={p.key} className={styles.packageCard}>
                    <div className={styles.packageLabel}>{p.label}</div>
                    <div className={styles.packageCredits}>{p.credits} kredi</div>
                    <div className={styles.packagePrice}>{p.price_try} TL</div>
                    <button
                      type="button"
                      className={`nb-btn ${styles.packageBtn}`}
                      disabled={requestingKey === p.key}
                      onClick={() => handleRequestPackage(p.key)}
                    >
                      {requestingKey === p.key ? "..." : "Talep Gönder"}
                    </button>
                  </div>
                ))}
              </div>
            )}
            {packageMsg && <div className={styles.modalMsg}>{packageMsg}</div>}
          </div>
        </div>
      )}
    </div>
  );
}
