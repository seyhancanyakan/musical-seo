"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  addTrack,
  deleteTrack,
  getMe,
  getPackages,
  getToken,
  listCurators,
  myTracks,
  requestPackage,
  startAutopilot,
  submitToCuratorD,
  type ArtistTrack,
  type Curator,
  type CuratorTier,
  type CuratorType,
  type CreditPackage,
  type User,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type SubmitOpts = { guaranteed: boolean; priority: boolean };

const DEFAULT_OPTS: SubmitOpts = { guaranteed: false, priority: false };

const T = {
  tr: {
    typeLabels: {
      playlist: "🎧 Playlist",
      radyo: "📻 Radyo",
      medya: "📰 Medya",
      label: "💿 Label",
      menajer: "🧑‍💼 Menajer",
      booker: "🎪 Booker",
      dj: "🎛️ DJ",
      mentor: "🎓 Mentor",
      sync: "🎬 Sync",
    } as Record<CuratorType, string>,
    tierLabels: {
      bronze: "Bronz",
      silver: "Gümüş",
      gold: "Altın",
      platinum: "Platin",
    } as Record<CuratorTier, string>,
    sponsored: "Sponsorlu",
    statsResponse: "yanıt",
    statsSuccess: "kabul",
    statsOpportunity: "fırsat",
    fanSuffix: "fan",
    trackSuffix: "parça",
    qualityLabel: "kalite",
    optGuaranteed: "Garanti (+%50 kredi): 72 saatte yanıt gelmezse 2x kredi iadesi",
    optPriority: "Öne çıkan (+1 kredi): 48 saat SLA + kurator kutusunda üst sıra",
    sentBtn: "✓ Gönderildi",
    insufficientBtn: "Kredin yetersiz — paket al",
    sendBtn: (cost: number) => `Gönder (${cost} kredi)`,
    busy: "...",
    songFormatError:
      'Şarkıyı "Sanatçı - Şarkı" formatında yaz (ör. Seyhan Canyakan - Serenity).',
    insufficientError: "Kredin yetersiz — paket al.",
    submitFailedError:
      "Gönderim başarısız — şarkı Deezer'da bulunamadı ya da kredi yetersiz.",
    autopilotBudgetError: "Bütçe en az 2 kredi olmalı.",
    autopilotFailedError: "Otopilot başarısız — tekrar dene.",
    gateTitle: "Giriş gerekli",
    gateText: "Şarkı göndermek için sanatçı hesabınla giriş yap.",
    gateLink: "Giriş / Kayıt",
    walletLine: (credits: number, name: string) => `💳 ${credits} kredi · ${name}`,
    heading: "Şarkını Küratörlere Gönder",
    promise:
      "72 saatte gerçek dinleme ve yazılı geri bildirim. Cevap yoksa kredin geri. Playlist garantisi satmıyoruz — Spotify kuralları gereği zaten kimse satamaz.",
    songInputPlaceholder: 'Şarkın: "Sanatçı - Şarkı" (ör. Seyhan Canyakan - Serenity)',
    emptyCurators: "Henüz onaylı küratör yok — başvurular değerlendiriliyor.",
    tracksHeading: "Şarkılarım",
    trackEmptyHint:
      "Önce şarkını kaydet — gönderimler kayıtlı şarkınla yapılır.",
    saveTrackBtn: "Kaydet",
    deleteTrackAria: "Şarkıyı sil",
    selectSongFirstHint: "Önce şarkı seç.",
    noSongSelected: "Şarkı seçilmedi",
    autopilotHeading: "Otopilot",
    autopilotPromise:
      "Bir şarkı ve bütçe belirle — sistem uygun küratörlere otomatik gönderim yapsın.",
    songFieldLabel: "Şarkı",
    budgetFieldLabel: "Bütçe (kredi)",
    startBtn: "Başlat",
    autopilotResult: (created: number, spent: number) =>
      `✓ ${created} gönderim oluştu · ${spent} kredi harcandı.`,
    modalClose: "Kapat",
    modalHeading: "Kredi Paketleri",
    loading: "Yükleniyor...",
    packageCreditsSuffix: "kredi",
    packageBtn: "Talep Gönder",
    requestFailedMsg: "Talep gönderilemedi — tekrar dene.",
    requestSuccessMsg:
      "Talebin alındı — ödeme bilgisi e-postana gelecek, admin onayıyla kredin yüklenecek (pilot dönem).",
  },
  en: {
    typeLabels: {
      playlist: "🎧 Playlist",
      radyo: "📻 Radio",
      medya: "📰 Media",
      label: "💿 Label",
      menajer: "🧑‍💼 Manager",
      booker: "🎪 Booker",
      dj: "🎛️ DJ",
      mentor: "🎓 Mentor",
      sync: "🎬 Sync",
    } as Record<CuratorType, string>,
    tierLabels: {
      bronze: "Bronze",
      silver: "Silver",
      gold: "Gold",
      platinum: "Platinum",
    } as Record<CuratorTier, string>,
    sponsored: "Sponsored",
    statsResponse: "response",
    statsSuccess: "acceptance",
    statsOpportunity: "opportunity",
    fanSuffix: "fans",
    trackSuffix: "tracks",
    qualityLabel: "quality",
    optGuaranteed: "Guaranteed (+50% credits): 2x credit refund if no response within 72 hours",
    optPriority: "Featured (+1 credit): 48-hour SLA + top position in curator's inbox",
    sentBtn: "✓ Sent",
    insufficientBtn: "Not enough credits — buy a package",
    sendBtn: (cost: number) => `Send (${cost} credits)`,
    busy: "...",
    songFormatError:
      'Write your song as "Artist - Title" (e.g. Seyhan Canyakan - Serenity).',
    insufficientError: "Not enough credits — buy a package.",
    submitFailedError:
      "Submission failed — the song wasn't found on Deezer, or you don't have enough credits.",
    autopilotBudgetError: "Budget must be at least 2 credits.",
    autopilotFailedError: "Autopilot failed — try again.",
    gateTitle: "Login required",
    gateText: "Log in with your artist account to send a song.",
    gateLink: "Login / Sign Up",
    walletLine: (credits: number, name: string) => `💳 ${credits} credits · ${name}`,
    heading: "Send Your Song to Curators",
    promise:
      "Real listening and written feedback within 72 hours. No response, your credit is refunded. We don't sell playlist guarantees — nobody can, per Spotify's rules.",
    songInputPlaceholder: 'Your song: "Artist - Title" (e.g. Seyhan Canyakan - Serenity)',
    emptyCurators: "No approved curators yet — applications are under review.",
    tracksHeading: "My Tracks",
    trackEmptyHint:
      "Save your song first — submissions are made with your saved song.",
    saveTrackBtn: "Save",
    deleteTrackAria: "Delete song",
    selectSongFirstHint: "Select a song first.",
    noSongSelected: "No song selected",
    autopilotHeading: "Autopilot",
    autopilotPromise:
      "Pick a song and a budget — the system automatically submits it to matching curators.",
    songFieldLabel: "Song",
    budgetFieldLabel: "Budget (credits)",
    startBtn: "Start",
    autopilotResult: (created: number, spent: number) =>
      `✓ ${created} submissions created · ${spent} credits spent.`,
    modalClose: "Close",
    modalHeading: "Credit Packages",
    loading: "Loading...",
    packageCreditsSuffix: "credits",
    packageBtn: "Send Request",
    requestFailedMsg: "Request failed — try again.",
    requestSuccessMsg:
      "Your request has been received — payment info will be sent to your email, credits will be added after admin approval (pilot period).",
  },
} as const;

/** guaranteed → +%50 (min 1 kredi), priority → +1 kredi — backend'le ayni formul. */
function computeCost(baseCost: number, opts: SubmitOpts): number {
  let total = baseCost;
  if (opts.guaranteed) total += Math.max(1, Math.ceil(baseCost * 0.5));
  if (opts.priority) total += 1;
  return total;
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
  const { locale } = useLocale();
  const t = pick(T, locale);
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [curators, setCurators] = useState<Curator[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [sentIds, setSentIds] = useState<Record<number, boolean>>({});
  const [error, setError] = useState("");
  const [optsMap, setOptsMap] = useState<Record<number, SubmitOpts>>({});
  const [highlightId, setHighlightId] = useState<number | null>(null);

  // Sarkilarim: sanatcinin kayitli sarki kutuphanesi — gonderimler bu secimle yapilir
  const [tracks, setTracks] = useState<ArtistTrack[]>([]);
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null);
  const [newTrackText, setNewTrackText] = useState("");
  const [addTrackBusy, setAddTrackBusy] = useState(false);
  const [addTrackError, setAddTrackError] = useState("");
  const [deletingTrackId, setDeletingTrackId] = useState<number | null>(null);

  // Kredi paketi modali (dusuk kredi uyarisindan veya elle acilir)
  const [showPackageModal, setShowPackageModal] = useState(false);
  const [packages, setPackages] = useState<CreditPackage[] | null>(null);
  const [packageMsg, setPackageMsg] = useState("");
  const [requestingKey, setRequestingKey] = useState<string | null>(null);

  // Otopilot: sarki + butce -> uygun kuratorlere otomatik gonderim
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
        const trackList = await myTracks();
        if (trackList) setTracks(trackList);
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

  const selectedTrack = tracks.find((track) => track.id === selectedTrackId) ?? null;

  /** Backend TR aciklamasi aynen gosterilir; EN locale'de "Error: " onekiyle. */
  function displayBackendError(msg: string): string {
    return locale === "en" ? `Error: ${msg}` : msg;
  }

  function selectTrack(id: number) {
    setError("");
    setSelectedTrackId(id);
  }

  async function handleAddTrack() {
    setAddTrackError("");
    const parsed = parseSongText(newTrackText);
    if (!parsed) {
      setAddTrackError(t.songFormatError);
      return;
    }
    setAddTrackBusy(true);
    const { data, error: err } = await addTrack(parsed.artist, parsed.title);
    setAddTrackBusy(false);
    if (!data) {
      setAddTrackError(err ? displayBackendError(err) : t.submitFailedError);
      return;
    }
    setTracks((prev) => [data, ...prev]);
    setSelectedTrackId(data.id);
    setNewTrackText("");
  }

  async function handleDeleteTrack(id: number) {
    setDeletingTrackId(id);
    const res = await deleteTrack(id);
    setDeletingTrackId(null);
    if (!res?.ok) return;
    setTracks((prev) => prev.filter((track) => track.id !== id));
    setSelectedTrackId((prev) => (prev === id ? null : prev));
  }

  function toggleOpt(curatorId: number, key: keyof SubmitOpts) {
    setOptsMap((prev) => {
      const current = prev[curatorId] ?? DEFAULT_OPTS;
      return { ...prev, [curatorId]: { ...current, [key]: !current[key] } };
    });
  }

  /** "yanıt %92 · kabul %38 · fırsat %41" — veri yoksa parça atlanır. */
  function statsLine(c: Curator): string {
    const s = c.stats;
    if (!s) return "";
    const parts: string[] = [];
    if (s.response_rate !== null) parts.push(`${t.statsResponse} %${s.response_rate}`);
    if (s.success_rate !== null) parts.push(`${t.statsSuccess} %${s.success_rate}`);
    if (s.opportunity_rate !== null)
      parts.push(`${t.statsOpportunity} %${s.opportunity_rate}`);
    return parts.join(" · ");
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
      setPackageMsg(t.requestFailedMsg);
      return;
    }
    setPackageMsg(t.requestSuccessMsg);
  }

  async function handleSubmit(curator: Curator) {
    setError("");
    if (!selectedTrack) {
      setError(t.selectSongFirstHint);
      return;
    }
    const opts = optsMap[curator.id] ?? DEFAULT_OPTS;
    const cost = computeCost(curator.base_cost ?? 1, opts);
    if (!user || user.credits < cost) {
      setError(t.insufficientError);
      openPackageModal();
      return;
    }
    setBusyId(curator.id);
    const { data: sub, error: subErr } = await submitToCuratorD(
      selectedTrack.artist,
      selectedTrack.title,
      curator.id,
      opts
    );
    setBusyId(null);
    if (!sub) {
      setError(subErr ? displayBackendError(subErr) : t.submitFailedError);
      return;
    }
    setSentIds((prev) => ({ ...prev, [curator.id]: true }));
    const spent = sub.cost_credits ?? cost;
    setUser((prev) => (prev ? { ...prev, credits: prev.credits - spent } : prev));
  }

  async function handleAutopilotStart() {
    setAutopilotError("");
    setAutopilotResult(null);
    if (!selectedTrack) {
      setAutopilotError(t.selectSongFirstHint);
      return;
    }
    if (autopilotBudget < 2) {
      setAutopilotError(t.autopilotBudgetError);
      return;
    }
    if (!user || user.credits < autopilotBudget) {
      setAutopilotError(t.insufficientError);
      openPackageModal();
      return;
    }
    setAutopilotBusy(true);
    const res = await startAutopilot(selectedTrack.artist, selectedTrack.title, autopilotBudget);
    setAutopilotBusy(false);
    if (!res) {
      setAutopilotError(t.autopilotFailedError);
      return;
    }
    setAutopilotResult({ created: res.created.length, spent: res.spent });
    setUser((prev) => (prev ? { ...prev, credits: prev.credits - res.spent } : prev));
  }

  if (checked && !user) {
    return (
      <div className={styles.gate}>
        <div className="nb-card" style={{ padding: 28, maxWidth: 460 }}>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
            <LangToggle />
          </div>
          <h2 className="nb-h">{t.gateTitle}</h2>
          <p className={styles.gateText}>{t.gateText}</p>
          <Link href="/giris" className="nb-btn">{t.gateLink}</Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" className={styles.logo}>Songdeck</Link>
          <LangToggle />
        </div>
        {user && (
          <div className={styles.wallet}>{t.walletLine(user.credits, user.name)}</div>
        )}
      </div>

      <h1 className="nb-h">{t.heading}</h1>
      <p className={styles.promise}>{t.promise}</p>

      <div className={`nb-card ${styles.trackSection}`}>
        <h2 className="nb-h" style={{ fontSize: 20 }}>{t.tracksHeading}</h2>

        {tracks.length === 0 && (
          <div className={styles.trackEmptyHint}>{t.trackEmptyHint}</div>
        )}

        {tracks.length > 0 && (
          <div className={styles.trackList}>
            {tracks.map((track) => (
              <div
                key={track.id}
                className={`${styles.trackChip} ${
                  selectedTrackId === track.id ? styles.trackChipSelected : ""
                }`}
                onClick={() => selectTrack(track.id)}
              >
                <span>{track.artist} - {track.title}</span>
                <button
                  type="button"
                  className={styles.trackChipDelete}
                  aria-label={t.deleteTrackAria}
                  disabled={deletingTrackId === track.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteTrack(track.id);
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        <div className={styles.trackAddRow}>
          <input
            className="nb-input"
            placeholder={t.songInputPlaceholder}
            value={newTrackText}
            onChange={(e) => setNewTrackText(e.target.value)}
          />
          <button
            type="button"
            className="nb-btn"
            disabled={addTrackBusy}
            onClick={handleAddTrack}
          >
            {addTrackBusy ? t.busy : t.saveTrackBtn}
          </button>
        </div>
        {addTrackError && <div className={styles.error}>{addTrackError}</div>}
      </div>

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.list}>
        {curators.length === 0 && (
          <div className={styles.empty}>{t.emptyCurators}</div>
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
                    {t.typeLabels[c.curator_type ?? "playlist"]}
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
                      {t.tierLabels[c.tier]}
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
                      {t.sponsored}
                    </span>
                  )}
                </div>
                <div className={styles.curatorMeta}>
                  {c.name} · {c.fans.toLocaleString(locale === "tr" ? "tr-TR" : "en-US")}{" "}
                  {t.fanSuffix} · {c.track_count} {t.trackSuffix} · {t.qualityLabel}{" "}
                  {c.quality_score}
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
                      {t.optGuaranteed}
                    </label>
                    <label className={styles.optLabel}>
                      <input
                        type="checkbox"
                        checked={opts.priority}
                        onChange={() => toggleOpt(c.id, "priority")}
                      />
                      {t.optPriority}
                    </label>
                  </div>
                )}
              </div>

              {sent ? (
                <button type="button" className={`nb-btn ${styles.sendBtn}`} disabled>
                  {t.sentBtn}
                </button>
              ) : !selectedTrack ? (
                <div className={styles.sendBtnWrap}>
                  <button type="button" className={`nb-btn ${styles.sendBtn}`} disabled>
                    {t.sendBtn(cost)}
                  </button>
                  <span className={styles.hint}>{t.selectSongFirstHint}</span>
                </div>
              ) : insufficient ? (
                <button
                  type="button"
                  className={`nb-btn ${styles.sendBtn}`}
                  onClick={openPackageModal}
                >
                  {t.insufficientBtn}
                </button>
              ) : (
                <button
                  type="button"
                  className={`nb-btn ${styles.sendBtn}`}
                  disabled={busyId === c.id}
                  onClick={() => handleSubmit(c)}
                >
                  {busyId === c.id ? t.busy : t.sendBtn(cost)}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <div className={`nb-card ${styles.autopilotSection}`}>
        <h2 className="nb-h">{t.autopilotHeading}</h2>
        <p className={styles.promise}>{t.autopilotPromise}</p>
        <div className={styles.autopilotRow}>
          <div className={styles.autopilotField}>
            <label className={styles.fieldLabel} htmlFor="autopilot-song">
              {t.songFieldLabel}
            </label>
            <div id="autopilot-song" className={styles.autopilotSelectedSong}>
              {selectedTrack
                ? `${selectedTrack.artist} - ${selectedTrack.title}`
                : t.noSongSelected}
            </div>
          </div>
          <div className={`${styles.autopilotField} ${styles.autopilotBudgetField}`}>
            <label className={styles.fieldLabel} htmlFor="autopilot-budget">
              {t.budgetFieldLabel}
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
            disabled={autopilotBusy || !selectedTrack}
            onClick={handleAutopilotStart}
          >
            {autopilotBusy ? t.busy : t.startBtn}
          </button>
        </div>
        {!selectedTrack && <div className={styles.hint}>{t.selectSongFirstHint}</div>}
        {autopilotError && <div className={styles.error}>{autopilotError}</div>}
        {autopilotResult && (
          <div className={styles.autopilotResult}>
            {t.autopilotResult(autopilotResult.created, autopilotResult.spent)}
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
              aria-label={t.modalClose}
              onClick={() => setShowPackageModal(false)}
            >
              ✕
            </button>
            <h2 className="nb-h">{t.modalHeading}</h2>
            {!packages && <div className={styles.empty}>{t.loading}</div>}
            {packages && (
              <div className={styles.packageGrid}>
                {packages.map((p) => (
                  <div key={p.key} className={styles.packageCard}>
                    <div className={styles.packageLabel}>{p.label}</div>
                    <div className={styles.packageCredits}>
                      {p.credits} {t.packageCreditsSuffix}
                    </div>
                    <div className={styles.packagePrice}>{p.price_try} TL</div>
                    <button
                      type="button"
                      className={`nb-btn ${styles.packageBtn}`}
                      disabled={requestingKey === p.key}
                      onClick={() => handleRequestPackage(p.key)}
                    >
                      {requestingKey === p.key ? t.busy : t.packageBtn}
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

/** Kademe rozeti — reach bazli fiyatlandirmayi gorsellestirir. */
const TIER_COLORS: Record<CuratorTier, string> = {
  bronze: "#cd7f32",
  silver: "#c0c0c0",
  gold: "#d4a017",
  platinum: "#7de2d1",
};
