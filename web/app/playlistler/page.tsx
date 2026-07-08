"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  streamPitches,
  type CuratorContact,
  type PitchItem,
  type PitchStreamEvent,
} from "@/lib/api";
import { useLocale, pick, LangToggle } from "@/lib/locale";
import styles from "./page.module.css";

type Status = "pitched" | "accepted" | "rejected";
type Filter = "all" | Status;

type PitchCard = {
  key: string;
  title: string;
  trackCount: number;
  fans: number;
  artists: string[];
  extraCount: number;
  score: number;
  status: Status;
  message: string;
  url?: string;
  contact?: CuratorContact | null;
  /** Aday playlist onayli kuratorse dogrudan gonderim koprusu (kredi harcar). */
  curatorId?: number | null;
};

/** Demo kart meta bilgisi (locale-bagimsiz). Pitch mesaji T sozlugunden gelir. */
const DEMO_CARDS_META: Omit<PitchCard, "message">[] = [
  {
    key: "demo-turk",
    title: '"Türk"',
    trackCount: 47,
    fans: 0,
    artists: ["Duman", "Hayko Cepkin", "Mor ve Ötesi", "Şebnem Ferah"],
    extraCount: 3,
    score: 70,
    status: "pitched",
  },
  {
    key: "demo-brk-tr",
    title: '"BRK - TR"',
    trackCount: 62,
    fans: 1200,
    artists: ["Duman", "Athena", "maNga"],
    extraCount: 2,
    score: 70,
    status: "accepted",
  },
  {
    key: "demo-turkce-rock",
    title: '"Türkçe Rock"',
    trackCount: 31,
    fans: 340,
    artists: ["Kurban", "Pentagram"],
    extraCount: 1,
    score: 40,
    status: "rejected",
  },
];

const STAGE_PHASE: Record<string, number> = {
  resolve: 0,
  pool: 0,
  search: 1,
  scan: 1,
  skip: 1,
  audio: 2,
  audio_profile: 2,
  audio_fit: 2,
  mood: 2,
  match: 3,
  rank: 3,
  contact: 3,
};

type LogEntry = { id: number; text: string; kind: string };

type TrackProfile = { bpm: number; energy: number; instrumental: number };

function logLineClass(kind: string): string {
  if (kind === "match") return styles.logMatch;
  if (kind === "skip") return styles.logSkip;
  if (kind.startsWith("audio") || kind === "mood") return styles.logAudio;
  return "";
}

const T = {
  tr: {
    nav: [
      { href: "/karne", label: "Karne", icon: "📊" },
      { href: "/playlistler", label: "Playlistler", icon: "🎧" },
      { href: "/kanit", label: "Kanıt", icon: "✅" },
      { href: "/curator/inbox", label: "Curator Kutusu", icon: "📥" },
    ],
    userChipSuffix: "— Sanatçı Paneli",
    pageTitle: "Playlist Eşleştirme & Pitch",
    searchPlaceholder: "Sanatçı veya şarkı adı ara...",
    searchAria: "Sanatçı veya şarkı adı ara",
    analyzing: "Analiz ediliyor...",
    submit: "Playlist Bul",
    phases: ["Çözümleme", "Tarama", "Ses Analizi", "Skorlama"],
    bpmText: (v: number) => `♩ ${v} BPM`,
    energyText: (v: number) => `⚡ Enerji %${v}`,
    instrumentalText: (v: number) => `🎹 Enstrümantal %${v}`,
    apiFailedPrefix: "Eşleşme bulunamadı ya da API'ye ulaşılamadı. Şarkıyı ",
    apiFailedStrong: '"Sanatçı - Şarkı"',
    apiFailedSuffix: " formatında dene (ör. Duman - Senden Daha Güzel).",
    filters: [
      { key: "all" as Filter, label: "Tümü" },
      { key: "pitched" as Filter, label: "Pitched" },
      { key: "accepted" as Filter, label: "Accepted" },
      { key: "rejected" as Filter, label: "Rejected" },
    ],
    emptyIdle: "Şarkını yukarıdan ara → uygun playlist'ler burada çıksın.",
    emptyFiltered: "Bu filtrede playlist bulunamadı.",
    trackCountLabel: "parça",
    fanLabel: "fan",
    numberLocale: "tr-TR",
    openLink: "Aç ↗",
    platformSendBtn: "🎯 Platformda — Gönder (kredi ile)",
    inviteBtn: "➕ Platforma davet et",
    inviteSentBtn: "✓ Davet mesajı kopyalandı",
    sentStatus: "Gönderildi",
    pitchPreviewTitle: "Pitch Mesajı Önizleme",
    pitchMetaText: (title: string) => `${title} için hazırlanan mesaj`,
    copied: "Kopyalandı!",
    copy: "Kopyala",
    markSent: "Gönderildi İşaretle",
    sentNote: "✓ Gönderildi olarak işaretlendi.",
    noSelection: "Önizlemek için soldan bir playlist seç.",
    inviteText: (title: string, origin: string) =>
      `Merhaba! ${title} listeni Songdeck curator ağına davet etmek istiyoruz. ` +
      `Sanatçılardan doğrudan, sana uygun şarkı gönderimi alırsın; kabul/ret tek tık. ` +
      `Başvuru: ${origin}/curator/basvuru`,
    demoMessages: [
      'Merhaba, "Türk" listende Duman, Hayko Cepkin, Mor ve Ötesi gibi isimlere yer veriyorsun; gerçekten tutarlı bir seçki olmuş. Ben Duman. Yeni şarkım "Senden Daha Güzel" aynı damardan besleniyor ve listenle örtüşen bir dinleyici kitlesine hitap ediyor. İncelemene minnettar olurum.',
      'Merhaba, "BRK - TR" listende Duman, Athena ve maNga gibi isimlerle güçlü bir Türkçe rock seçkisi kurmuşsun. Ben Duman. Yeni şarkım "Senden Daha Güzel" listenin enerjisiyle birebir örtüşüyor. Değerlendirmeni rica ederim.',
      'Merhaba, "Türkçe Rock" listende Kurban ve Pentagram gibi isimlere yer veriyorsun. Ben Duman. Yeni şarkım "Senden Daha Güzel" listenin tarzına yakın bir seste. İncelemene minnettar olurum.',
    ],
  },
  en: {
    nav: [
      { href: "/karne", label: "Scorecard", icon: "📊" },
      { href: "/playlistler", label: "Playlists", icon: "🎧" },
      { href: "/kanit", label: "Proof", icon: "✅" },
      { href: "/curator/inbox", label: "Curator Inbox", icon: "📥" },
    ],
    userChipSuffix: "— Artist Panel",
    pageTitle: "Playlist Matching & Pitch",
    searchPlaceholder: "Search artist or song name...",
    searchAria: "Search artist or song name",
    analyzing: "Analyzing...",
    submit: "Find Playlists",
    phases: ["Resolving", "Scanning", "Audio Analysis", "Scoring"],
    bpmText: (v: number) => `♩ ${v} BPM`,
    energyText: (v: number) => `⚡ Energy ${v}%`,
    instrumentalText: (v: number) => `🎹 Instrumental ${v}%`,
    apiFailedPrefix: "No match found or the API is unreachable. Try the song in ",
    apiFailedStrong: '"Artist - Song"',
    apiFailedSuffix: " format (e.g. Duman - Senden Daha Güzel).",
    filters: [
      { key: "all" as Filter, label: "All" },
      { key: "pitched" as Filter, label: "Pitched" },
      { key: "accepted" as Filter, label: "Accepted" },
      { key: "rejected" as Filter, label: "Rejected" },
    ],
    emptyIdle: "Search your song above → matching playlists show up here.",
    emptyFiltered: "No playlists found in this filter.",
    trackCountLabel: "tracks",
    fanLabel: "fans",
    numberLocale: "en-US",
    openLink: "Open ↗",
    platformSendBtn: "🎯 On Platform — Send (uses credit)",
    inviteBtn: "➕ Invite to platform",
    inviteSentBtn: "✓ Invite message copied",
    sentStatus: "Sent",
    pitchPreviewTitle: "Pitch Message Preview",
    pitchMetaText: (title: string) => `Message prepared for ${title}`,
    copied: "Copied!",
    copy: "Copy",
    markSent: "Mark as Sent",
    sentNote: "✓ Marked as sent.",
    noSelection: "Select a playlist on the left to preview.",
    inviteText: (title: string, origin: string) =>
      `Hi! We'd like to invite your ${title} playlist to the Songdeck curator network. ` +
      `You'll get song submissions directly from artists tailored to your list; accept/reject with one tap. ` +
      `Apply: ${origin}/curator/basvuru`,
    demoMessages: [
      'Hi, your "Türk" playlist features names like Duman, Hayko Cepkin, and Mor ve Ötesi — it\'s a genuinely coherent selection. I\'m Duman. My new song "Senden Daha Güzel" draws from the same vein and speaks to a listener base that overlaps with your playlist. I\'d be grateful if you gave it a listen.',
      'Hi, your "BRK - TR" playlist builds a strong Turkish rock selection with names like Duman, Athena, and maNga. I\'m Duman. My new song "Senden Daha Güzel" matches your playlist\'s energy exactly. I\'d appreciate you considering it.',
      'Hi, your "Türkçe Rock" playlist features names like Kurban and Pentagram. I\'m Duman. My new song "Senden Daha Güzel" has a sound close to your playlist\'s style. I\'d be grateful if you gave it a listen.',
    ],
  },
};

function toCards(pitches: PitchItem[]): PitchCard[] {
  return pitches.map((p, i) => {
    const allArtists = p.playlist.matched_artists ?? [];
    return {
      key: `${p.playlist.source}-${p.playlist.playlist_id}-${i}`,
      title: `"${p.playlist.title}"`,
      trackCount: p.playlist.track_count,
      fans: p.playlist.fans,
      artists: allArtists.slice(0, 4),
      extraCount: Math.max(0, allArtists.length - 4),
      score: p.playlist.score,
      status: "pitched",
      message: p.message,
      url: p.playlist.url,
      contact: p.contact ?? null,
      curatorId: p.curator_id ?? null,
    };
  });
}

function statusPillClass(status: Status): string {
  if (status === "accepted") return styles.statusAccepted;
  if (status === "rejected") return styles.statusRejected;
  return styles.statusPitched;
}

function statusLabel(status: Status): string {
  if (status === "accepted") return "Accepted";
  if (status === "rejected") return "Rejected";
  return "Pitched";
}

export default function PlaylistlerPage() {
  const { locale } = useLocale();
  const t = pick(T, locale);
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [cards, setCards] = useState<PitchCard[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [apiFailed, setApiFailed] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [sentKeys, setSentKeys] = useState<Record<string, boolean>>({});
  const [invitedKeys, setInvitedKeys] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState(false);

  // Canli analiz VFX durumu
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [activePhase, setActivePhase] = useState(0);
  const [visitedPhases, setVisitedPhases] = useState<number[]>([]);
  const [profile, setProfile] = useState<TrackProfile | null>(null);
  const stopStreamRef = useRef<(() => void) | null>(null);
  const logIdRef = useRef(0);

  useEffect(() => () => stopStreamRef.current?.(), []);

  const filteredCards = useMemo(
    () => (filter === "all" ? cards : cards.filter((c) => c.status === filter)),
    [cards, filter]
  );

  const selected = cards.find((c) => c.key === selectedKey) ?? cards[0] ?? null;

  function handleStreamEvent(ev: PitchStreamEvent) {
    if (ev.stage === "done") {
      setLoading(false);
      const pitches = ev.data?.pitches ?? [];
      if (pitches.length === 0) {
        // Bos = eslesme yok. Demo'ya DUSME — net bos durum goster.
        setApiFailed(true);
        setCards([]);
        setSelectedKey("");
        setFilter("all");
        return;
      }
      const liveCards = toCards(pitches);
      setApiFailed(false);
      setCards(liveCards);
      setSelectedKey(liveCards[0]?.key ?? "");
      setFilter("all");
      return;
    }
    if (ev.stage === "error") {
      setLoading(false);
      setApiFailed(true);
      return;
    }

    if (ev.stage === "audio_profile" && ev.data) {
      setProfile({
        bpm: ev.data.bpm ?? 0,
        energy: ev.data.energy ?? 0,
        instrumental: ev.data.instrumental ?? 0,
      });
    }
    const phase = STAGE_PHASE[ev.stage];
    if (phase !== undefined) {
      setActivePhase(phase);
      setVisitedPhases((v) => (v.includes(phase) ? v : [...v, phase]));
    }
    logIdRef.current += 1;
    const entry: LogEntry = { id: logIdRef.current, text: ev.msg, kind: ev.stage };
    setLogs((prev) => [entry, ...prev].slice(0, 8));
  }

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q || loading) return;

    setLoading(true);
    setCopied(false);
    setHasSearched(true);
    setApiFailed(false);
    setCards([]);
    setSelectedKey("");
    setLogs([]);
    setVisitedPhases([]);
    setActivePhase(0);
    setProfile(null);

    stopStreamRef.current?.();
    stopStreamRef.current = streamPitches(q, 10, handleStreamEvent);
  }

  function handleSelect(key: string) {
    setSelectedKey(key);
    setCopied(false);
  }

  async function handleCopy() {
    if (!selected) return;
    try {
      await navigator.clipboard.writeText(selected.message);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // pano erisimi reddedildiyse sessizce yut — kritik olmayan yardimci eylem
    }
  }

  function handleMarkSent() {
    if (!selected) return;
    setSentKeys((prev) => ({ ...prev, [selected.key]: true }));
  }

  async function handleInvite(card: PitchCard) {
    // Iletisimi olmayan curator'a platform daveti — mesaj panoya kopyalanir,
    // sanatci Spotify/Deezer uzerinden (takip/yorum) iletebilir.
    const inviteText = t.inviteText(card.title, window.location.origin);
    try {
      await navigator.clipboard.writeText(inviteText);
      setInvitedKeys((prev) => ({ ...prev, [card.key]: true }));
      setTimeout(
        () => setInvitedKeys((prev) => ({ ...prev, [card.key]: false })),
        2500
      );
    } catch {
      // pano reddedilirse sessiz gec — kritik olmayan yardimci eylem
    }
  }

  return (
    <div className={styles.shell}>
      <div className={styles.topbar}>
        <Link href="/" className={styles.logo}>Songdeck</Link>
        <div className={styles.userChip}>👤 Duman {t.userChipSuffix}</div>
        <LangToggle />
      </div>

      <div className={styles.sidebar}>
        {t.nav.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={
              link.href === "/playlistler"
                ? `${styles.sidebarLink} ${styles.sidebarLinkActive}`
                : styles.sidebarLink
            }
          >
            {link.icon} {link.label}
          </Link>
        ))}
      </div>

      <main className={styles.main}>
        <h1 className={`nb-h ${styles.pageTitle}`}>{t.pageTitle}</h1>

        <form className={styles.searchRow} onSubmit={handleSearch}>
          <input
            className="nb-input"
            type="text"
            placeholder={t.searchPlaceholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label={t.searchAria}
          />
          <button
            type="submit"
            className={`nb-btn nb-btn--purple ${styles.searchBtn}`}
            disabled={loading}
          >
            {loading ? t.analyzing : t.submit}
          </button>
        </form>

        {loading && (
          <div className={styles.analysisPanel} aria-live="polite">
            <div className={styles.stageRail}>
              {t.phases.map((phaseLabel, i) => (
                <span
                  key={phaseLabel}
                  className={`${styles.stageChip} ${
                    i === activePhase
                      ? styles.stageChipActive
                      : visitedPhases.includes(i)
                        ? styles.stageChipDone
                        : ""
                  }`}
                >
                  {phaseLabel}
                </span>
              ))}
            </div>

            <div className={styles.eqRow} aria-hidden="true">
              {Array.from({ length: 10 }).map((_, i) => (
                <div
                  key={i}
                  className={`${styles.eqBar} ${
                    activePhase === 2 ? styles.eqBarAudio : ""
                  }`}
                />
              ))}
            </div>

            {profile && (
              <div className={styles.profileChips}>
                <span className={styles.profileChip}>{t.bpmText(profile.bpm)}</span>
                <span className={styles.profileChip}>
                  {t.energyText(Math.round(profile.energy * 100))}
                </span>
                <span className={styles.profileChip}>
                  {t.instrumentalText(Math.round(profile.instrumental * 100))}
                </span>
              </div>
            )}

            <div className={styles.logFeed}>
              {logs.map((l) => (
                <div key={l.id} className={`${styles.logLine} ${logLineClass(l.kind)}`}>
                  ▸ {l.text}
                </div>
              ))}
            </div>
          </div>
        )}

        {apiFailed && (
          <div className={styles.banner} role="status">
            {t.apiFailedPrefix}
            <strong>{t.apiFailedStrong}</strong>
            {t.apiFailedSuffix}
          </div>
        )}

        <div className={styles.tabs}>
          {t.filters.map((f) => (
            <button
              key={f.key}
              type="button"
              className={`${styles.wristband} ${filter === f.key ? styles.wristbandOn : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className={styles.layout}>
          <div className={styles.plList}>
            {filteredCards.length === 0 && (
              <div className={styles.emptyState}>
                {!hasSearched ? t.emptyIdle : t.emptyFiltered}
              </div>
            )}

            {filteredCards.map((card) => (
              <div
                key={card.key}
                role="button"
                tabIndex={0}
                className={`${styles.plCard} ${
                  card.key === selectedKey ? styles.plCardSelected : ""
                }`}
                onClick={() => handleSelect(card.key)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handleSelect(card.key);
                  }
                }}
                aria-pressed={card.key === selectedKey}
              >
                <div className={styles.plTop}>
                  <div>
                    <div className={styles.plName}>{card.title}</div>
                    <div className={styles.plMeta}>
                      {card.trackCount} {t.trackCountLabel} ·{" "}
                      {card.fans.toLocaleString(t.numberLocale)} {t.fanLabel}
                    </div>
                  </div>
                  <div className={styles.plTopRight}>
                    <div className={styles.scoreBadge}>{card.score}</div>
                    {card.url && (
                      <a
                        className={styles.openLink}
                        href={card.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {t.openLink}
                      </a>
                    )}
                  </div>
                </div>

                <div className={styles.stickerRow}>
                  {card.artists.map((artist) => (
                    <span key={artist} className={styles.sticker}>
                      {artist}
                    </span>
                  ))}
                  {card.extraCount > 0 && (
                    <span className={`${styles.sticker} ${styles.stickerMore}`}>
                      +{card.extraCount}
                    </span>
                  )}
                </div>

                <div className={styles.contactRow}>
                  {card.curatorId != null && (
                    <button
                      type="button"
                      className={styles.platformBtn}
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/gonder?curator=${card.curatorId}`);
                      }}
                    >
                      {t.platformSendBtn}
                    </button>
                  )}
                  {card.contact ? (
                    <>
                      {card.contact.emails.slice(0, 1).map((email) => (
                        <a
                          key={email}
                          className={styles.contactLink}
                          href={`mailto:${email}`}
                          onClick={(e) => e.stopPropagation()}
                        >
                          📧 {email}
                        </a>
                      ))}
                      {card.contact.instagram.slice(0, 1).map((handle) => (
                        <a
                          key={handle}
                          className={styles.contactLink}
                          href={`https://instagram.com/${handle}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                        >
                          📸 @{handle}
                        </a>
                      ))}
                      {card.contact.links.slice(0, 1).map((link) => (
                        <a
                          key={link}
                          className={styles.contactLink}
                          href={link}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                        >
                          🔗 {link.replace(/^https?:\/\/(www\.)?/, "").slice(0, 28)}
                        </a>
                      ))}
                    </>
                  ) : (
                    card.curatorId == null && (
                      <button
                        type="button"
                        className={styles.inviteBtn}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleInvite(card);
                        }}
                      >
                        {invitedKeys[card.key] ? t.inviteSentBtn : t.inviteBtn}
                      </button>
                    )
                  )}
                </div>

                <div className={styles.statusRow}>
                  <span className={`${styles.statusPill} ${statusPillClass(card.status)}`}>
                    {sentKeys[card.key] && card.status === "pitched"
                      ? t.sentStatus
                      : statusLabel(card.status)}
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className={styles.pitchPanel}>
            <h3 className="nb-h">{t.pitchPreviewTitle}</h3>
            {selected ? (
              <>
                <div className={styles.pitchMeta}>{t.pitchMetaText(selected.title)}</div>
                <div className={styles.pitchBox}>{selected.message}</div>
                <div className={styles.pitchActions}>
                  <button type="button" className={styles.actionBtn} onClick={handleCopy}>
                    {copied ? t.copied : t.copy}
                  </button>
                  <button
                    type="button"
                    className={`${styles.actionBtn} ${styles.actionPrimary}`}
                    onClick={handleMarkSent}
                  >
                    {t.markSent}
                  </button>
                </div>
                {sentKeys[selected.key] && (
                  <div className={styles.sentNote}>{t.sentNote}</div>
                )}
              </>
            ) : (
              <div className={styles.pitchMeta}>{t.noSelection}</div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
