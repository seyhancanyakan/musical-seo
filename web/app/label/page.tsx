"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { applyLabel, labelReport, type RisingArtistEntry } from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type ApplyState = "idle" | "busy" | "success" | "error";
type ReportState = "idle" | "busy" | "success" | "error";

const T = {
  tr: {
    heroKicker: "Label / A&R",
    heroTitle: "Yükselen bağımsız sanatçıları veriyle keşfet",
    heroTagline:
      "SEO skor trendi, API-doğrulamalı playlist yerleşimleri, kabul oranları. Beyan değil, kanıt.",
    proof: [
      { icon: "📈", title: "SEO skor trendi", text: "Sanatçının 30 günlük skor değişimini gör — büyüyeni erken yakala." },
      { icon: "✅", title: "API-doğrulamalı yerleşim", text: "Playlist kabulleri Deezer/Spotify API ile doğrulanır, beyana dayanmaz." },
      { icon: "🎯", title: "Kabul oranı", text: "Küratörler tarafından ne sıklıkla kabul edildiğini net rakamla gör." },
    ],
    applyTitle: "Başvuru Yap",
    applyNote: "Onaylanırsa 30 günlük erişim token'ı e-postana iletilir (pilot: manuel onay).",
    companyPlaceholder: "Şirket / Label adı",
    contactNamePlaceholder: "İletişim adı",
    emailPlaceholder: "E-posta",
    notePlaceholder: "Not (opsiyonel) — kimi/ne tür sanatçı arıyorsun?",
    submit: "Başvur",
    busy: "...",
    applySuccess:
      "Başvurun alındı — onaylanınca 30 günlük erişim token'ı e-postana iletilir (pilot: manuel).",
    applyError: "Başvuru gönderilemedi — tekrar dene.",
    reportTitle: "Rapor Görüntüle",
    reportNote: "Erişim token'ın var mı?",
    tokenPlaceholder: "Erişim token'ı",
    openReport: "Raporu Aç",
    reportError: "Geçersiz veya süresi dolmuş token.",
    reportEmpty: "Bu dönemde yükselen sanatçı bulunamadı.",
    columns: {
      artist: "Sanatçı",
      score: "Son Skor",
      delta: "30g Değişim",
      accepted: "Kabul",
      verified: "Doğrulanmış Yerleşim",
      rate: "Kabul Oranı",
    },
  },
  en: {
    heroKicker: "Label / A&R",
    heroTitle: "Discover rising independent artists — backed by data",
    heroTagline:
      "SEO score trend, API-verified playlist placements, acceptance rates. Proof, not claims.",
    proof: [
      { icon: "📈", title: "SEO score trend", text: "See an artist's 30-day score change — spot growth early." },
      { icon: "✅", title: "API-verified placements", text: "Playlist acceptances are verified via Deezer/Spotify APIs, not self-reported." },
      { icon: "🎯", title: "Acceptance rate", text: "See exactly how often curators accept them, in hard numbers." },
    ],
    applyTitle: "Apply",
    applyNote: "If approved, a 30-day access token is emailed to you (pilot: manual approval).",
    companyPlaceholder: "Company / Label name",
    contactNamePlaceholder: "Contact name",
    emailPlaceholder: "Email",
    notePlaceholder: "Note (optional) — who/what kind of artist are you looking for?",
    submit: "Apply",
    busy: "...",
    applySuccess:
      "Your application has been received — once approved, a 30-day access token will be emailed to you (pilot: manual).",
    applyError: "Couldn't send your application — try again.",
    reportTitle: "View Report",
    reportNote: "Have an access token?",
    tokenPlaceholder: "Access token",
    openReport: "Open Report",
    reportError: "Invalid or expired token.",
    reportEmpty: "No rising artists found for this period.",
    columns: {
      artist: "Artist",
      score: "Latest Score",
      delta: "30d Change",
      accepted: "Accepted",
      verified: "Verified Placements",
      rate: "Accept Rate",
    },
  },
} as const;

function deltaClass(styles: Record<string, string>, delta: number | null): string {
  if (delta === null) return styles.deltaFlat;
  if (delta > 0) return styles.deltaUp;
  if (delta < 0) return styles.deltaDown;
  return styles.deltaFlat;
}

function formatDelta(delta: number | null): string {
  if (delta === null) return "—";
  if (delta > 0) return `↑ +${delta.toFixed(1)}`;
  if (delta < 0) return `↓ ${delta.toFixed(1)}`;
  return "0.0";
}

function formatRate(rate: number | null): string {
  if (rate === null) return "—";
  return `%${Math.round(rate * 100)}`;
}

/** Label/A&R B2B tanitim + basvuru + token'li rapor goruntuleme — auth gerektirmez. */
export default function LabelPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [company, setCompany] = useState("");
  const [contactName, setContactName] = useState("");
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [applyState, setApplyState] = useState<ApplyState>("idle");

  const [tokenInput, setTokenInput] = useState("");
  const [reportState, setReportState] = useState<ReportState>("idle");
  const [report, setReport] = useState<RisingArtistEntry[] | null>(null);

  async function handleApply(e: FormEvent) {
    e.preventDefault();
    if (applyState === "busy") return;
    setApplyState("busy");
    const result = await applyLabel({
      company,
      contact_name: contactName,
      email,
      note: note.trim() || undefined,
    });
    if (result) {
      setApplyState("success");
      setCompany("");
      setContactName("");
      setEmail("");
      setNote("");
    } else {
      setApplyState("error");
    }
  }

  async function handleOpenReport(e: FormEvent) {
    e.preventDefault();
    if (reportState === "busy" || !tokenInput.trim()) return;
    setReportState("busy");
    setReport(null);
    const result = await labelReport(tokenInput.trim());
    if (result) {
      setReportState("success");
      setReport(result);
    } else {
      setReportState("error");
    }
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.top}>
        <Link href="/" className={styles.logo}>Sozy Echo</Link>
        <LangToggle />
      </div>

      <div className={styles.hero}>
        <span className={styles.heroKicker}>{t.heroKicker}</span>
        <h1 className={`nb-h ${styles.heroTitle}`}>{t.heroTitle}</h1>
        <p className={styles.heroTagline}>{t.heroTagline}</p>
      </div>

      <div className={styles.proofGrid}>
        {t.proof.map((p) => (
          <div key={p.title} className={`nb-card ${styles.proofCard}`}>
            <span className={styles.proofIcon}>{p.icon}</span>
            <div className={styles.proofTitle}>{p.title}</div>
            <div className={styles.proofText}>{p.text}</div>
          </div>
        ))}
      </div>

      <div className={styles.grid}>
        <div className={`nb-card ${styles.card}`}>
          <h2 className={`nb-h ${styles.cardTitle}`}>{t.applyTitle}</h2>
          <p className={styles.cardNote}>{t.applyNote}</p>
          <form onSubmit={handleApply} className={styles.form}>
            <input
              className="nb-input"
              placeholder={t.companyPlaceholder}
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              required
            />
            <input
              className="nb-input"
              placeholder={t.contactNamePlaceholder}
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
              required
            />
            <input
              className="nb-input"
              type="email"
              placeholder={t.emailPlaceholder}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <textarea
              className="nb-input"
              placeholder={t.notePlaceholder}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
            <button
              type="submit"
              className={`nb-btn nb-btn--purple ${applyState === "busy" ? styles.busyBtn : ""}`}
              disabled={applyState === "busy"}
            >
              {applyState === "busy" ? t.busy : t.submit}
            </button>
            {applyState === "success" && <div className={styles.success}>{t.applySuccess}</div>}
            {applyState === "error" && <div className={styles.error}>{t.applyError}</div>}
          </form>
        </div>

        <div className={`nb-card ${styles.card}`}>
          <h2 className={`nb-h ${styles.cardTitle}`}>{t.reportTitle}</h2>
          <p className={styles.cardNote}>{t.reportNote}</p>
          <form onSubmit={handleOpenReport} className={styles.tokenRow}>
            <input
              className="nb-input"
              placeholder={t.tokenPlaceholder}
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              required
            />
            <button
              type="submit"
              className={`nb-btn ${reportState === "busy" ? styles.busyBtn : ""}`}
              disabled={reportState === "busy"}
            >
              {reportState === "busy" ? t.busy : t.openReport}
            </button>
          </form>
          {reportState === "error" && <div className={styles.error}>{t.reportError}</div>}

          {reportState === "success" && report && (
            <div className={styles.reportWrap}>
              {report.length === 0 ? (
                <div className={styles.cardNote}>{t.reportEmpty}</div>
              ) : (
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>{t.columns.artist}</th>
                        <th className={styles.num}>{t.columns.score}</th>
                        <th className={styles.num}>{t.columns.delta}</th>
                        <th className={styles.num}>{t.columns.accepted}</th>
                        <th className={styles.num}>{t.columns.verified}</th>
                        <th className={styles.num}>{t.columns.rate}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.map((r) => (
                        <tr key={r.artist_name}>
                          <td className={styles.name}>{r.artist_name}</td>
                          <td className={styles.num}>{r.latest_score.toFixed(1)}</td>
                          <td className={`${styles.num} ${deltaClass(styles, r.score_delta)}`}>
                            {formatDelta(r.score_delta)}
                          </td>
                          <td className={styles.num}>{r.accepted}</td>
                          <td className={styles.num}>{r.verified_placements}</td>
                          <td className={styles.num}>{formatRate(r.accept_rate)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
