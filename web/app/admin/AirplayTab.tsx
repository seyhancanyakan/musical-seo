"use client";

import { useEffect, useState } from "react";
import {
  adminAddStation,
  adminAirplayPoll,
  adminStations,
  type AirplayHit,
  type AirplayStation,
} from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";
import { formatDate } from "./utils";

type StationKind = "icecast" | "shoutcast";

const KIND_KEYS: StationKind[] = ["icecast", "shoutcast"];

const T = {
  tr: {
    addTitle: "İstasyon Ekle",
    nameLabel: "İstasyon Adı",
    namePlaceholder: "Örn. Radyo Eksen",
    metaUrlLabel: "Meta URL",
    metaUrlPlaceholder: "https://stream.example.com/status-json.xsl",
    kindLabel: "Tür",
    kindLabels: {
      icecast: "Icecast",
      shoutcast: "Shoutcast",
    } as Record<StationKind, string>,
    addBtn: "Ekle",
    addingBtn: "Ekleniyor...",
    addErrorMissing: "İstasyon adı ve meta URL gerekli.",
    addErrorFailed: "İstasyon eklenemedi — meta URL'yi kontrol et.",
    listTitle: "İstasyonlar",
    loading: "Yükleniyor...",
    empty: "Henüz istasyon eklenmedi.",
    columns: {
      name: "İstasyon",
      metaUrl: "Meta URL",
      kind: "Tür",
      status: "Durum",
      added: "Eklendi",
    },
    active: "Aktif",
    inactive: "Pasif",
    pollTitle: "Yoklama",
    pollText: "Arka plandaki 10 dakikalık döngü beklenmeden istasyonları hemen tara.",
    pollBtn: "Şimdi Tara",
    pollingBtn: "Taranıyor...",
    pollErrorFailed: "Yoklama başarısız — tekrar dene.",
    pollResult: (checked: number, hitCount: number) =>
      `${checked} istasyon tarandı · ${hitCount} yeni çalma yakalandı.`,
    hitsColDate: "Tarih - Saat",
    hitsColStation: "İstasyon",
    hitsColSong: "Şarkı",
    hitsColRaw: "Ham Başlık",
  },
  en: {
    addTitle: "Add Station",
    nameLabel: "Station Name",
    namePlaceholder: "e.g. Radio Eksen",
    metaUrlLabel: "Meta URL",
    metaUrlPlaceholder: "https://stream.example.com/status-json.xsl",
    kindLabel: "Kind",
    kindLabels: {
      icecast: "Icecast",
      shoutcast: "Shoutcast",
    } as Record<StationKind, string>,
    addBtn: "Add",
    addingBtn: "Adding...",
    addErrorMissing: "Station name and meta URL are required.",
    addErrorFailed: "Couldn't add station — check the meta URL.",
    listTitle: "Stations",
    loading: "Loading...",
    empty: "No stations added yet.",
    columns: {
      name: "Station",
      metaUrl: "Meta URL",
      kind: "Kind",
      status: "Status",
      added: "Added",
    },
    active: "Active",
    inactive: "Inactive",
    pollTitle: "Poll",
    pollText: "Scan stations right now, without waiting for the 10-minute background loop.",
    pollBtn: "Poll Now",
    pollingBtn: "Polling...",
    pollErrorFailed: "Poll failed — try again.",
    pollResult: (checked: number, hitCount: number) =>
      `Scanned ${checked} stations · caught ${hitCount} new hit(s).`,
    hitsColDate: "Date - Time",
    hitsColStation: "Station",
    hitsColSong: "Song",
    hitsColRaw: "Raw Title",
  },
} as const;

/** Admin: radyo istasyon yonetimi — icecast/shoutcast meta URL ekle,
 *  10 dakikalik arka plan taramasini bekle ya da elle "Simdi Tara" tetikle. */
export default function AirplayTab() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [stations, setStations] = useState<AirplayStation[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const [name, setName] = useState("");
  const [metaUrl, setMetaUrl] = useState("");
  const [kind, setKind] = useState<StationKind>("icecast");
  const [addBusy, setAddBusy] = useState(false);
  const [addError, setAddError] = useState("");

  const [pollBusy, setPollBusy] = useState(false);
  const [pollError, setPollError] = useState("");
  const [pollResult, setPollResult] = useState<{ checked: number; hits: AirplayHit[] } | null>(
    null
  );

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    adminStations().then((data) => {
      if (cancelled) return;
      setStations(data ?? []);
      setIsLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleAddStation() {
    setAddError("");
    if (!name.trim() || !metaUrl.trim()) {
      setAddError(t.addErrorMissing);
      return;
    }
    setAddBusy(true);
    const created = await adminAddStation({
      name: name.trim(),
      meta_url: metaUrl.trim(),
      kind,
    });
    setAddBusy(false);
    if (!created) {
      setAddError(t.addErrorFailed);
      return;
    }
    setStations((prev) => [created, ...prev]);
    setName("");
    setMetaUrl("");
    setKind("icecast");
  }

  async function handlePollNow() {
    setPollError("");
    setPollResult(null);
    setPollBusy(true);
    const res = await adminAirplayPoll();
    setPollBusy(false);
    if (!res) {
      setPollError(t.pollErrorFailed);
      return;
    }
    setPollResult({ checked: res.checked_stations, hits: res.hits });
  }

  return (
    <div>
      <div className={styles.formCard}>
        <div className={styles.formLabel} style={{ marginBottom: 18 }}>
          {t.addTitle}
        </div>
        <div className={styles.formGrid}>
          <label className={styles.formLabel}>
            {t.nameLabel}
            <input
              className="nb-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t.namePlaceholder}
            />
          </label>
          <label className={styles.formLabel}>
            {t.metaUrlLabel}
            <input
              className="nb-input"
              value={metaUrl}
              onChange={(e) => setMetaUrl(e.target.value)}
              placeholder={t.metaUrlPlaceholder}
            />
          </label>
          <label className={styles.formLabel}>
            {t.kindLabel}
            <select
              className="nb-input"
              value={kind}
              onChange={(e) => setKind(e.target.value as StationKind)}
            >
              {KIND_KEYS.map((key) => (
                <option key={key} value={key}>
                  {t.kindLabels[key]}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className={styles.formActions}>
          <button type="button" className="nb-btn" onClick={handleAddStation} disabled={addBusy}>
            {addBusy ? t.addingBtn : t.addBtn}
          </button>
        </div>
        {addError && <div className={styles.errorBanner}>{addError}</div>}
      </div>

      <h3 style={{ margin: "24px 0 12px" }}>{t.listTitle}</h3>

      {isLoading && <div className={styles.loading}>{t.loading}</div>}

      {!isLoading && stations.length === 0 && (
        <div className={styles.empty}>{t.empty}</div>
      )}

      {!isLoading && stations.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t.columns.name}</th>
                <th>{t.columns.metaUrl}</th>
                <th>{t.columns.kind}</th>
                <th>{t.columns.status}</th>
                <th>{t.columns.added}</th>
              </tr>
            </thead>
            <tbody>
              {stations.map((s) => (
                <tr key={s.id}>
                  <td>
                    <div className={styles.name}>{s.name}</div>
                  </td>
                  <td className={styles.sub}>{s.meta_url}</td>
                  <td>{s.kind}</td>
                  <td>
                    <span
                      className={`${styles.badge} ${
                        s.active ? styles.badgeApproved : styles.badgeRejected
                      }`}
                    >
                      {s.active ? t.active : t.inactive}
                    </span>
                  </td>
                  <td className={styles.sub}>{formatDate(s.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className={styles.formCard} style={{ marginTop: 24 }}>
        <div className={styles.formLabel} style={{ marginBottom: 12 }}>
          {t.pollTitle}
        </div>
        <p className={styles.sub} style={{ marginBottom: 14 }}>{t.pollText}</p>
        <div className={styles.formActions}>
          <button type="button" className="nb-btn" onClick={handlePollNow} disabled={pollBusy}>
            {pollBusy ? t.pollingBtn : t.pollBtn}
          </button>
        </div>
        {pollError && <div className={styles.errorBanner}>{pollError}</div>}
        {pollResult && (
          <div className={styles.resultBanner}>
            {t.pollResult(pollResult.checked, pollResult.hits.length)}
          </div>
        )}
        {pollResult && pollResult.hits.length > 0 && (
          <div className={styles.tableWrap} style={{ marginTop: 14 }}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>{t.hitsColDate}</th>
                  <th>{t.hitsColStation}</th>
                  <th>{t.hitsColSong}</th>
                  <th>{t.hitsColRaw}</th>
                </tr>
              </thead>
              <tbody>
                {pollResult.hits.map((h) => (
                  <tr key={h.id}>
                    <td className={styles.sub}>{formatDate(h.created_at)}</td>
                    <td>{h.station_name}</td>
                    <td>{h.artist} — {h.title}</td>
                    <td className={styles.sub}>{h.raw_title ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
