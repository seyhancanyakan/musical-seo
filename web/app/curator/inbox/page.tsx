"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  getMe,
  getToken,
  linkCuratorPlaylist,
  myCurator,
  myInbox,
  myRespond,
  verifyOwnershipCheck,
  verifyOwnershipStart,
  type Curator,
  type Earnings,
  type Submission,
  type User,
} from "@/lib/api";
import styles from "./page.module.css";

const SLA_URGENT_HOURS = 6;
const MS_PER_HOUR = 3_600_000;
const MS_PER_DAY = 24 * MS_PER_HOUR;
const QUALIFIED_MIN_CHARS = 120; // backend esigiyle ayni: nitelikli = odenir

type RowStatus = Submission["status"];

type Row = {
  id: number;
  title: string;
  artist: string;
  status: RowStatus;
  feedback: string | null;
  createdAt: string | null;
  deadline: string | null;
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
  };
}

type SlaDisplay = { text: string; percent: number; urgent: boolean };

function formatSla(row: Row, now: number): SlaDisplay {
  if (!row.deadline) {
    return { text: "—", percent: 0, urgent: false };
  }

  const deadlineMs = new Date(row.deadline).getTime();
  const createdMs = row.createdAt ? new Date(row.createdAt).getTime() : deadlineMs;
  const remainingMs = deadlineMs - now;

  if (remainingMs <= 0) {
    return { text: "Süre doldu", percent: 0, urgent: true };
  }

  const totalMs = deadlineMs - createdMs;
  const totalMinutes = Math.floor(remainingMs / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  const percent = totalMs > 0 ? Math.min(100, Math.max(0, (remainingMs / totalMs) * 100)) : 0;

  return {
    text: `${hours} sa ${String(minutes).padStart(2, "0")} dk`,
    percent,
    urgent: remainingMs <= SLA_URGENT_HOURS * MS_PER_HOUR,
  };
}

function statusLabel(status: RowStatus): string {
  if (status === "accepted") return "Kabul edildi";
  if (status === "rejected") return "Reddedildi";
  if (status === "expired") return "Süresi doldu";
  return status;
}

function statusClass(status: RowStatus): string {
  if (status === "accepted") return styles.statusAccepted;
  if (status === "rejected") return styles.statusRejected;
  return styles.statusExpired;
}

export default function CuratorInboxPage() {
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [earnings, setEarnings] = useState<Earnings | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [apiFailed, setApiFailed] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedAction, setExpandedAction] = useState<"accepted" | "rejected">("rejected");
  const [feedbackDrafts, setFeedbackDrafts] = useState<Record<number, string>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());

  // Spotify/Deezer playlist sahiplik dogrulamasi
  const [curatorRec, setCuratorRec] = useState<Curator | null>(null);
  const [verifyCode, setVerifyCode] = useState<string | null>(null);
  const [verifyMsg, setVerifyMsg] = useState("");
  const [linkDraft, setLinkDraft] = useState("");

  async function handleLinkPlaylist() {
    setVerifyMsg("");
    const curator = await linkCuratorPlaylist(linkDraft.trim());
    if (!curator) {
      setVerifyMsg("Liste bağlanamadı — linki kontrol et (Deezer veya Spotify, herkese açık).");
      return;
    }
    setCuratorRec(curator);
    setUser((prev) => (prev ? { ...prev, curator_id: curator.id } : prev));
  }

  async function handleVerifyStart() {
    setVerifyMsg("");
    const result = await verifyOwnershipStart();
    if (result) setVerifyCode(result.code);
    else setVerifyMsg("Kod üretilemedi — tekrar dene.");
  }

  async function handleVerifyCheck() {
    setVerifyMsg("");
    const curator = await verifyOwnershipCheck();
    if (curator) {
      setCuratorRec(curator);
      setVerifyCode(null);
      setVerifyMsg("✅ Sahiplik doğrulandı — listen onaylandı, kodu açıklamadan silebilirsin.");
    } else {
      setVerifyMsg("Kod açıklamada bulunamadı — ekledikten 1-2 dk sonra tekrar dene.");
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

  const stats = useMemo(() => {
    const decided = rows.filter((r) => r.status === "accepted" || r.status === "rejected");
    const accepted = rows.filter((r) => r.status === "accepted").length;
    const acceptRatePct =
      decided.length > 0 ? Math.round((accepted / decided.length) * 100) : 0;
    const weekAgo = now - 7 * MS_PER_DAY;
    const weekCount = rows.filter(
      (r) => r.createdAt && new Date(r.createdAt).getTime() >= weekAgo
    ).length;
    return { acceptRate: `%${acceptRatePct}`, weekCount: String(weekCount) };
  }, [rows, now]);

  function updateRow(id: number, patch: Partial<Row>) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function handleActionClick(id: number, action: "accepted" | "rejected") {
    setExpandedAction(action);
    setExpandedId((current) => (current === id && expandedAction === action ? null : id));
  }

  async function handleSend(id: number) {
    const draft = (feedbackDrafts[id] ?? "").trim();
    if (expandedAction === "rejected" && !draft) return;

    setBusyId(id);
    const updated = await myRespond(id, expandedAction, draft);
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
        <h1 className={styles.pageTitle}>Curator Gelen Kutusu</h1>
        <p style={{ fontWeight: 600, margin: "16px 0 24px" }}>
          Gelen kutunu görmek için küratör hesabınla giriş yap.
        </p>
        <Link href="/giris" className="nb-btn">Giriş / Kayıt</Link>
      </div>
    );
  }

  return (
    <div>
      <nav className={styles.topbar}>
        <div className={styles.topbarInner}>
          <Link href="/" className={styles.logo}>MuzikSEO</Link>
          <div className={styles.userChip}>
            👤 {user ? `${user.name} — Curator Paneli` : "Curator Paneli"}
          </div>
        </div>
      </nav>

      <div className={styles.wrap}>
        <h1 className={styles.pageTitle}>Gelen Kutusu</h1>

        {apiFailed && (
          <div className={styles.apiBanner} role="status">
            <strong>API&apos;ye ulaşılamadı</strong> — tekrar dene.
          </div>
        )}

        {user && !user.curator_id && (
          <div className={styles.apiBanner} role="status">
            <strong>Playlist bağlı değil.</strong> Deezer veya Spotify playlist
            linkini ekle:
            <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
              <input
                className="nb-input"
                placeholder="https://open.spotify.com/playlist/... veya deezer.com/playlist/..."
                value={linkDraft}
                onChange={(e) => setLinkDraft(e.target.value)}
              />
              <button type="button" className="nb-btn" onClick={handleLinkPlaylist}>
                Bağla
              </button>
            </div>
            {verifyMsg && <div style={{ marginTop: 8, fontWeight: 800 }}>{verifyMsg}</div>}
          </div>
        )}

        {curatorRec && !curatorRec.ownership_verified && (
          <div className={styles.apiBanner} role="status">
            <strong>Liste sahipliğini doğrula</strong> — doğrulanana kadar
            gönderim alamazsın.
            {verifyCode ? (
              <div style={{ marginTop: 10 }}>
                1. Bu kodu playlist <b>açıklamasına</b> ekle:{" "}
                <code style={{ fontSize: 16, fontWeight: 900, background: "#fff",
                               padding: "2px 8px", border: "2px solid #000" }}>
                  {verifyCode}
                </code>
                <br />
                2. Kaydettikten sonra doğrula:
                <button type="button" className="nb-btn" style={{ marginLeft: 10 }}
                        onClick={handleVerifyCheck}>
                  Doğrula
                </button>
              </div>
            ) : (
              <button type="button" className="nb-btn" style={{ marginLeft: 10 }}
                      onClick={handleVerifyStart}>
                Doğrulama kodu al
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
            Kabul oranı <b>{stats.acceptRate}</b>
          </div>
          <div className={styles.sep} />
          <div className={styles.stat}>
            Bu hafta <b>{stats.weekCount}</b> gönderim
          </div>
          {earnings && (
            <>
              <div className={styles.sep} />
              <div className={styles.stat}>
                Kazanç <b>${earnings.total_usd.toFixed(0)}</b> (bekleyen $
                {earnings.pending_usd.toFixed(0)})
              </div>
            </>
          )}
        </div>

        {isLoading && <div className={styles.loading}>Yükleniyor...</div>}

        {!isLoading && rows.length === 0 && !apiFailed && (
          <div className={styles.loading}>
            Henüz gönderim yok — sanatçılar şarkı gönderince burada görünür.
          </div>
        )}

        {!isLoading &&
          rows.map((row) => {
            const sla = formatSla(row, now);
            const isExpanded = expandedId === row.id;
            const isBusy = busyId === row.id;
            const draft = feedbackDrafts[row.id] ?? "";
            const isPending = row.status === "pending";
            const qualified = draft.trim().length >= QUALIFIED_MIN_CHARS;

            return (
              <div key={row.id}>
                <div className={styles.rowCard}>
                  <button
                    type="button"
                    className={styles.playBtn}
                    aria-label={`${row.title} — önizlemeyi oynat`}
                  >
                    <span className={styles.playTri} />
                  </button>

                  <div className={styles.trackInfo}>
                    <div className={styles.name}>{row.title}</div>
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
                          Kabul Et
                        </button>
                        <button
                          type="button"
                          className={`${styles.btn} ${styles.btnReject}`}
                          onClick={() => handleActionClick(row.id, "rejected")}
                          disabled={isBusy}
                        >
                          Reddet
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className={`${styles.statusResult} ${statusClass(row.status)}`}>
                      {statusLabel(row.status)}
                    </div>
                  )}
                </div>

                {isExpanded && isPending && (
                  <div className={styles.expanded}>
                    <label htmlFor={`reason-${row.id}`}>
                      {expandedAction === "accepted"
                        ? "Geri bildirim (opsiyonel — 120+ karakter nitelikli sayılır ve $1 kazandırır)"
                        : "Red nedeni (zorunlu — 120+ karakter nitelikli sayılır ve $1 kazandırır)"}
                    </label>
                    <textarea
                      id={`reason-${row.id}`}
                      placeholder="Örn: Miks temiz ama nakarat listenin tempo profiline göre yavaş kalıyor; ikinci verse'teki vokal katmanı güçlü..."
                      value={draft}
                      onChange={(e) =>
                        setFeedbackDrafts((prev) => ({ ...prev, [row.id]: e.target.value }))
                      }
                    />
                    <div className={styles.sendRow}>
                      <span style={{ fontSize: 12, fontWeight: 700 }}>
                        {draft.trim().length} karakter {qualified ? "— nitelikli ✓ ($1)" : ""}
                      </span>
                      <button
                        type="button"
                        className={`${styles.btn} ${styles.btnSend}`}
                        onClick={() => handleSend(row.id)}
                        disabled={(expandedAction === "rejected" && !draft.trim()) || isBusy}
                      >
                        {expandedAction === "accepted" ? "Kabul + Gönder" : "Reddet + Gönder"}
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
