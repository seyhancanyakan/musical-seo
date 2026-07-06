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
import styles from "./page.module.css";

function parseSong(raw: string): { artist: string; title: string } | null {
  const trimmed = raw.trim();
  if (!trimmed.includes(" - ")) return null;
  const [artist, ...rest] = trimmed.split(" - ");
  const title = rest.join(" - ").trim();
  if (!artist.trim() || !title) return null;
  return { artist: artist.trim(), title };
}

function statusLabel(status: ScheduledSubmission["status"]): string {
  if (status === "executed") return "Gönderildi";
  if (status === "failed") return "Başarısız";
  return "Bekliyor";
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
      setError('Şarkıyı "Sanatçı - Şarkı" formatında yaz.');
      return;
    }
    if (!curatorId) {
      setError("Bir küratör seç.");
      return;
    }
    if (!scheduledAt) {
      setError("Bir tarih-saat seç.");
      return;
    }
    const iso = new Date(scheduledAt).toISOString();
    setBusy(true);
    const created = await createSchedule(parsed.artist, parsed.title, curatorId, iso);
    setBusy(false);
    if (!created) {
      setError("Planlama başarısız — bilgileri kontrol et.");
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
          <h2 className="nb-h">Giriş gerekli</h2>
          <p className={styles.gateText}>
            Yayın planı oluşturmak için sanatçı hesabınla giriş yap.
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
          <div className={styles.wallet}>💳 {user.credits} kredi · {user.name}</div>
        )}
      </div>

      <h1 className="nb-h">Yayın Planı</h1>
      <p className={styles.promise}>
        Şarkını ileri bir tarihe planla — gönderim o anda otomatik yapılır.
      </p>

      <div className={`nb-card ${styles.readinessCard}`}>
        <div className={styles.readinessTitle}>Yayına Hazırlık Kontrolü</div>
        <form className={styles.readinessRow} onSubmit={handleReadinessCheck}>
          <input
            className="nb-input"
            placeholder='"Sanatçı - Şarkı"'
            value={readinessQuery}
            onChange={(e) => setReadinessQuery(e.target.value)}
          />
          <button type="submit" className="nb-btn" disabled={readinessBusy}>
            {readinessBusy ? "..." : "Kontrol Et"}
          </button>
        </form>

        {readiness === null && (
          <div className={styles.readinessEmpty}>
            Kontrol edilemedi — şarkı bulunamadı olabilir.
          </div>
        )}

        {readiness && (
          <div className={styles.readinessResult}>
            <div className={styles.readinessScoreRow}>
              <div className={styles.readinessScore}>{Math.round(readiness.score)}</div>
              <span
                className={`nb-pill ${readiness.ready ? "nb-pill--green" : "nb-pill--red"}`}
              >
                {readiness.ready ? "Hazır" : `Eşik ${readiness.threshold}`}
              </span>
            </div>
            {readiness.checklist.length === 0 ? (
              <div className={styles.readinessEmpty}>Sorun bulunamadı.</div>
            ) : (
              <ul className={styles.checklist}>
                {readiness.checklist.map((item, i) => (
                  <li key={i} className={styles.checklistItem}>
                    <span className={`${styles.sevPill} ${severityClass(item.severity, styles)}`}>
                      {item.severity}
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

      <h2 className="nb-h" style={{ fontSize: 18 }}>Yeni Plan</h2>
      <form className={`nb-card ${styles.planForm}`} onSubmit={handlePlan}>
        <input
          className="nb-input"
          placeholder='Şarkın: "Sanatçı - Şarkı"'
          value={song}
          onChange={(e) => setSong(e.target.value)}
        />
        <select
          className="nb-input"
          value={curatorId}
          onChange={(e) => setCuratorId(e.target.value ? Number(e.target.value) : "")}
          aria-label="Küratör seç"
        >
          <option value="">Küratör seç</option>
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
          aria-label="Tarih ve saat"
        />
        {error && <div className={styles.error}>{error}</div>}
        <button type="submit" className="nb-btn nb-btn--purple" disabled={busy}>
          {busy ? "..." : "Planla"}
        </button>
      </form>

      <h2 className="nb-h" style={{ fontSize: 18 }}>Planlanmış Gönderimler</h2>
      {loading && <div className={styles.empty}>Yükleniyor...</div>}
      {!loading && schedules.length === 0 && (
        <div className={styles.empty}>Henüz planlanmış gönderim yok.</div>
      )}
      {!loading && schedules.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Şarkı</th>
                <th>Küratör</th>
                <th>Zaman</th>
                <th>Durum</th>
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
                      {statusLabel(s.status)}
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
