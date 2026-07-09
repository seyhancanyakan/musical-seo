"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getCoverReport,
  reviewCandidate,
  type CoverCandidate,
  type CoverHunt,
} from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";

const HIGH_CONFIDENCE_THRESHOLD = 0.8;
const REVENUE_PER_CANDIDATE_USD = 600;

const DEMO_HUNT: CoverHunt = {
  id: 9001,
  report_token: "HUNT-9K4E",
  original_query: "Selin Kaya - Yağmur Sonrası",
  candidates_found: 4,
  high_confidence: 2,
  medium_confidence: 1,
  estimated_unlicensed_revenue: "$2.400",
  candidates: [
    {
      id: 4471,
      hunt_id: 9001,
      title: "Yağmur Sonrası (Cover) — Akustik",
      channel: "@acoustic_covers_tr",
      source: "youtube",
      url: "https://youtube.com/watch?v=demo1",
      similarity: 0.91,
      match_reasons: ["ses profili çok yakın", "başlık/söz eşleşmesi"],
      status: "pending",
    },
    {
      id: 4472,
      hunt_id: 9001,
      title: "yağmur sonrası | speed up",
      channel: "tiktok sound",
      source: "tiktok",
      url: "https://tiktok.com/demo2",
      similarity: 0.86,
      match_reasons: ["ses profili çok yakın"],
      status: "pending",
    },
    {
      id: 4473,
      hunt_id: 9001,
      title: "Rain After (English version)",
      channel: "@indie_reworks",
      source: "youtube",
      url: "https://youtube.com/watch?v=demo3",
      similarity: 0.72,
      match_reasons: ["söz benzerliği tespit edildi"],
      status: "pending",
    },
    {
      id: 4474,
      hunt_id: 9001,
      title: "Yağmur — piano tribute",
      channel: "@piano_moods",
      source: "youtube",
      url: "https://youtube.com/watch?v=demo4",
      similarity: 0.58,
      match_reasons: ["başlık/söz eşleşmesi"],
      status: "pending",
    },
  ],
};

const T = {
  tr: {
    loading: "Rapor yükleniyor…",
    foundTitle: (n: number) => `${n} aday bulundu`,
    confidenceSummary: (high: number, medium: number) =>
      `${high} yüksek güven · ${medium} orta güven · doğrulama bekliyor`,
    highLabel: "Yüksek (>0.8)",
    lostRevenue: "Tahmini kayıp gelir",
    simLabel: "benzerlik",
    belowThreshold: "eşik altı",
    approve: "✓ Onayla",
    reject: "✕",
    verifyAll: "Tümünü doğrula →",
    exportCsv: "⬇ Aday CSV",
    emptyState:
      "0 aday bulundu — kaynak anahtarı yok (YouTube/Genius API) ya da henüz eşleşme yok.",
  },
  en: {
    loading: "Loading report…",
    foundTitle: (n: number) => `${n} candidates found`,
    confidenceSummary: (high: number, medium: number) =>
      `${high} high confidence · ${medium} medium confidence · awaiting review`,
    highLabel: "High (>0.8)",
    lostRevenue: "Est. lost revenue",
    simLabel: "similarity",
    belowThreshold: "below threshold",
    approve: "✓ Approve",
    reject: "✕",
    verifyAll: "Verify all →",
    exportCsv: "⬇ Candidate CSV",
    emptyState: "0 candidates found — no source key configured (YouTube/Genius) or no matches yet.",
  },
};

const SIM_THRESHOLD = 0.6;

function simOf(cand: CoverCandidate): number {
  return cand.similarity ?? cand.similarity_score ?? 0;
}

function simColor(similarity: number): string {
  if (similarity >= 0.8) return "var(--red)";
  if (similarity >= SIM_THRESHOLD) return "#ffb020";
  return "#888";
}

function formatUsd(amount: number): string {
  return `$${amount.toLocaleString("en-US").replace(/,/g, ".")}`;
}

export default function CoverHuntReportPage() {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [hunt, setHunt] = useState<CoverHunt | null>(null);
  const [candidates, setCandidates] = useState<CoverCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [isDemo, setIsDemo] = useState(false);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    (async () => {
      const huntResult = await getCoverReport(token);
      if (huntResult) {
        setHunt(huntResult);
        // GET /cover-hunt/report/{token} adaylari zaten govdede tasir —
        // ayri bir liste cagrisi gerekmez. Gercekten bos olabilir (API
        // anahtari yok) — bu durumda DEMO'ya duselim yerine bos hali gosteririz.
        setCandidates(huntResult.candidates ?? []);
      } else {
        setHunt({ ...DEMO_HUNT, report_token: token });
        setCandidates(DEMO_HUNT.candidates ?? []);
        setIsDemo(true);
      }
      setLoading(false);
    })();
  }, [token]);

  async function handleReview(id: number | undefined, verdict: "approved" | "rejected") {
    if (id == null) return;
    setCandidates((prev) =>
      prev.map((c) => (c.id === id ? { ...c, status: verdict } : c))
    );
    if (!isDemo) await reviewCandidate(id, verdict);
  }

  const data = hunt ?? { ...DEMO_HUNT, report_token: token || DEMO_HUNT.report_token };
  const list = candidates;

  const candidatesFound = data.candidates_found ?? list.length;
  const highConfidence =
    data.high_confidence ?? list.filter((c) => simOf(c) >= HIGH_CONFIDENCE_THRESHOLD).length;
  const mediumConfidence =
    data.medium_confidence ?? Math.max(list.length - highConfidence, 0);
  const revenue =
    data.estimated_unlicensed_revenue ?? formatUsd(list.length * REVENUE_PER_CANDIDATE_USD);

  return (
    <div className={styles.page}>

      <main className={styles.body}>
        {loading ? (
          <div className={styles.loading}>{t.loading}</div>
        ) : (
          <>
            <div className={styles.head}>
              <div>
                <span className="nb-pill nb-pill--green">
                  {data.report_token ?? token} · {data.original_query || "—"}
                </span>
                <h1 className={`nb-h ${styles.trackName}`}>
                  {t.foundTitle(candidatesFound)}
                </h1>
                <div className={styles.trackSub}>
                  {t.confidenceSummary(highConfidence, mediumConfidence)}
                </div>
              </div>
              <div className={styles.kpiRow}>
                <div className={`nb-card ${styles.kpi}`}>
                  <div className={styles.kpiVal} style={{ color: "var(--red)" }}>
                    {highConfidence}
                  </div>
                  <div className={styles.kpiLabel}>{t.highLabel}</div>
                </div>
                <div className={`nb-card ${styles.kpi}`}>
                  <div className={styles.kpiVal} style={{ color: "var(--green)" }}>
                    {revenue}
                  </div>
                  <div className={styles.kpiLabel}>{t.lostRevenue}</div>
                </div>
              </div>
            </div>

            {list.length === 0 ? (
              <div className="nb-card" style={{ padding: 20 }}>
                <p>{t.emptyState}</p>
              </div>
            ) : (
              <div className={styles.candList}>
                {list.map((cand) => {
                  const similarity = simOf(cand);
                  const isTiktok = (cand.source ?? "").toLowerCase().includes("tiktok");
                  const key = cand.id ?? `${cand.url}-${cand.title}`;
                  const reasons = cand.match_reasons ?? [];
                  const inner = (
                    <>
                      <b className={styles.candTitle}>{cand.title || "—"}</b>
                      <div className={styles.candMeta}>
                        {cand.channel || cand.source || "—"}
                      </div>
                      <div className={styles.reasons}>
                        {reasons.map((reason, idx) => (
                          <span key={`${reason}-${idx}`} className="nb-chip">
                            {reason}
                          </span>
                        ))}
                      </div>
                    </>
                  );
                  return (
                    <div
                      key={key}
                      className={`nb-card ${styles.cand} ${
                        similarity < SIM_THRESHOLD ? styles.candBelowThreshold : ""
                      }`}
                    >
                      {cand.id != null ? (
                        <Link href={`/cover-avcisi/aday/${cand.id}`} className={styles.thumb}>
                          {isTiktok ? "♪" : "▶"}
                        </Link>
                      ) : (
                        <span className={styles.thumb}>{isTiktok ? "♪" : "▶"}</span>
                      )}
                      {cand.id != null ? (
                        <Link
                          href={`/cover-avcisi/aday/${cand.id}`}
                          style={{ textDecoration: "none", color: "inherit" }}
                        >
                          {inner}
                        </Link>
                      ) : (
                        <div>{inner}</div>
                      )}
                      <div className={styles.simwrap}>
                        <div className={styles.sim} style={{ color: simColor(similarity) }}>
                          {similarity.toFixed(2)}
                        </div>
                        <div className={styles.simLabel}>
                          {similarity >= SIM_THRESHOLD ? t.simLabel : t.belowThreshold}
                        </div>
                        {similarity >= SIM_THRESHOLD && (
                          <div className={styles.candActions}>
                            <button
                              type="button"
                              className={`nb-pill nb-pill--green ${styles.miniPill}`}
                              onClick={() => handleReview(cand.id, "approved")}
                              disabled={cand.status !== "pending"}
                            >
                              {t.approve}
                            </button>
                            <button
                              type="button"
                              className={`nb-pill ${styles.miniPill}`}
                              style={{ background: "#fff" }}
                              onClick={() => handleReview(cand.id, "rejected")}
                              disabled={cand.status !== "pending"}
                            >
                              {t.reject}
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className={styles.bottomActions}>
              <button type="button" className="nb-btn nb-btn--green">
                {t.verifyAll}
              </button>
              <button type="button" className="nb-btn nb-btn--outline">
                {t.exportCsv}
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
