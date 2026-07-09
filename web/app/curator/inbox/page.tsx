"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  getMe,
  getToken,
  linkCuratorPlaylist,
  listPayouts,
  myCurator,
  myInbox,
  myRespond,
  openSubmission,
  requestPayout,
  verifyOwnershipCheck,
  verifyOwnershipStart,
  type Curator,
  type Earnings,
  type OpportunityLevel,
  type Payout,
  type Submission,
  type User,
} from "@/lib/api";
import { LangToggle, pick, useLocale } from "@/lib/locale";
import styles from "./page.module.css";

const T = {
  tr: {
    opportunityLabels: {
      playlist_ekleme: "Playlist'e ekleyeceğim",
      radyo_calma: "Radyoda çalacağım",
      haber_yazi: "Haber / yazı yapacağım",
      label_degerlendirme: "Label olarak değerlendireceğim",
      menajerlik_gorusme: "Menajerlik görüşmesi",
      booking_teklif: "Booking teklifi",
      dj_set: "DJ setimde çalacağım",
      mentorluk_seansi: "Mentorluk seansı",
      sync_degerlendirme: "Sync için değerlendireceğim",
      sosyal_paylasim: "Sosyal medyada paylaşacağım",
      tavsiye: "Tavsiyede bulunacağım",
      iletisimde_kal: "İletişimde kalalım",
    } as Record<string, string>,
    slaExpired: "Süre doldu",
    slaRemaining: (h: number, m: number) => `${h} sa ${String(m).padStart(2, "0")} dk`,
    statusAccepted: "Kabul edildi",
    statusRejected: "Reddedildi",
    statusExpired: "Süresi doldu",
    gateTitle: "Curator Gelen Kutusu",
    gateText: "Gelen kutunu görmek için küratör hesabınla giriş yap.",
    loginBtn: "Giriş / Kayıt",
    curatorPanel: "Curator Paneli",
    userChip: (name: string) => `👤 ${name} — Curator Paneli`,
    pageTitle: "Gelen Kutusu",
    apiFailedStrong: "API'ye ulaşılamadı",
    apiFailedRest: " — tekrar dene.",
    playlistNotLinkedStrong: "Playlist bağlı değil.",
    playlistNotLinkedRest: " Deezer veya Spotify playlist linkini ekle:",
    playlistUrlPlaceholder: "https://open.spotify.com/playlist/... veya deezer.com/playlist/...",
    linkBtn: "Bağla",
    linkFailed: "Liste bağlanamadı — linki kontrol et (Deezer veya Spotify, herkese açık).",
    verifyOwnershipStrong: "Liste sahipliğini doğrula",
    verifyOwnershipRest: " — doğrulanana kadar gönderim alamazsın.",
    verifyStep1: "1. Bu kodu playlist açıklamasına ekle:",
    verifyStep2: "2. Kaydettikten sonra doğrula:",
    verifyBtn: "Doğrula",
    getCodeBtn: "Doğrulama kodu al",
    codeGenFailed: "Kod üretilemedi — tekrar dene.",
    ownershipVerified: "✅ Sahiplik doğrulandı — listen onaylandı, kodu açıklamadan silebilirsin.",
    codeNotFound: "Kod açıklamada bulunamadı — ekledikten 1-2 dk sonra tekrar dene.",
    acceptRateLabel: "Kabul oranı",
    weekCountLabel: (n: string) => `Bu hafta ${n} gönderim`,
    earningsLabel: (total: string, pending: string) => `Kazanç ${total} (bekleyen ${pending})`,
    percentFmt: (n: number) => `%${n}`,
    payoutTitle: "Ödeme",
    payoutPendingLabel: "Bekleyen kazanç",
    payoutStandardBtn: "Standart Ödeme İste",
    payoutInstantBtn: (pct: number) => `Anında Ödeme (%${pct} kesinti)`,
    payoutHint: (min: number, balance: string) =>
      `Standart ödeme eşiği $${min} — bakiyen $${balance}. Eşiğe ulaşana kadar anında ödemeyi kullanabilirsin.`,
    payoutFailed: "Ödeme talebi oluşturulamadı — tekrar dene.",
    payoutRequested: (amount: string, fee: string | null) =>
      fee ? `Talep oluşturuldu: $${amount} (kesinti $${fee})` : `Talep oluşturuldu: $${amount}`,
    tableDate: "Tarih",
    tableAmount: "Tutar",
    tableFee: "Kesinti",
    tableStatus: "Durum",
    payoutPaid: "Ödendi",
    payoutRequestedStatus: "Talep edildi",
    loading: "Yükleniyor...",
    emptyInbox: "Henüz gönderim yok — sanatçılar şarkı gönderince burada görünür.",
    previewAria: (title: string) => `${title} — önizlemeyi oynat`,
    priorityBadge: "Öne çıkan (+$0.50 bonus)",
    acceptBtn: "Kabul Et",
    rejectBtn: "Reddet",
    feedbackLabelAccepted:
      "Geri bildirim (opsiyonel — 120+ karakter nitelikli sayılır ve $1 kazandırır)",
    feedbackLabelRejected:
      "Red nedeni (zorunlu — 120+ karakter nitelikli sayılır ve $1 kazandırır)",
    feedbackPlaceholder:
      "Örn: Miks temiz ama nakarat listenin tempo profiline göre yavaş kalıyor; ikinci verse'teki vokal katmanı güçlü...",
    opportunityLabel: "Fırsat sun (opsiyonel — sanatçıya ekstra değer)",
    opportunityAutoAccepted: "Otomatik (kabul = birincil fırsat)",
    opportunityNone: "Fırsat yok",
    opportunityPrimaryGroup: "Birincil fırsat (somut sonuç)",
    opportunitySecondaryGroup: "İkincil fırsat (dolaylı değer)",
    gateWait: (n: number) => `Şarkıyı dinle — yanıt ${n} saniye sonra açılır`,
    charCount: (n: number, qualified: boolean) =>
      qualified ? `${n} karakter — nitelikli ✓ ($1)` : `${n} karakter`,
    sendAccepted: "Kabul + Gönder",
    sendRejected: "Reddet + Gönder",
    dateLocale: "tr-TR",
  },
  en: {
    opportunityLabels: {
      playlist_ekleme: "I'll add it to a playlist",
      radyo_calma: "I'll play it on the radio",
      haber_yazi: "I'll write a news piece / article",
      label_degerlendirme: "I'll review it as a label",
      menajerlik_gorusme: "Management conversation",
      booking_teklif: "Booking offer",
      dj_set: "I'll play it in my DJ set",
      mentorluk_seansi: "Mentorship session",
      sync_degerlendirme: "I'll review it for sync",
      sosyal_paylasim: "I'll share it on social media",
      tavsiye: "I'll recommend it",
      iletisimde_kal: "Let's stay in touch",
    } as Record<string, string>,
    slaExpired: "Expired",
    slaRemaining: (h: number, m: number) => `${h}h ${String(m).padStart(2, "0")}m`,
    statusAccepted: "Accepted",
    statusRejected: "Rejected",
    statusExpired: "Expired",
    gateTitle: "Curator Inbox",
    gateText: "Log in with your curator account to see your inbox.",
    loginBtn: "Log in / Sign up",
    curatorPanel: "Curator Panel",
    userChip: (name: string) => `👤 ${name} — Curator Panel`,
    pageTitle: "Inbox",
    apiFailedStrong: "Couldn't reach the API",
    apiFailedRest: " — try again.",
    playlistNotLinkedStrong: "Playlist not linked.",
    playlistNotLinkedRest: " Add your Deezer or Spotify playlist link:",
    playlistUrlPlaceholder: "https://open.spotify.com/playlist/... or deezer.com/playlist/...",
    linkBtn: "Link",
    linkFailed: "Couldn't link the playlist — check the link (Deezer or Spotify, must be public).",
    verifyOwnershipStrong: "Verify playlist ownership",
    verifyOwnershipRest: " — you can't receive submissions until it's verified.",
    verifyStep1: "1. Add this code to the playlist description:",
    verifyStep2: "2. Verify after saving:",
    verifyBtn: "Verify",
    getCodeBtn: "Get verification code",
    codeGenFailed: "Couldn't generate a code — try again.",
    ownershipVerified: "✅ Ownership verified — your playlist is confirmed, you can remove the code from the description now.",
    codeNotFound: "Code not found in the description — try again 1-2 minutes after adding it.",
    acceptRateLabel: "Accept rate",
    weekCountLabel: (n: string) => `${n} submissions this week`,
    earningsLabel: (total: string, pending: string) => `Earnings ${total} (pending ${pending})`,
    percentFmt: (n: number) => `${n}%`,
    payoutTitle: "Payout",
    payoutPendingLabel: "Pending earnings",
    payoutStandardBtn: "Request Standard Payout",
    payoutInstantBtn: (pct: number) => `Instant Payout (${pct}% fee)`,
    payoutHint: (min: number, balance: string) =>
      `Standard payout threshold is $${min} — your balance is $${balance}. You can use instant payout until you reach the threshold.`,
    payoutFailed: "Couldn't create the payout request — try again.",
    payoutRequested: (amount: string, fee: string | null) =>
      fee ? `Request created: $${amount} (fee $${fee})` : `Request created: $${amount}`,
    tableDate: "Date",
    tableAmount: "Amount",
    tableFee: "Fee",
    tableStatus: "Status",
    payoutPaid: "Paid",
    payoutRequestedStatus: "Requested",
    loading: "Loading...",
    emptyInbox: "No submissions yet — they'll show up here once artists submit songs.",
    previewAria: (title: string) => `${title} — play preview`,
    priorityBadge: "Priority (+$0.50 bonus)",
    acceptBtn: "Accept",
    rejectBtn: "Reject",
    feedbackLabelAccepted:
      "Feedback (optional — 120+ characters counts as qualified and earns $1)",
    feedbackLabelRejected:
      "Rejection reason (required — 120+ characters counts as qualified and earns $1)",
    feedbackPlaceholder:
      "E.g.: The mix is clean but the chorus feels slow for the playlist's tempo profile; the vocal layer in the second verse is strong...",
    opportunityLabel: "Offer an opportunity (optional — extra value for the artist)",
    opportunityAutoAccepted: "Automatic (accept = primary opportunity)",
    opportunityNone: "No opportunity",
    opportunityPrimaryGroup: "Primary opportunity (concrete outcome)",
    opportunitySecondaryGroup: "Secondary opportunity (indirect value)",
    gateWait: (n: number) => `Listen to the track — the response opens in ${n}s`,
    charCount: (n: number, qualified: boolean) =>
      qualified ? `${n} characters — qualified ✓ ($1)` : `${n} characters`,
    sendAccepted: "Accept + Send",
    sendRejected: "Reject + Send",
    dateLocale: "en-US",
  },
} as const;

type TDict = {
  opportunityLabels: Record<string, string>;
  slaExpired: string;
  slaRemaining: (h: number, m: number) => string;
  statusAccepted: string;
  statusRejected: string;
  statusExpired: string;
  gateTitle: string;
  gateText: string;
  loginBtn: string;
  curatorPanel: string;
  userChip: (name: string) => string;
  pageTitle: string;
  apiFailedStrong: string;
  apiFailedRest: string;
  playlistNotLinkedStrong: string;
  playlistNotLinkedRest: string;
  playlistUrlPlaceholder: string;
  linkBtn: string;
  linkFailed: string;
  verifyOwnershipStrong: string;
  verifyOwnershipRest: string;
  verifyStep1: string;
  verifyStep2: string;
  verifyBtn: string;
  getCodeBtn: string;
  codeGenFailed: string;
  ownershipVerified: string;
  codeNotFound: string;
  acceptRateLabel: string;
  weekCountLabel: (n: string) => string;
  earningsLabel: (total: string, pending: string) => string;
  percentFmt: (n: number) => string;
  payoutTitle: string;
  payoutPendingLabel: string;
  payoutStandardBtn: string;
  payoutInstantBtn: (pct: number) => string;
  payoutHint: (min: number, balance: string) => string;
  payoutFailed: string;
  payoutRequested: (amount: string, fee: string | null) => string;
  tableDate: string;
  tableAmount: string;
  tableFee: string;
  tableStatus: string;
  payoutPaid: string;
  payoutRequestedStatus: string;
  loading: string;
  emptyInbox: string;
  previewAria: (title: string) => string;
  priorityBadge: string;
  acceptBtn: string;
  rejectBtn: string;
  feedbackLabelAccepted: string;
  feedbackLabelRejected: string;
  feedbackPlaceholder: string;
  opportunityLabel: string;
  opportunityAutoAccepted: string;
  opportunityNone: string;
  opportunityPrimaryGroup: string;
  opportunitySecondaryGroup: string;
  gateWait: (n: number) => string;
  charCount: (n: number, qualified: boolean) => string;
  sendAccepted: string;
  sendRejected: string;
  dateLocale: string;
};

/** Firsat secenekleri — backend PRIMARY_KINDS/SECONDARY_KINDS ile ayni (value/level backend'e gonderilir, degismez). */
const OPPORTUNITY_VALUES: { value: string; level: OpportunityLevel }[] = [
  { value: "playlist_ekleme", level: "primary" },
  { value: "radyo_calma", level: "primary" },
  { value: "haber_yazi", level: "primary" },
  { value: "label_degerlendirme", level: "primary" },
  { value: "menajerlik_gorusme", level: "primary" },
  { value: "booking_teklif", level: "primary" },
  { value: "dj_set", level: "primary" },
  { value: "mentorluk_seansi", level: "primary" },
  { value: "sync_degerlendirme", level: "primary" },
  { value: "sosyal_paylasim", level: "secondary" },
  { value: "tavsiye", level: "secondary" },
  { value: "iletisimde_kal", level: "secondary" },
];

const SLA_URGENT_HOURS = 6;
const MS_PER_HOUR = 3_600_000;
const MS_PER_DAY = 24 * MS_PER_HOUR;
const QUALIFIED_MIN_CHARS = 120; // backend esigiyle ayni: nitelikli = odenir
const PAYOUT_MIN_USD = 20; // backend pricing.PAYOUT_MIN_USD ile ayni
const INSTANT_PAYOUT_FEE_PCT = 12; // backend pricing.INSTANT_PAYOUT_FEE_RATE ile ayni

type RowStatus = Submission["status"];

type Row = {
  id: number;
  title: string;
  artist: string;
  status: RowStatus;
  feedback: string | null;
  createdAt: string | null;
  deadline: string | null;
  priority: number | undefined;
};

function submissionToRow(sub: Submission): Row {
  return {
    id: sub.id,
    title: sub.title,
    artist: sub.artist,
    status: sub.status,
    feedback: sub.feedback,
    createdAt: sub.created_at,
    deadline: sub.deadline,
    priority: sub.priority,
  };
}

/** Kurator gonderimi actiginda alinan dinleme kapisi bilgisi. */
type GateInfo = { openedAtMs: number; gateSeconds: number };

/** Kalan kapi suresi (saniye) — 0 ise yanit acik. */
function gateRemainingSeconds(gate: GateInfo | undefined, nowMs: number): number {
  if (!gate) return 0;
  const remainingMs = gate.openedAtMs + gate.gateSeconds * 1000 - nowMs;
  return remainingMs > 0 ? Math.ceil(remainingMs / 1000) : 0;
}

type SlaDisplay = { text: string; percent: number; urgent: boolean };

function formatSla(row: Row, now: number, t: TDict): SlaDisplay {
  if (!row.deadline) {
    return { text: "—", percent: 0, urgent: false };
  }

  const deadlineMs = new Date(row.deadline).getTime();
  const createdMs = row.createdAt ? new Date(row.createdAt).getTime() : deadlineMs;
  const remainingMs = deadlineMs - now;

  if (remainingMs <= 0) {
    return { text: t.slaExpired, percent: 0, urgent: true };
  }

  const totalMs = deadlineMs - createdMs;
  const totalMinutes = Math.floor(remainingMs / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  const percent = totalMs > 0 ? Math.min(100, Math.max(0, (remainingMs / totalMs) * 100)) : 0;

  return {
    text: t.slaRemaining(hours, minutes),
    percent,
    urgent: remainingMs <= SLA_URGENT_HOURS * MS_PER_HOUR,
  };
}

function statusLabel(status: RowStatus, t: TDict): string {
  if (status === "accepted") return t.statusAccepted;
  if (status === "rejected") return t.statusRejected;
  if (status === "expired") return t.statusExpired;
  return status;
}

function statusClass(status: RowStatus): string {
  if (status === "accepted") return styles.statusAccepted;
  if (status === "rejected") return styles.statusRejected;
  return styles.statusExpired;
}

export default function CuratorInboxPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const OPPORTUNITY_OPTIONS = useMemo(
    () =>
      OPPORTUNITY_VALUES.map((o) => ({
        ...o,
        label: t.opportunityLabels[o.value] ?? o.value,
      })),
    [t]
  );

  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [earnings, setEarnings] = useState<Earnings | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [apiFailed, setApiFailed] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedAction, setExpandedAction] = useState<"accepted" | "rejected">("rejected");
  const [feedbackDrafts, setFeedbackDrafts] = useState<Record<number, string>>({});
  // Gonderim basina secilen firsat ("" = otomatik: kabulde primary varsayilani)
  const [opportunityDrafts, setOpportunityDrafts] = useState<Record<number, string>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [tick, setTick] = useState(() => Date.now());

  // Dinleme kapisi: gonderim id -> acilis ani + kapi suresi
  const [gateInfo, setGateInfo] = useState<Record<number, GateInfo>>({});

  // Kurator odeme paneli
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [payoutBusy, setPayoutBusy] = useState(false);
  const [payoutMsg, setPayoutMsg] = useState("");

  // Spotify/Deezer playlist sahiplik dogrulamasi
  const [curatorRec, setCuratorRec] = useState<Curator | null>(null);
  const [verifyCode, setVerifyCode] = useState<string | null>(null);
  const [verifyMsg, setVerifyMsg] = useState("");
  const [linkDraft, setLinkDraft] = useState("");

  async function handleLinkPlaylist() {
    setVerifyMsg("");
    const curator = await linkCuratorPlaylist(linkDraft.trim());
    if (!curator) {
      setVerifyMsg(t.linkFailed);
      return;
    }
    setCuratorRec(curator);
    setUser((prev) => (prev ? { ...prev, curator_id: curator.id } : prev));
  }

  async function handleVerifyStart() {
    setVerifyMsg("");
    const result = await verifyOwnershipStart();
    if (result) setVerifyCode(result.code);
    else setVerifyMsg(t.codeGenFailed);
  }

  async function handleVerifyCheck() {
    setVerifyMsg("");
    const curator = await verifyOwnershipCheck();
    if (curator) {
      setCuratorRec(curator);
      setVerifyCode(null);
      setVerifyMsg(t.ownershipVerified);
    } else {
      setVerifyMsg(t.codeNotFound);
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!getToken()) {
        setChecked(true);
        setIsLoading(false);
        return;
      }
      const me = await getMe();
      if (cancelled) return;
      setChecked(true);
      if (!me || me.user.role !== "curator") {
        setIsLoading(false);
        return;
      }
      setUser(me.user);
      setEarnings(me.earnings ?? null);
      if (me.user.curator_id) {
        const rec = await myCurator();
        if (!cancelled && rec) setCuratorRec(rec);
      }
      const inbox = await myInbox();
      if (cancelled) return;
      if (inbox === null) {
        setApiFailed(true);
      } else {
        setRows(inbox.map(submissionToRow));
      }
      const payoutList = await listPayouts();
      if (!cancelled && payoutList) setPayouts(payoutList);
      setIsLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // SLA geri sayimlarini canli tut
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  // Dinleme kapisi geri sayimini saniye hassasiyetinde canli tut
  useEffect(() => {
    const id = setInterval(() => setTick(Date.now()), 1_000);
    return () => clearInterval(id);
  }, []);

  const stats = useMemo(() => {
    const decided = rows.filter((r) => r.status === "accepted" || r.status === "rejected");
    const accepted = rows.filter((r) => r.status === "accepted").length;
    const acceptRatePct =
      decided.length > 0 ? Math.round((accepted / decided.length) * 100) : 0;
    const weekAgo = now - 7 * MS_PER_DAY;
    const weekCount = rows.filter(
      (r) => r.createdAt && new Date(r.createdAt).getTime() >= weekAgo
    ).length;
    return { acceptRate: t.percentFmt(acceptRatePct), weekCount: String(weekCount) };
  }, [rows, now, t]);

  function updateRow(id: number, patch: Partial<Row>) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  async function handleActionClick(id: number, action: "accepted" | "rejected") {
    const willOpen = !(expandedId === id && expandedAction === action);
    setExpandedAction(action);
    setExpandedId(willOpen ? id : null);
    if (willOpen && !gateInfo[id]) {
      // Dinleme kapisi: yanit formu ilk kez acilinca sayac baslar.
      const result = await openSubmission(id);
      if (result?.opened_at) {
        setGateInfo((prev) => ({
          ...prev,
          [id]: {
            openedAtMs: new Date(result.opened_at).getTime(),
            gateSeconds: result.listen_gate_seconds,
          },
        }));
      }
    }
  }

  async function handlePayoutRequest(instant: boolean) {
    setPayoutMsg("");
    setPayoutBusy(true);
    const result = await requestPayout(instant);
    setPayoutBusy(false);
    if (!result) {
      setPayoutMsg(t.payoutFailed);
      return;
    }
    setPayouts((prev) => [result, ...prev]);
    // Talep tum tahakkuk etmis bakiyeyi kapsar; bekleyen kazanci sifirla.
    setEarnings((prev) => (prev ? { ...prev, pending_usd: 0 } : prev));
    setPayoutMsg(
      t.payoutRequested(
        result.amount_usd.toFixed(2),
        result.fee_usd > 0 ? result.fee_usd.toFixed(2) : null
      )
    );
  }

  async function handleSend(id: number) {
    const draft = (feedbackDrafts[id] ?? "").trim();
    if (expandedAction === "rejected" && !draft) return;

    const oppValue = opportunityDrafts[id] ?? "";
    const oppOption = OPPORTUNITY_OPTIONS.find((o) => o.value === oppValue);

    setBusyId(id);
    const updated = await myRespond(
      id,
      expandedAction,
      draft,
      oppOption ? { level: oppOption.level, kind: oppOption.value } : undefined
    );
    setBusyId(null);
    if (!updated) return;
    updateRow(id, { status: expandedAction, feedback: updated.feedback ?? draft });
    setExpandedId(null);
    if (draft.length >= QUALIFIED_MIN_CHARS) {
      // Kazanc tahakkuku backend'de olustu; paneli tazele
      setEarnings((prev) =>
        prev
          ? {
              ...prev,
              total_usd: prev.total_usd + 1,
              pending_usd: prev.pending_usd + 1,
              items: prev.items,
            }
          : prev
      );
    }
  }

  if (checked && !user) {
    return (
      <div className={styles.wrap} style={{ paddingTop: 80, textAlign: "center" }}>
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <LangToggle />
        </div>
        <h1 className={styles.pageTitle}>{t.gateTitle}</h1>
        <p style={{ fontWeight: 600, margin: "16px 0 24px" }}>{t.gateText}</p>
        <Link href="/giris" className="nb-btn">{t.loginBtn}</Link>
      </div>
    );
  }

  return (
    <div>
      <nav className={styles.topbar}>
        <div className={styles.topbarInner}>
          <Link href="/" className={styles.logo}>Sozy Echo</Link>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div className={styles.userChip}>
              {user ? t.userChip(user.name) : `👤 ${t.curatorPanel}`}
            </div>
            <LangToggle />
          </div>
        </div>
      </nav>

      <div className={styles.wrap}>
        <h1 className={styles.pageTitle}>{t.pageTitle}</h1>

        {apiFailed && (
          <div className={styles.apiBanner} role="status">
            <strong>{t.apiFailedStrong}</strong>
            {t.apiFailedRest}
          </div>
        )}

        {user && !user.curator_id && (
          <div className={styles.apiBanner} role="status">
            <strong>{t.playlistNotLinkedStrong}</strong>
            {t.playlistNotLinkedRest}
            <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
              <input
                className="nb-input"
                placeholder={t.playlistUrlPlaceholder}
                value={linkDraft}
                onChange={(e) => setLinkDraft(e.target.value)}
              />
              <button type="button" className="nb-btn" onClick={handleLinkPlaylist}>
                {t.linkBtn}
              </button>
            </div>
            {verifyMsg && <div style={{ marginTop: 8, fontWeight: 800 }}>{verifyMsg}</div>}
          </div>
        )}

        {curatorRec && !curatorRec.ownership_verified && (
          <div className={styles.apiBanner} role="status">
            <strong>{t.verifyOwnershipStrong}</strong>
            {t.verifyOwnershipRest}
            {verifyCode ? (
              <div style={{ marginTop: 10 }}>
                {t.verifyStep1}{" "}
                <code style={{ fontSize: 16, fontWeight: 900, background: "#fff",
                               padding: "2px 8px", border: "2px solid #000" }}>
                  {verifyCode}
                </code>
                <br />
                {t.verifyStep2}
                <button type="button" className="nb-btn" style={{ marginLeft: 10 }}
                        onClick={handleVerifyCheck}>
                  {t.verifyBtn}
                </button>
              </div>
            ) : (
              <button type="button" className="nb-btn" style={{ marginLeft: 10 }}
                      onClick={handleVerifyStart}>
                {t.getCodeBtn}
              </button>
            )}
            {verifyMsg && <div style={{ marginTop: 8, fontWeight: 800 }}>{verifyMsg}</div>}
          </div>
        )}
        {verifyMsg.startsWith("✅") && curatorRec?.ownership_verified ? (
          <div className={styles.apiBanner} role="status">{verifyMsg}</div>
        ) : null}

        <div className={styles.statsBar}>
          <div className={styles.stat}>
            {t.acceptRateLabel} <b>{stats.acceptRate}</b>
          </div>
          <div className={styles.sep} />
          <div className={styles.stat}>{t.weekCountLabel(stats.weekCount)}</div>
          {earnings && (
            <>
              <div className={styles.sep} />
              <div className={styles.stat}>
                {t.earningsLabel(
                  `$${earnings.total_usd.toFixed(0)}`,
                  `$${earnings.pending_usd.toFixed(0)}`
                )}
              </div>
            </>
          )}
        </div>

        {user && (
          <div className={styles.payoutPanel}>
            <h2 className={styles.payoutTitle}>{t.payoutTitle}</h2>
            <div className={styles.payoutPending}>
              {t.payoutPendingLabel} <b>${(earnings?.pending_usd ?? 0).toFixed(2)}</b>
            </div>
            <div className={styles.payoutButtons}>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnAccept}`}
                onClick={() => handlePayoutRequest(false)}
                disabled={payoutBusy || (earnings?.pending_usd ?? 0) < PAYOUT_MIN_USD}
              >
                {t.payoutStandardBtn}
              </button>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnSend}`}
                onClick={() => handlePayoutRequest(true)}
                disabled={payoutBusy || (earnings?.pending_usd ?? 0) <= 0}
              >
                {t.payoutInstantBtn(INSTANT_PAYOUT_FEE_PCT)}
              </button>
            </div>
            {(earnings?.pending_usd ?? 0) < PAYOUT_MIN_USD && (
              <div className={styles.payoutHint}>
                {t.payoutHint(PAYOUT_MIN_USD, (earnings?.pending_usd ?? 0).toFixed(2))}
              </div>
            )}
            {payoutMsg && <div className={styles.payoutMsg}>{payoutMsg}</div>}

            {payouts.length > 0 && (
              <table className={styles.payoutTable}>
                <thead>
                  <tr>
                    <th>{t.tableDate}</th>
                    <th>{t.tableAmount}</th>
                    <th>{t.tableFee}</th>
                    <th>{t.tableStatus}</th>
                  </tr>
                </thead>
                <tbody>
                  {payouts.map((p) => (
                    <tr key={p.id}>
                      <td>{new Date(p.created_at).toLocaleDateString(t.dateLocale)}</td>
                      <td>${p.amount_usd.toFixed(2)}</td>
                      <td>{p.fee_usd > 0 ? `$${p.fee_usd.toFixed(2)}` : "—"}</td>
                      <td>{p.status === "paid" ? t.payoutPaid : t.payoutRequestedStatus}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {isLoading && <div className={styles.loading}>{t.loading}</div>}

        {!isLoading && rows.length === 0 && !apiFailed && (
          <div className={styles.loading}>{t.emptyInbox}</div>
        )}

        {!isLoading &&
          rows.map((row) => {
            const sla = formatSla(row, now, t);
            const isExpanded = expandedId === row.id;
            const isBusy = busyId === row.id;
            const draft = feedbackDrafts[row.id] ?? "";
            const isPending = row.status === "pending";
            const qualified = draft.trim().length >= QUALIFIED_MIN_CHARS;
            const gateRemaining = gateRemainingSeconds(gateInfo[row.id], tick);
            const gateActive = isExpanded && gateRemaining > 0;

            return (
              <div key={row.id}>
                <div className={styles.rowCard}>
                  <button
                    type="button"
                    className={styles.playBtn}
                    aria-label={t.previewAria(row.title)}
                  >
                    <span className={styles.playTri} />
                  </button>

                  <div className={styles.trackInfo}>
                    <div className={styles.name}>
                      {row.title}
                      {row.priority === 1 && (
                        <span className={styles.priorityBadge}>{t.priorityBadge}</span>
                      )}
                    </div>
                    <div className={styles.artist}>{row.artist}</div>
                  </div>

                  {isPending ? (
                    <>
                      <div
                        className={
                          sla.urgent ? `${styles.sla} ${styles.slaUrgent}` : styles.sla
                        }
                      >
                        <div className={styles.time}>{sla.text}</div>
                        <div className={styles.slaTrack}>
                          <div
                            className={styles.slaFill}
                            style={{ width: `${sla.percent}%` }}
                          />
                        </div>
                      </div>

                      <div className={styles.actions}>
                        <button
                          type="button"
                          className={`${styles.btn} ${styles.btnAccept}`}
                          onClick={() => handleActionClick(row.id, "accepted")}
                          disabled={isBusy}
                        >
                          {t.acceptBtn}
                        </button>
                        <button
                          type="button"
                          className={`${styles.btn} ${styles.btnReject}`}
                          onClick={() => handleActionClick(row.id, "rejected")}
                          disabled={isBusy}
                        >
                          {t.rejectBtn}
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className={`${styles.statusResult} ${statusClass(row.status)}`}>
                      {statusLabel(row.status, t)}
                    </div>
                  )}
                </div>

                {isExpanded && isPending && (
                  <div className={styles.expanded}>
                    <label htmlFor={`reason-${row.id}`}>
                      {expandedAction === "accepted"
                        ? t.feedbackLabelAccepted
                        : t.feedbackLabelRejected}
                    </label>
                    <textarea
                      id={`reason-${row.id}`}
                      placeholder={t.feedbackPlaceholder}
                      value={draft}
                      onChange={(e) =>
                        setFeedbackDrafts((prev) => ({ ...prev, [row.id]: e.target.value }))
                      }
                    />
                    <div style={{ marginTop: 10 }}>
                      <label
                        htmlFor={`opp-${row.id}`}
                        style={{ fontSize: 12, fontWeight: 800, display: "block" }}
                      >
                        {t.opportunityLabel}
                      </label>
                      <select
                        id={`opp-${row.id}`}
                        className="nb-input"
                        value={opportunityDrafts[row.id] ?? ""}
                        onChange={(e) =>
                          setOpportunityDrafts((prev) => ({
                            ...prev,
                            [row.id]: e.target.value,
                          }))
                        }
                      >
                        <option value="">
                          {expandedAction === "accepted"
                            ? t.opportunityAutoAccepted
                            : t.opportunityNone}
                        </option>
                        <optgroup label={t.opportunityPrimaryGroup}>
                          {OPPORTUNITY_OPTIONS.filter((o) => o.level === "primary").map(
                            (o) => (
                              <option key={o.value} value={o.value}>
                                {o.label}
                              </option>
                            )
                          )}
                        </optgroup>
                        <optgroup label={t.opportunitySecondaryGroup}>
                          {OPPORTUNITY_OPTIONS.filter((o) => o.level === "secondary").map(
                            (o) => (
                              <option key={o.value} value={o.value}>
                                {o.label}
                              </option>
                            )
                          )}
                        </optgroup>
                      </select>
                    </div>
                    {gateActive && (
                      <div className={styles.gateNotice}>{t.gateWait(gateRemaining)}</div>
                    )}
                    <div className={styles.sendRow}>
                      <span style={{ fontSize: 12, fontWeight: 700 }}>
                        {t.charCount(draft.trim().length, qualified)}
                      </span>
                      <button
                        type="button"
                        className={`${styles.btn} ${styles.btnSend}`}
                        onClick={() => handleSend(row.id)}
                        disabled={
                          (expandedAction === "rejected" && !draft.trim()) ||
                          isBusy ||
                          gateActive
                        }
                      >
                        {expandedAction === "accepted" ? t.sendAccepted : t.sendRejected}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
      </div>
    </div>
  );
}
