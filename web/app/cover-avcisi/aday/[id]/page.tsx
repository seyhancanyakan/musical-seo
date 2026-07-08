"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  coverLicense,
  getCoverCandidate,
  reviewCandidate,
  type CoverCandidate,
} from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import SiteHeader from "@/components/SiteHeader";
import styles from "./page.module.css";

const DEMO_CANDIDATE: CoverCandidate = {
  id: 4471,
  hunt_id: 9001,
  title: "Yağmur Sonrası (Cover) — Akustik",
  channel: "@acoustic_covers_tr",
  platform: "YouTube · @acoustic_covers_tr",
  views: 340000,
  similarity: 0.91,
  confidence: "high",
  match_reasons: ["audio profil", "söz %88", "başlık"],
  status: "pending",
  original_profile: { bpm: 92, energy: 0.48, brightness: 0.55, key: "A min" },
  candidate_profile: { bpm: 94, energy: 0.52, brightness: 0.58, key: "C maj*" },
  license_offer_usd: 220,
  match_notes: "BPM ±%2, tonalite harmonik (relative), söz benzerliği %88. Mesafe 0.09.",
};

const DEFAULT_PROFILE = { bpm: 0, energy: 0, brightness: 0, key: "—" };

const T = {
  tr: {
    loading: "Aday yükleniyor…",
    confidenceHigh: "Yüksek Güven",
    confidenceMedium: "Orta Güven",
    confidenceLow: "Düşük Güven",
    simPrefix: "Benzerlik",
    candidateTitle: (id: string) => `Aday #${id} — audio profil eşleşmesi`,
    originalLabel: "◆ Orijinal",
    candidateLabel: "▶ Aday",
    bpm: "BPM",
    energy: "Enerji",
    brightness: "Parlaklık",
    key: "Tonalite",
    reasonsTitle: "Eşleşme Nedenleri",
    licenseTitle: "Lisans Teklifi",
    licenseNote: "syncmarket fiyatı — akustik cover, orta erişim. %15 komisyon dahil.",
    sendOffer: "Teklif gönder",
    claimTitle: "Telif Claim",
    claimNote: "YouTube Content ID claim talimatı + ISRC/ISWC referansı hazır.",
    claimDoc: "Claim dökümanı ⬇",
    approve: "✓ Onayla",
    reject: "✕ Reddet — cover değil",
    offerSent: "Teklif gönderildi.",
  },
  en: {
    loading: "Loading candidate…",
    confidenceHigh: "High Confidence",
    confidenceMedium: "Medium Confidence",
    confidenceLow: "Low Confidence",
    simPrefix: "Similarity",
    candidateTitle: (id: string) => `Candidate #${id} — audio profile match`,
    originalLabel: "◆ Original",
    candidateLabel: "▶ Candidate",
    bpm: "BPM",
    energy: "Energy",
    brightness: "Brightness",
    key: "Key",
    reasonsTitle: "Match Reasons",
    licenseTitle: "License Offer",
    licenseNote: "syncmarket price — acoustic cover, medium reach. 15% commission included.",
    sendOffer: "Send offer",
    claimTitle: "Copyright Claim",
    claimNote: "YouTube Content ID claim instructions + ISRC/ISWC reference ready.",
    claimDoc: "Claim document ⬇",
    approve: "✓ Approve",
    reject: "✕ Reject — not a cover",
    offerSent: "Offer sent.",
  },
};

const CONFIDENCE_PILL: Record<string, string> = {
  high: "nb-pill--red",
  medium: "nb-pill--blue",
  low: "nb-pill--green",
};
const CONFIDENCE_PILL_DEFAULT = "nb-pill--blue";

/** Gercek API'de confidence alani yok — similarity'den turetiriz (bilgi
 *  eksikse fallback "low"). */
function confidenceOf(cand: CoverCandidate): "high" | "medium" | "low" {
  if (cand.confidence) return cand.confidence;
  const sim = cand.similarity ?? cand.similarity_score ?? 0;
  if (sim >= 0.8) return "high";
  if (sim >= 0.65) return "medium";
  return "low";
}

export default function CoverCandidateDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [candidate, setCandidate] = useState<CoverCandidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [isDemo, setIsDemo] = useState(false);
  const [status, setStatus] = useState<CoverCandidate["status"]>("pending");
  const [offerMsg, setOfferMsg] = useState<string | null>(null);

  useEffect(() => {
    const numId = parseInt(id, 10);
    if (!numId) {
      setLoading(false);
      return;
    }
    (async () => {
      const result = await getCoverCandidate(numId);
      if (result) {
        setCandidate(result);
        setStatus(result.status);
      } else {
        setCandidate({ ...DEMO_CANDIDATE, id: numId });
        setStatus("pending");
        setIsDemo(true);
      }
      setLoading(false);
    })();
  }, [id]);

  const numId = parseInt(id, 10) || DEMO_CANDIDATE.id || 0;
  const data = candidate ?? { ...DEMO_CANDIDATE, id: numId };
  const candidateId = data.id ?? numId;
  const original = data.original_profile ?? DEFAULT_PROFILE;
  const cover = data.candidate_profile ?? DEFAULT_PROFILE;
  const similarity = data.similarity ?? data.similarity_score ?? 0;
  const confidence = confidenceOf(data);
  const reasons = data.match_reasons ?? [];
  const confidenceLabel =
    confidence === "high"
      ? t.confidenceHigh
      : confidence === "medium"
      ? t.confidenceMedium
      : t.confidenceLow;

  async function handleReview(verdict: "approved" | "rejected") {
    setStatus(verdict);
    if (!isDemo) await reviewCandidate(candidateId, verdict);
  }

  async function handleLicense() {
    if (isDemo) {
      setOfferMsg(t.offerSent);
      return;
    }
    const { data: result } = await coverLicense(candidateId);
    if (result) setOfferMsg(t.offerSent);
  }

  return (
    <div className={styles.page}>
      <SiteHeader />

      <main className={styles.body}>
        {loading ? (
          <div className={styles.loading}>{t.loading}</div>
        ) : (
          <>
            <div className={styles.head}>
              <span className={`nb-pill ${CONFIDENCE_PILL[confidence] ?? CONFIDENCE_PILL_DEFAULT}`}>
                {t.simPrefix} {similarity.toFixed(2)} · {confidenceLabel}
              </span>
              <h1 className={`nb-h ${styles.headTitle}`}>{t.candidateTitle(String(candidateId))}</h1>
            </div>

            <div className={styles.compare}>
              <div className={styles.profile}>
                <h5 className={styles.profileTitle}>{t.originalLabel}</h5>
                <div className={styles.prow}>
                  <span>{t.bpm}</span>
                  <div className={styles.prowBar}>
                    <span
                      className={styles.prowBarFill}
                      style={{ width: `${(original.bpm / 144) * 100}%`, background: "var(--blue)" }}
                    />
                  </div>
                  <b>{original.bpm}</b>
                </div>
                <div className={styles.prow}>
                  <span>{t.energy}</span>
                  <div className={styles.prowBar}>
                    <span
                      className={styles.prowBarFill}
                      style={{ width: `${original.energy * 100}%`, background: "var(--blue)" }}
                    />
                  </div>
                  <b>{original.energy.toFixed(2)}</b>
                </div>
                <div className={styles.prow}>
                  <span>{t.brightness}</span>
                  <div className={styles.prowBar}>
                    <span
                      className={styles.prowBarFill}
                      style={{ width: `${original.brightness * 100}%`, background: "var(--blue)" }}
                    />
                  </div>
                  <b>{original.brightness.toFixed(2)}</b>
                </div>
                <div className={styles.prow}>
                  <span>{t.key}</span>
                  <div className={styles.prowBar}>
                    <span
                      className={styles.prowBarFill}
                      style={{ width: "70%", background: "var(--blue)" }}
                    />
                  </div>
                  <b>{original.key}</b>
                </div>
              </div>
              <div className={styles.vs}>≈</div>
              <div className={`${styles.profile} ${styles.profileCandidate}`}>
                <h5 className={styles.profileTitle} style={{ color: "var(--red)" }}>
                  {t.candidateLabel}
                </h5>
                <div className={styles.prow}>
                  <span>{t.bpm}</span>
                  <div className={styles.prowBar}>
                    <span
                      className={styles.prowBarFill}
                      style={{ width: `${(cover.bpm / 144) * 100}%`, background: "var(--red)" }}
                    />
                  </div>
                  <b>{cover.bpm}</b>
                </div>
                <div className={styles.prow}>
                  <span>{t.energy}</span>
                  <div className={styles.prowBar}>
                    <span
                      className={styles.prowBarFill}
                      style={{ width: `${cover.energy * 100}%`, background: "var(--red)" }}
                    />
                  </div>
                  <b>{cover.energy.toFixed(2)}</b>
                </div>
                <div className={styles.prow}>
                  <span>{t.brightness}</span>
                  <div className={styles.prowBar}>
                    <span
                      className={styles.prowBarFill}
                      style={{ width: `${cover.brightness * 100}%`, background: "var(--red)" }}
                    />
                  </div>
                  <b>{cover.brightness.toFixed(2)}</b>
                </div>
                <div className={styles.prow}>
                  <span>{t.key}</span>
                  <div className={styles.prowBar}>
                    <span
                      className={styles.prowBarFill}
                      style={{ width: "72%", background: "var(--red)" }}
                    />
                  </div>
                  <b>{cover.key}</b>
                </div>
              </div>
            </div>

            <div className={styles.signalGrid}>
              <div className={`nb-card ${styles.signal}`}>
                <h4>{t.reasonsTitle}</h4>
                <div className={styles.reasonChips}>
                  {reasons.map((reason, idx) => (
                    <span key={`${reason}-${idx}`} className={`nb-pill nb-pill--blue ${styles.miniPill}`}>
                      {reason}
                    </span>
                  ))}
                </div>
                <p>{data.match_notes ?? "—"}</p>
              </div>
              <div className={`nb-card ${styles.signal}`}>
                <h4>{t.licenseTitle}</h4>
                <div className={styles.offerVal}>${data.license_offer_usd ?? "—"}</div>
                <p>{t.licenseNote}</p>
                <button
                  type="button"
                  className={`nb-btn nb-btn--green ${styles.signalBtn}`}
                  onClick={handleLicense}
                >
                  {t.sendOffer}
                </button>
                {offerMsg && <p style={{ color: "#0a8f3c", fontWeight: 800 }}>{offerMsg}</p>}
              </div>
              <div className={`nb-card ${styles.signal}`}>
                <h4>{t.claimTitle}</h4>
                <p>{t.claimNote}</p>
                <button type="button" className={`nb-btn nb-btn--outline ${styles.signalBtn}`}>
                  {t.claimDoc}
                </button>
              </div>
            </div>

            <div className={styles.bottomActions}>
              <button
                type="button"
                className="nb-btn nb-btn--green"
                disabled={status !== "pending"}
                onClick={() => handleReview("approved")}
              >
                {t.approve}
              </button>
              <button
                type="button"
                className="nb-btn nb-btn--outline"
                disabled={status !== "pending"}
                onClick={() => handleReview("rejected")}
              >
                {t.reject}
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
