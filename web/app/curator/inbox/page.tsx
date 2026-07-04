"use client";

import { useEffect, useMemo, useState } from "react";
import { listSubmissions, respondSubmission, type Submission } from "@/lib/api";
import styles from "./page.module.css";

const CURATOR_ID = 1;
const SLA_URGENT_HOURS = 6;
const MS_PER_HOUR = 3_600_000;
const MS_PER_DAY = 24 * MS_PER_HOUR;

type RowStatus = Submission["status"];

type Row = {
  id: number;
  title: string;
  artist: string;
  status: RowStatus;
  feedback: string | null;
  isDemo: boolean;
  createdAt: string | null;
  deadline: string | null;
  // Demo rows use fixed display values straight from the approved mockup
  // instead of computed SLA math.
  fixedSlaText?: string;
  fixedSlaPercent?: number;
  fixedUrgent?: boolean;
};

const DEMO_ROWS: Row[] = [
  {
    id: 9001,
    title: "Senden Daha Güzel",
    artist: "Duman",
    status: "pending",
    feedback: null,
    isDemo: true,
    createdAt: null,
    deadline: null,
    fixedSlaText: "3 sa 40 dk",
    fixedSlaPercent: 8,
    fixedUrgent: true,
  },
  {
    id: 9002,
    title: "Kırık Ayna",
    artist: "Mor ve Ötesi",
    status: "pending",
    feedback: null,
    isDemo: true,
    createdAt: null,
    deadline: null,
    fixedSlaText: "58 sa 12 dk",
    fixedSlaPercent: 78,
    fixedUrgent: false,
  },
  {
    id: 9003,
    title: "Yeşil Sessizlik",
    artist: "Şebnem Ferah",
    status: "pending",
    feedback: null,
    isDemo: true,
    createdAt: null,
    deadline: null,
    fixedSlaText: "41 sa 05 dk",
    fixedSlaPercent: 55,
    fixedUrgent: false,
  },
  {
    id: 9004,
    title: "Uzak İhtimal",
    artist: "Athena",
    status: "pending",
    feedback: null,
    isDemo: true,
    createdAt: null,
    deadline: null,
    fixedSlaText: "22 sa 30 dk",
    fixedSlaPercent: 32,
    fixedUrgent: false,
  },
  {
    id: 9005,
    title: "Dön Bak Bana",
    artist: "maNga",
    status: "pending",
    feedback: null,
    isDemo: true,
    createdAt: null,
    deadline: null,
    fixedSlaText: "65 sa 50 dk",
    fixedSlaPercent: 88,
    fixedUrgent: false,
  },
];

function submissionToRow(sub: Submission): Row {
  return {
    id: sub.id,
    title: sub.title,
    artist: sub.artist,
    status: sub.status,
    feedback: sub.feedback,
    isDemo: false,
    createdAt: sub.created_at,
    deadline: sub.deadline,
  };
}

type SlaDisplay = { text: string; percent: number; urgent: boolean };

function formatSla(row: Row, now: number): SlaDisplay {
  if (row.isDemo) {
    return {
      text: row.fixedSlaText ?? "—",
      percent: row.fixedSlaPercent ?? 0,
      urgent: !!row.fixedUrgent,
    };
  }

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
  const [rows, setRows] = useState<Row[]>([]);
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [feedbackDrafts, setFeedbackDrafts] = useState<Record<number, string>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let cancelled = false;

    listSubmissions(CURATOR_ID).then((data) => {
      if (cancelled) return;
      if (data === null) {
        setIsDemoMode(true);
        setRows(DEMO_ROWS);
      } else {
        setIsDemoMode(false);
        setRows(data.map(submissionToRow));
      }
      setIsLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  // Keep SLA countdowns fresh for real (non-demo) rows.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  const stats = useMemo(() => {
    if (isDemoMode) {
      return { acceptRate: "%38", avgResponse: "14 sa", weekCount: "12" };
    }

    const decided = rows.filter((r) => r.status === "accepted" || r.status === "rejected");
    const accepted = rows.filter((r) => r.status === "accepted").length;
    const acceptRatePct =
      decided.length > 0 ? Math.round((accepted / decided.length) * 100) : 0;

    const responseHours = decided
      .map((r) => (r.createdAt ? (now - new Date(r.createdAt).getTime()) / MS_PER_HOUR : null))
      .filter((h): h is number => h !== null && h >= 0);
    const avgHours =
      responseHours.length > 0
        ? Math.round(responseHours.reduce((sum, h) => sum + h, 0) / responseHours.length)
        : 0;

    const weekAgo = now - 7 * MS_PER_DAY;
    const weekCount = rows.filter(
      (r) => r.createdAt && new Date(r.createdAt).getTime() >= weekAgo
    ).length;

    return {
      acceptRate: `%${acceptRatePct}`,
      avgResponse: `${avgHours} sa`,
      weekCount: String(weekCount),
    };
  }, [rows, isDemoMode, now]);

  function updateRow(id: number, patch: Partial<Row>) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  async function handleAccept(id: number) {
    setBusyId(id);
    const updated = await respondSubmission(id, "accepted");
    updateRow(id, { status: "accepted", feedback: updated?.feedback ?? null });
    setBusyId(null);
  }

  function handleRejectClick(id: number) {
    setExpandedId((current) => (current === id ? null : id));
  }

  async function handleSendReject(id: number) {
    const reason = (feedbackDrafts[id] ?? "").trim();
    if (!reason) return;

    setBusyId(id);
    const updated = await respondSubmission(id, "rejected", reason);
    updateRow(id, { status: "rejected", feedback: updated?.feedback ?? reason });
    setBusyId(null);
    setExpandedId(null);
  }

  return (
    <div>
      <nav className={styles.topbar}>
        <div className={styles.topbarInner}>
          <div className={styles.logo}>MuzikSEO</div>
          <div className={styles.userChip}>
            👤 &quot;Türk&quot; — Curator Paneli
          </div>
        </div>
      </nav>

      <div className={styles.wrap}>
        <h1 className={styles.pageTitle}>Gelen Kutusu</h1>

        {isDemoMode && (
          <div className={styles.apiBanner} role="status">
            <strong>API&apos;ye ulaşılamadı</strong> — demo veri gösteriliyor.
          </div>
        )}

        <div className={styles.statsBar}>
          <div className={styles.stat}>
            Kabul oranı <b>{stats.acceptRate}</b>
          </div>
          <div className={styles.sep} />
          <div className={styles.stat}>
            Ort. yanıt <b>{stats.avgResponse}</b>
          </div>
          <div className={styles.sep} />
          <div className={styles.stat}>
            Bu hafta <b>{stats.weekCount}</b> gönderim
          </div>
        </div>

        {isLoading && <div className={styles.loading}>Yükleniyor...</div>}

        {!isLoading &&
          rows.map((row) => {
            const sla = formatSla(row, now);
            const isExpanded = expandedId === row.id;
            const isBusy = busyId === row.id;
            const draft = feedbackDrafts[row.id] ?? "";
            const isPending = row.status === "pending";

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
                          onClick={() => handleAccept(row.id)}
                          disabled={isBusy}
                        >
                          Kabul Et
                        </button>
                        <button
                          type="button"
                          className={`${styles.btn} ${styles.btnReject}`}
                          onClick={() => handleRejectClick(row.id)}
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

                {isExpanded && (
                  <div className={styles.expanded}>
                    <label htmlFor={`reason-${row.id}`}>Red nedeni (zorunlu)</label>
                    <textarea
                      id={`reason-${row.id}`}
                      placeholder="Örn: Listenin tempo/tarz profiline uymuyor..."
                      value={draft}
                      onChange={(e) =>
                        setFeedbackDrafts((prev) => ({ ...prev, [row.id]: e.target.value }))
                      }
                    />
                    <div className={styles.sendRow}>
                      <button
                        type="button"
                        className={`${styles.btn} ${styles.btnSend}`}
                        onClick={() => handleSendReject(row.id)}
                        disabled={!draft.trim() || isBusy}
                      >
                        Gönder
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
