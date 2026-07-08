"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  createSchedule,
  getMe,
  getReadiness,
  getToken,
  listCurators,
  listSchedules,
  type Curator,
  type Readiness,
  type ScheduledSubmission,
  type User,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

const T = {
  tr: {
    loginRequired: "Giriş gerekli",
    gateText: "Yayın planı oluşturmak için sanatçı hesabınla giriş yap.",
    loginCta: "Giriş / Kayıt",
    creditsWord: "kredi",
    title: "Yayın Planı",
    promise: "Şarkını ileri bir tarihe planla — gönderim o anda otomatik yapılır.",
    readinessTitle: "Yayına Hazırlık Kontrolü",
    songPlaceholder: '"Sanatçı - Şarkı"',
    checkCta: "Kontrol Et",
    busy: "...",
    readinessEmpty: "Kontrol edilemedi — şarkı bulunamadı olabilir.",
    ready: "Hazır",
    threshold: (n: number) => `Eşik ${n}`,
    noIssues: "Sorun bulunamadı.",
    severity: {
      critical: "kritik",
      warn: "uyarı",
      info: "bilgi",
    } as Record<string, string>,
    newPlanTitle: "Yeni Plan",
    songFormPlaceholder: 'Şarkın: "Sanatçı - Şarkı"',
    chooseCurator: "Küratör seç",
    curatorAria: "Küratör seç",
    dateTimeAria: "Tarih ve saat",
    planCta: "Planla",
    scheduledTitle: "Planlanmış Gönderimler",
    loading: "Yükleniyor...",
    noSchedules: "Henüz planlanmış gönderim yok.",
    colSong: "Şarkı",
    colCurator: "Küratör",
    colTime: "Zaman",
    colStatus: "Durum",
    status: {
      executed: "Gönderildi",
      failed: "Başarısız",
      pending: "Bekliyor",
    } as Record<ScheduledSubmission["status"], string>,
    errSongFormat: 'Şarkıyı "Sanatçı - Şarkı" formatında yaz.',
    errCurator: "Bir küratör seç.",
    errDateTime: "Bir tarih-saat seç.",
    errPlanFailed: "Planlama başarısız — bilgileri kontrol et.",
  },
  en: {
    loginRequired: "Login required",
    gateText: "Log in with your artist account to create a release plan.",
    loginCta: "Log In / Sign Up",
    creditsWord: "credits",
    title: "Release Calendar",
    promise: "Schedule your song for a future date — the submission happens automatically then.",
    readinessTitle: "Release Readiness Check",
    songPlaceholder: '"Artist - Song"',
    checkCta: "Check",
    busy: "...",
    readinessEmpty: "Couldn't check — the song may not be found.",
    ready: "Ready",
    threshold: (n: number) => `Threshold ${n}`,
    noIssues: "No issues found.",
    severity: {
      critical: "critical",
      warn: "warning",
      info: "info",
    } as Record<string, string>,
    newPlanTitle: "New Plan",
    songFormPlaceholder: 'Your song: "Artist - Song"',
    chooseCurator: "Choose curator",
    curatorAria: "Choose curator",
    dateTimeAria: "Date and time",
    planCta: "Schedule",
    scheduledTitle: "Scheduled Submissions",
    loading: "Loading...",
    noSchedules: "No scheduled submissions yet.",
    colSong: "Song",
    colCurator: "Curator",
    colTime: "Time",
    colStatus: "Status",
    status: {
      executed: "Sent",
      failed: "Failed",
      pending: "Pending",
    } as Record<ScheduledSubmission["status"], string>,
    errSongFormat: 'Write your song as "Artist - Song".',
    errCurator: "Choose a curator.",
    errDateTime: "Choose a date and time.",
    errPlanFailed: "Scheduling failed — check the details.",
  },
} as const;

function parseSong(raw: string): { artist: string; title: string } | null {
  const trimmed = raw.trim();
  if (!trimmed.includes(" - ")) return null;
  const [artist, ...rest] = trimmed.split(" - ");
  const title = rest.join(" - ").trim();
  if (!artist.trim() || !title) return null;
  return { artist: artist.trim(), title };
}

function statusClass(status: ScheduledSubmission["status"], styles: Record<string, string>): string {
  if (status === "executed") return styles.ok;
  if (status === "failed") return styles.fail;
  return styles.pending;
}

function severityClass(severity: string, styles: Record<string, string>): string {
  if (severity === "critical") return styles.sevCritical;
  if (severity === "warn") return styles.sevWarn;
  return styles.sevInfo;
}

/** Yayin Plani — sanatci ilerideki bir tarihe gonderim planlar (createSchedule
 *  cron worker'i tetikler); ustte opsiyonel yayina hazirlik on kontrolu. */
export default function TakvimPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [curators, setCurators] = useState<Curator[]>([]);
  const [schedules, setSchedules] = useState<ScheduledSubmission[]>([]);
  const [loading, setLoading] = useState(true);

  // Planlama formu
  const [song, setSong] = useState("");
  const [curatorId, setCuratorId] = useState<number | "">("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Yayina hazirlik on kontrolu
  const [readinessQuery, setReadinessQuery] = useState("");
  const [readiness, setReadiness] = useState<Readiness | null | undefined>(undefined);
  const [readinessBusy, setReadinessBusy] = useState(false);

  useEffect(() => {
    (async () => {
      if (getToken()) {
        const me = await getMe();
        if (me && me.user.role === "artist") {
          setUser(me.user);
          const [curatorList, scheduleList] = await Promise.all([
            listCurators(),
            listSchedules(),
          ]);
          if (curatorList) setCurators(curatorList.filter((c) => c.status === "approved"));
          if (scheduleList) setSchedules(scheduleList);
        }
      }
      setChecked(true);
      setLoading(false);
    })();
  }, []);

  const curatorLabel = useMemo(() => {
    const map = new Map<number, string>();
    curators.forEach((c) => map.set(c.id, c.playlist_title));
    return (id: number) => map.get(id) ?? `#${id}`;
  }, [curators]);

  async function handlePlan(e: FormEvent) {
    e.preventDefault();
    setError("");
    const parsed = parseSong(song);
    if (!parsed) {
      setError(t.errSongFormat);
      return;
    }
    if (!curatorId) {
      setError(t.errCurator);
      return;
    }
    if (!scheduledAt) {
      setError(t.errDateTime);
      return;
    }
    const iso = new Date(scheduledAt).toISOString();
    setBusy(true);
    const created = await createSchedule(parsed.artist, parsed.title, curatorId, iso);
    setBusy(false);
    if (!created) {
      setError(t.errPlanFailed);
      return;
    }
    setSchedules((prev) => [created, ...prev]);
    setSong("");
    setCuratorId("");
    setScheduledAt("");
  }

  async function handleReadinessCheck(e: FormEvent) {
    e.preventDefault();
    const trimmed = readinessQuery.trim();
    if (!trimmed) return;
    setReadinessBusy(true);
    setReadiness(undefined);
    const result = await getReadiness(trimmed);
    setReadiness(result);
    setReadinessBusy(false);
  }

  if (checked && !user) {
    return (
      <div className={styles.gate}>
        <div className="nb-card" style={{ padding: 28, maxWidth: 460 }}>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <LangToggle />
          </div>
          <h2 className="nb-h">{t.loginRequired}</h2>
          <p className={styles.gateText}>{t.gateText}</p>
          <Link href="/giris" className="nb-btn">{t.loginCta}</Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <Link href="/" className={styles.logo}>Songdeck</Link>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {user && (
            <div className={styles.wallet}>💳 {user.credits} {t.creditsWord} · {user.name}</div>
          )}
          <LangToggle />
        </div>
      </div>

      <h1 className="nb-h">{t.title}</h1>
      <p className={styles.promise}>{t.promise}</p>

      <div className={`nb-card ${styles.readinessCard}`}>
        <div className={styles.readinessTitle}>{t.readinessTitle}</div>
        <form className={styles.readinessRow} onSubmit={handleReadinessCheck}>
          <input
            className="nb-input"
            placeholder={t.songPlaceholder}
            value={readinessQuery}
            onChange={(e) => setReadinessQuery(e.target.value)}
          />
          <button type="submit" className="nb-btn" disabled={readinessBusy}>
            {readinessBusy ? t.busy : t.checkCta}
          </button>
        </form>

        {readiness === null && (
          <div className={styles.readinessEmpty}>{t.readinessEmpty}</div>
        )}

        {readiness && (
          <div className={styles.readinessResult}>
            <div className={styles.readinessScoreRow}>
              <div className={styles.readinessScore}>{Math.round(readiness.score)}</div>
              <span
                className={`nb-pill ${readiness.ready ? "nb-pill--green" : "nb-pill--red"}`}
              >
                {readiness.ready ? t.ready : t.threshold(readiness.threshold)}
              </span>
            </div>
            {readiness.checklist.length === 0 ? (
              <div className={styles.readinessEmpty}>{t.noIssues}</div>
            ) : (
              <ul className={styles.checklist}>
                {readiness.checklist.map((item, i) => (
                  <li key={i} className={styles.checklistItem}>
                    <span className={`${styles.sevPill} ${severityClass(item.severity, styles)}`}>
                      {t.severity[item.severity] ?? item.severity}
                    </span>
                    <div>
                      <div className={styles.checklistMsg}>{item.message}</div>
                      {item.action && (
                        <div className={styles.checklistAction}>→ {item.action}</div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <h2 className="nb-h" style={{ fontSize: 18 }}>{t.newPlanTitle}</h2>
      <form className={`nb-card ${styles.planForm}`} onSubmit={handlePlan}>
        <input
          className="nb-input"
          placeholder={t.songFormPlaceholder}
          value={song}
          onChange={(e) => setSong(e.target.value)}
        />
        <select
          className="nb-input"
          value={curatorId}
          onChange={(e) => setCuratorId(e.target.value ? Number(e.target.value) : "")}
          aria-label={t.curatorAria}
        >
          <option value="">{t.chooseCurator}</option>
          {curators.map((c) => (
            <option key={c.id} value={c.id}>
              {c.playlist_title} — {c.name}
            </option>
          ))}
        </select>
        <input
          className="nb-input"
          type="datetime-local"
          value={scheduledAt}
          onChange={(e) => setScheduledAt(e.target.value)}
          aria-label={t.dateTimeAria}
        />
        {error && <div className={styles.error}>{error}</div>}
        <button type="submit" className="nb-btn nb-btn--purple" disabled={busy}>
          {busy ? t.busy : t.planCta}
        </button>
      </form>

      <h2 className="nb-h" style={{ fontSize: 18 }}>{t.scheduledTitle}</h2>
      {loading && <div className={styles.empty}>{t.loading}</div>}
      {!loading && schedules.length === 0 && (
        <div className={styles.empty}>{t.noSchedules}</div>
      )}
      {!loading && schedules.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t.colSong}</th>
                <th>{t.colCurator}</th>
                <th>{t.colTime}</th>
                <th>{t.colStatus}</th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((s) => (
                <tr key={s.id}>
                  <td>{s.artist} — {s.title}</td>
                  <td>{curatorLabel(s.curator_id)}</td>
                  <td>{new Date(s.scheduled_at).toLocaleString("tr-TR")}</td>
                  <td>
                    <span
                      className={`${styles.pill} ${statusClass(s.status, styles)}`}
                      title={s.error ?? undefined}
                    >
                      {t.status[s.status]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
