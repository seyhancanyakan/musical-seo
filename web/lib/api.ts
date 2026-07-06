/** FastAPI istemcisi — tum sayfalar bu yardimcilari kullanir.
 *  Hata durumunda null doner; sayfalar demo veriye duser. */

const API =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100";

async function j<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(`${API}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export type AuditResult = {
  query: string;
  resolved_artist: string;
  resolved_title: string;
  created_at: string;
  sources: {
    source: string;
    found: boolean;
    title: string | null;
    artist: string | null;
    isrc: string | null;
    release_date: string | null;
    popularity: number | null;
    url: string | null;
    note: string | null;
  }[];
  keywords: {
    query: string;
    engine: string;
    suggestions: string[];
    artist_present: boolean;
    track_present: boolean;
  }[];
  findings: {
    severity: "critical" | "warn" | "info" | "ok";
    category: string;
    message: string;
    action: string | null;
  }[];
  subscores: Record<string, number>;
  score: number;
};

export type PlaylistMatch = {
  source: string;
  playlist_id: string;
  title: string;
  url: string;
  fans: number;
  track_count: number;
  matched_artists: string[];
  contains_track: boolean;
  score: number;
  owner_name: string | null;
  owner_id: string | null;
};

export type CuratorStatus = "lead" | "pending" | "approved" | "rejected";

/** Kurator/profesyonel turu — playlist disi turler linksiz basvurur. */
export type CuratorType =
  | "playlist" | "radyo" | "medya" | "label" | "menajer"
  | "booker" | "dj" | "mentor" | "sync";

/** Kurator performans metrikleri (oranlar 0-100; hic veri yoksa null). */
export type CuratorStats = {
  total_submissions: number;
  responded: number;
  accepted: number;
  response_rate: number | null;
  success_rate: number | null;
  opportunity_rate: number | null;
};

/** Reach-bazli fiyat kademesi: gonderim maliyeti kademeye gore artar. */
export type CuratorTier = "bronze" | "silver" | "gold" | "platinum";

export type Curator = {
  id: number;
  created_at: string;
  name: string;
  email: string;
  deezer_playlist_id: string;
  playlist_title: string;
  playlist_url: string;
  fans: number;
  track_count: number;
  diversity: number;
  quality_score: number;
  status: CuratorStatus;
  // Fiyatlandirma + sponsorluk (public katalog DTO'su)
  tier?: CuratorTier;
  base_cost?: number;
  sponsored?: boolean;
  // İletişim kaynağı — nereden bulundu (manuel doğrulama için).
  contact_source?: string | null;
  source_url?: string | null;
  contact_confidence?: number | null;
  // Playlist sahiplik dogrulamasi (SubmitHub yontemi: kod aciklamaya eklenir)
  ownership_verified?: number;
  verify_code?: string | null;
  // Kurator turu + performans metrikleri (public DTO her zaman doner)
  curator_type?: CuratorType;
  stats?: CuratorStats;
};

/** Firsat sistemi: primary = somut sonuc, secondary = dolayli deger. */
export type OpportunityLevel = "primary" | "secondary";

export type Submission = {
  id: number;
  created_at: string;
  artist: string;
  title: string;
  track_url: string | null;
  curator_id: number;
  message: string;
  status: "pending" | "accepted" | "rejected" | "expired";
  feedback: string | null;
  deadline: string;
  placement_verified: number;
  opportunity_level?: OpportunityLevel | null;
  opportunity_kind?: string | null;
  // Fiyat + eklentiler
  cost_credits?: number;
  guaranteed?: number;      // 1: SLA kacarsa 2x iade sozu
  priority?: number;        // 1: one cikan (48s SLA, inbox ustu)
  opened_at?: string | null;
  certificate_token?: string | null;
  readiness_score?: number | null;
};

export const getAudit = (query: string) =>
  j<AuditResult>(`/audit?query=${encodeURIComponent(query)}`);

export const getHistory = (query: string) =>
  j<{ created_at: string; score: number; spotify_popularity: number | null }[]>(
    `/audit/history?query=${encodeURIComponent(query)}`
  );

export const getPlaylists = (query: string, limit = 10) =>
  j<PlaylistMatch[]>(
    `/playlists?query=${encodeURIComponent(query)}&limit=${limit}`
  );

/** Curator'in KENDI yayinladigi iletisim bilgileri (playlist aciklamalarindan). */
export type CuratorContact = {
  emails: string[];
  instagram: string[];
  links: string[];
  source_hint?: string | null;
};

export type PitchItem = {
  playlist: PlaylistMatch;
  message: string;
  contact?: CuratorContact | null;
  /** Aday playlist onayli kuratorse dogrudan gonderim koprusu (kredi harcar). */
  curator_id?: number | null;
};

export const generatePitches = (query: string, limit = 5) =>
  j<PitchItem[]>(`/pitch/generate`, {
    method: "POST",
    body: JSON.stringify({ query, limit }),
  });

/** SSE canli asama olayi — /pitch/stream. `done.data.pitches` sonucu tasir. */
export type PitchStreamEvent = {
  stage:
    | "resolve" | "pool" | "search" | "scan" | "skip"
    | "audio" | "audio_profile" | "audio_fit" | "mood"
    | "match" | "rank" | "contact" | "done" | "error";
  msg: string;
  data?: {
    pitches?: PitchItem[];
    bpm?: number;
    energy?: number;
    instrumental?: number;
    fit?: number;
    names?: string[];
    terms?: string[];
    fans?: number;
  } | null;
};

/** Pitch uretimini canli izle (EventSource). Kapatma fonksiyonu dondurur.
 *  'done' veya 'error' geldiginde baglanti otomatik kapanir. */
export function streamPitches(
  query: string,
  limit: number,
  onEvent: (ev: PitchStreamEvent) => void
): () => void {
  const es = new EventSource(
    `${API}/pitch/stream?query=${encodeURIComponent(query)}&limit=${limit}`
  );
  es.onmessage = (e) => {
    let ev: PitchStreamEvent | null = null;
    try {
      ev = JSON.parse(e.data) as PitchStreamEvent;
    } catch {
      return;
    }
    if (ev.stage === "done" || ev.stage === "error") es.close();
    onEvent(ev);
  };
  es.onerror = () => {
    // Sunucu akisi kapatinca da tetiklenir; acik baglantiyi kapat, hata bildir.
    if (es.readyState !== EventSource.CLOSED) es.close();
    onEvent({ stage: "error", msg: "Bağlantı koptu" });
  };
  return () => es.close();
}

export const applyCurator = (payload: {
  name: string;
  email: string;
  playlist_url: string;
  curator_type?: CuratorType;
}) => j<Curator>(`/curators/apply`, { method: "POST", body: JSON.stringify(payload) });

export const listCurators = () => j<Curator[]>(`/curators`);

/** Admin cagrilari X-Admin-Key ister (server-side yetki). Anahtar admin
 *  panelinde girilir, localStorage'da tutulur — public build'e gomulmez. */
const ADMIN_KEY_STORAGE = "muzikseo_admin_key";

export const getAdminKey = (): string =>
  typeof window === "undefined" ? "" : localStorage.getItem(ADMIN_KEY_STORAGE) ?? "";

export const setAdminKey = (key: string): void => {
  if (typeof window !== "undefined") localStorage.setItem(ADMIN_KEY_STORAGE, key);
};

const adminHeaders = (): Record<string, string> => ({ "X-Admin-Key": getAdminKey() });

/** Admin: tüm curator'lar — tam kayıt (e-posta + iletişim kaynağı dahil). */
export const listAllCurators = () =>
  j<Curator[]>(`/admin/curators`, { headers: adminHeaders() });

/** Admin: bir curator'ın başvuru durumunu değiştir. */
export const setCuratorStatus = (id: number, status: CuratorStatus) =>
  j<Curator>(`/curators/${id}/status`, {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify({ status }),
  });

/* --- Hesap / kredi / cekirdek dongu ------------------------------------- */

export type User = {
  id: number;
  created_at: string;
  email: string;
  role: "artist" | "curator" | "admin";
  name: string;
  curator_id: number | null;
  credits: number;
  pro_until?: string | null;       // Artist Pro bitis tarihi
  referral_code?: string | null;
  leaderboard_opt_in?: number;
};

export type WalletTransaction = {
  id: number;
  created_at: string;
  delta: number;
  reason: string;
  submission_id: number | null;
};

export type Earnings = {
  items: {
    id: number;
    created_at: string;
    submission_id: number;
    amount_usd: number;
    status: "accrued" | "paid";
  }[];
  total_usd: number;
  pending_usd: number;
};

const TOKEN_KEY = "muzikseo_token";

export const getToken = (): string | null =>
  typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);

export const setToken = (token: string | null): void => {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};

const authHeaders = (): Record<string, string> => {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const authRegister = (payload: {
  email: string;
  password: string;
  name: string;
  role: "artist" | "curator";
  playlist_url?: string;
  curator_type?: CuratorType;
  referral_code?: string;
}) =>
  j<{ user: User; token: string }>(`/auth/register`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const authLogin = (email: string, password: string) =>
  j<{ user: User; token: string }>(`/auth/login`, {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

export const getMe = () =>
  j<{ user: User; transactions: WalletTransaction[]; earnings?: Earnings }>(
    `/me`,
    { headers: authHeaders() }
  );

export const submitToCurator = (
  artist: string,
  title: string,
  curatorId: number,
  opts?: { guaranteed?: boolean; priority?: boolean }
) =>
  j<Submission>(`/me/submissions`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      artist,
      title,
      curator_id: curatorId,
      guaranteed: opts?.guaranteed ?? false,
      priority: opts?.priority ?? false,
    }),
  });

export const myInbox = () =>
  j<Submission[]>(`/me/inbox`, { headers: authHeaders() });

export const myRespond = (
  id: number,
  action: "accepted" | "rejected",
  feedback = "",
  opportunity?: { level: OpportunityLevel; kind: string }
) =>
  j<Submission>(`/me/submissions/${id}/respond`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      action,
      feedback,
      opportunity_level: opportunity?.level ?? null,
      opportunity_kind: opportunity?.kind ?? null,
    }),
  });

export const myEarnings = () =>
  j<Earnings>(`/me/earnings`, { headers: authHeaders() });

/** Sanatci kampanya gecmisi (durum + feedback + SLA). */
export const mySubmissions = () =>
  j<Submission[]>(`/me/submissions`, { headers: authHeaders() });

/** Kuratorun bagli playlist kaydi (sahiplik durumu dahil, e-postasiz). */
export const myCurator = () =>
  j<Curator & { ownership_verified?: number; verify_code?: string | null }>(
    `/me/curator`,
    { headers: authHeaders() }
  );

export const linkCuratorPlaylist = (playlistUrl: string) =>
  j<Curator>(`/me/curator/link`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ playlist_url: playlistUrl }),
  });

export const verifyOwnershipStart = () =>
  j<{ code: string; instructions: string }>(`/me/curator/verify/start`, {
    method: "POST",
    headers: authHeaders(),
  });

export const verifyOwnershipCheck = () =>
  j<Curator>(`/me/curator/verify/check`, {
    method: "POST",
    headers: authHeaders(),
  });

/* --- Gelir ozellikleri: paketler, pro, referans, premium urunler ---------- */

export type CreditPackage = {
  key: string;
  credits: number;
  price_try: number;
  label: string;
};

export const getPackages = () =>
  j<{
    packages: CreditPackage[];
    pro: { price_try: number; monthly_credits: number; sla_hours: number };
  }>(`/packages`);

/** Paket talebi: odeme pilotta manuel (havale/Papara) -> admin krediyi yukler. */
export const requestPackage = (packageKey: string) =>
  j<{ id: number; status: string; credits: number; price_try: number }>(
    `/me/packages/request`,
    {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ package_key: packageKey }),
    }
  );

export const getReferral = () =>
  j<{ code: string; bonus_credits: number; note: string }>(`/me/referral`, {
    headers: authHeaders(),
  });

export type Notification = {
  id: number;
  created_at: string;
  kind: string;
  message: string;
  read: number;
};

export const getNotifications = (unreadOnly = false) =>
  j<Notification[]>(`/me/notifications?unread_only=${unreadOnly}`, {
    headers: authHeaders(),
  });

export const markNotificationsRead = () =>
  j<{ marked: number }>(`/me/notifications/read`, {
    method: "POST",
    headers: authHeaders(),
  });

/* --- Paylasilabilir karne + lig + kurator vitrini -------------------------- */

export type PublicReport = {
  token: string;
  artist: string;
  title: string;
  score: number;
  created_at: string;
  finding_counts: Record<string, number>;
  subscores: Record<string, number>;
  locked: boolean;
};

export const shareKarne = (query: string, leaderboardOptIn?: boolean) =>
  j<{ token: string; url: string }>(`/me/karne/share`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ query, leaderboard_opt_in: leaderboardOptIn ?? null }),
  });

export const getPublicKarne = (token: string) =>
  j<PublicReport>(`/public/karne/${encodeURIComponent(token)}`);

export type LeaderboardEntry = {
  artist: string;
  title: string;
  score: number;
  created_at: string;
  token: string;
};

export const getLeaderboard = (limit = 20) =>
  j<LeaderboardEntry[]>(`/public/leaderboard?limit=${limit}`);

export const setLeaderboardOptIn = (optIn: boolean) =>
  j<{ opt_in: boolean }>(`/me/leaderboard-opt-in`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ opt_in: optIn }),
  });

export type CuratorProfile = {
  id: number;
  name: string;
  curator_type: CuratorType;
  playlist_title: string;
  playlist_url: string;
  fans: number;
  track_count: number;
  quality_score: number;
  ownership_verified: number;
  verified_placements: number;
  sponsored: boolean;
  stats: Partial<CuratorStats>;
};

export const getCuratorProfile = (id: number) =>
  j<CuratorProfile>(`/public/curators/${id}`);

/* --- Dinleme kapisi + yerlesim kaniti urunleri ------------------------------ */

/** Kurator gonderimi acti: dinleme sayaci baslar (yanit kapisi). */
export const openSubmission = (id: number) =>
  j<{ opened_at: string; listen_gate_seconds: number }>(
    `/me/submissions/${id}/open`,
    { method: "POST", headers: authHeaders() }
  );

/** Sanatci self-servis yerlesim dogrulama (admin beklemeden). */
export const verifyPlacementSelf = (id: number) =>
  j<Submission & { placement_checked?: boolean }>(
    `/me/submissions/${id}/verify-placement`,
    { method: "POST", headers: authHeaders() }
  );

/** Auth gerektiren HTML/SVG iceriklerini yeni sekmede acmak icin blob URL. */
async function fetchBlobUrl(path: string): Promise<string | null> {
  try {
    const res = await fetch(`${API}${path}`, { headers: authHeaders() });
    if (!res.ok) return null;
    return URL.createObjectURL(await res.blob());
  } catch {
    return null;
  }
}

export const openCertificate = (id: number) =>
  fetchBlobUrl(`/me/submissions/${id}/certificate`);

export const openShareCard = (id: number) =>
  fetchBlobUrl(`/me/submissions/${id}/share-card`);

export const openEpk = () => fetchBlobUrl(`/me/epk`);

export type ImpactReport = {
  submission_id: number;
  artist: string;
  title: string;
  placement_verified: boolean;
  pivot: string;
  data_points: number;
  before: { score: number | null; spotify_popularity: number | null };
  after: { score: number | null; spotify_popularity: number | null };
  score_delta: number | null;
  premium: boolean;
};

export const getImpact = (id: number, premiumReport = false) =>
  j<ImpactReport>(
    `/me/submissions/${id}/impact?premium_report=${premiumReport}`,
    { headers: authHeaders() }
  );

/* --- Kariyer panosu + hazirlik + otopilot + takvim --------------------------- */

export type Dashboard = {
  funnel: Record<string, number>;
  credits_spent: number;
  tracks: {
    artist: string;
    title: string;
    latest_score: number | null;
    trend: { created_at: string; score: number | null }[];
  }[];
  pro: boolean;
  cohort: { avg_score: number | null; artists: number } | null;
  notifications: Notification[];
};

export const getDashboard = () =>
  j<Dashboard>(`/me/dashboard`, { headers: authHeaders() });

export type Readiness = {
  score: number;
  ready: boolean;
  threshold: number;
  checklist: { severity: string; message: string; action: string | null }[];
};

export const getReadiness = (query: string) =>
  j<Readiness>(`/me/readiness?query=${encodeURIComponent(query)}`, {
    headers: authHeaders(),
  });

export const startAutopilot = (
  artist: string,
  title: string,
  budgetCredits: number
) =>
  j<{ created: Submission[]; spent: number; errors: unknown[] }>(
    `/me/autopilot`,
    {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ artist, title, budget_credits: budgetCredits }),
    }
  );

export type ScheduledSubmission = {
  id: number;
  created_at: string;
  artist: string;
  title: string;
  curator_id: number;
  scheduled_at: string;
  status: "pending" | "executed" | "failed";
  submission_id: number | null;
  error: string | null;
};

export const createSchedule = (
  artist: string,
  title: string,
  curatorId: number,
  scheduledAt: string
) =>
  j<ScheduledSubmission>(`/me/schedule`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      artist,
      title,
      curator_id: curatorId,
      scheduled_at: scheduledAt,
    }),
  });

export const listSchedules = () =>
  j<ScheduledSubmission[]>(`/me/schedule`, { headers: authHeaders() });

/* --- Kurator payout'lari ------------------------------------------------------ */

export type Payout = {
  id: number;
  created_at: string;
  amount_usd: number;
  fee_usd: number;
  instant: number;
  status: "requested" | "paid";
};

export const requestPayout = (instant = false) =>
  j<Payout>(`/me/payouts`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ instant }),
  });

export const listPayouts = () =>
  j<Payout[]>(`/me/payouts`, { headers: authHeaders() });

/* --- Admin: satin alma talepleri + pro + sponsor + payout --------------------- */

export type PurchaseRequest = {
  id: number;
  created_at: string;
  user_id: number;
  package_key: string;
  credits: number;
  price_try: number;
  status: "pending" | "granted" | "rejected";
};

export const listPurchaseRequests = (status = "pending") =>
  j<PurchaseRequest[]>(`/admin/purchase-requests?status=${status}`, {
    headers: adminHeaders(),
  });

export const grantPurchaseRequest = (id: number) =>
  j<User>(`/admin/purchase-requests/${id}/grant`, {
    method: "POST",
    headers: adminHeaders(),
  });

export const activatePro = (userId: number, untilIso: string) =>
  j<User>(`/admin/pro/activate`, {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify({ user_id: userId, until_iso: untilIso }),
  });

export const sponsorCurator = (curatorId: number, untilIso: string) =>
  j<Curator>(`/admin/curators/sponsor`, {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify({ curator_id: curatorId, until_iso: untilIso }),
  });

export const markPayoutPaid = (payoutId: number) =>
  j<Payout>(`/admin/payouts/${payoutId}/paid`, {
    method: "POST",
    headers: adminHeaders(),
  });

/* --- Sarkilarim (sanatci sarki kutuphanesi) -------------------------------- */

/** Backend'in Turkce hata detail'ini YUTMAYAN yardimci: {data} veya {error}.
 *  j<T> null dondugu icin sayfalar gercek sebebi gosteremiyordu
 *  (or. "Sarki Deezer/Spotify'da bulunamadi..."). Yeni akislar bunu kullanir. */
export async function jd<T>(
  path: string,
  init?: RequestInit
): Promise<{ data: T | null; error: string | null }> {
  try {
    const res = await fetch(`${API}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      const detail =
        body && typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`;
      return { data: null, error: detail };
    }
    return { data: body as T, error: null };
  } catch {
    return { data: null, error: "Sunucuya ulaşılamadı" };
  }
}

export type ArtistTrack = {
  id: number;
  created_at: string;
  artist: string;
  title: string;
  track_url: string | null;
  source: "deezer" | "spotify";
};

export const myTracks = () =>
  j<ArtistTrack[]>(`/me/tracks`, { headers: authHeaders() });

/** Sarki ekle — bulunamazsa error alaninda Turkce sebep doner. */
export const addTrack = (artist: string, title: string) =>
  jd<ArtistTrack>(`/me/tracks`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ artist, title }),
  });

export const deleteTrack = (trackId: number) =>
  j<{ ok: boolean }>(`/me/tracks/${trackId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });

/* --- Radyo reklam pazari ------------------------------------------------------ */

export type RadioAdListing = {
  id: number;
  created_at: string;
  curator_id: number;
  station_name: string;
  slot_seconds: number;
  daypart: "sabah" | "gunduz" | "drive" | "aksam" | "gece";
  weekly_spots: number;
  price_week_try: number;
  description: string;
  status: "active" | "paused";
};

export type RadioAdOrder = {
  id: number;
  created_at: string;
  listing_id: number;
  buyer_name: string;
  buyer_email: string;
  buyer_kind: "artist" | "business";
  weeks: number;
  message: string;
  status: "pending" | "accepted" | "rejected" | "paid" | "airing";
  price_try: number;
  commission_try: number;
  contract_text: string | null;
  verified_plays: number;
  station_name?: string; // owner gorunumunde join'li gelir
};

export const createRadioAdListing = (payload: {
  station_name: string;
  slot_seconds: number;
  daypart: string;
  weekly_spots: number;
  price_week_try: number;
  description?: string;
}) =>
  jd<RadioAdListing>(`/me/radio-ads/listings`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });

export const myRadioAdListings = () =>
  j<RadioAdListing[]>(`/me/radio-ads/listings`, { headers: authHeaders() });

export const pauseRadioAdListing = (id: number) =>
  j<RadioAdListing>(`/me/radio-ads/listings/${id}/pause`, {
    method: "POST",
    headers: authHeaders(),
  });

export const activateRadioAdListing = (id: number) =>
  j<RadioAdListing>(`/me/radio-ads/listings/${id}/activate`, {
    method: "POST",
    headers: authHeaders(),
  });

export const publicRadioAds = (filters?: {
  daypart?: string;
  max_price?: number;
}) => {
  const q = new URLSearchParams();
  if (filters?.daypart) q.set("daypart", filters.daypart);
  if (filters?.max_price) q.set("max_price", String(filters.max_price));
  const qs = q.toString();
  return j<RadioAdListing[]>(`/public/radio-ads${qs ? `?${qs}` : ""}`);
};

export const orderRadioAd = (
  listingId: number,
  payload: {
    buyer_name: string;
    buyer_email: string;
    buyer_kind: "artist" | "business";
    weeks: number;
    message?: string;
  }
) =>
  jd<RadioAdOrder>(`/public/radio-ads/${listingId}/order`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const myRadioAdOrders = () =>
  j<RadioAdOrder[]>(`/me/radio-ads/orders`, { headers: authHeaders() });

export const respondRadioAdOrder = (
  id: number,
  action: "accepted" | "rejected"
) =>
  jd<RadioAdOrder>(`/me/radio-ads/orders/${id}/respond`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ action }),
  });

/** Radyo sahibi: spot yayinlandi -> dogrulanan yayin sayacini artir. */
export const recordRadioAdAir = (id: number) =>
  jd<RadioAdOrder>(`/me/radio-ads/orders/${id}/air`, {
    method: "POST",
    headers: authHeaders(),
  });

export const adminRadioAdOrders = (status?: string) =>
  j<RadioAdOrder[]>(
    `/admin/radio-ads/orders${status ? `?status=${status}` : ""}`,
    { headers: adminHeaders() }
  );

export const adminRadioAdMarkPaid = (id: number) =>
  j<RadioAdOrder>(`/admin/radio-ads/orders/${id}/paid`, {
    method: "POST",
    headers: adminHeaders(),
  });

/** Gonderim — hata detayli surum (kredi/cozumleme hatalari gorunur). */
export const submitToCuratorD = (
  artist: string,
  title: string,
  curatorId: number,
  opts?: { guaranteed?: boolean; priority?: boolean }
) =>
  jd<Submission>(`/me/submissions`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      artist,
      title,
      curator_id: curatorId,
      guaranteed: opts?.guaranteed ?? false,
      priority: opts?.priority ?? false,
    }),
  });

/** Admin: kullanici listesi satiri. */
export type AdminUser = {
  id: number;
  created_at: string;
  email: string;
  name: string;
  role: "artist" | "curator" | "admin";
  credits: number;
  pro_until: string | null;
  curator_id: number | null;
  referral_code: string | null;
};

export const listAdminUsers = (role?: "artist" | "curator") =>
  j<AdminUser[]>(`/admin/users${role ? `?role=${role}` : ""}`, {
    headers: adminHeaders(),
  });

/** Admin: gonderim denetim satiri (sanatci + kurator bilgisiyle). */
export type AdminSubmission = {
  id: number;
  created_at: string;
  artist: string;
  title: string;
  status: "pending" | "accepted" | "rejected" | "expired";
  deadline: string;
  cost_credits: number | null;
  guaranteed: number | null;
  priority: number | null;
  placement_verified: number;
  responded_at: string | null;
  opportunity_kind: string | null;
  curator_name: string;
  playlist_title: string;
  artist_account: string | null;
  artist_email: string | null;
};

export const listAdminSubmissions = (status?: string) =>
  j<AdminSubmission[]>(`/admin/submissions${status ? `?status=${status}` : ""}`, {
    headers: adminHeaders(),
  });

export type AdminPayout = Payout & {
  curator_user_id: number;
  curator_name: string;
  curator_email: string;
};

export const listAdminPayouts = (status = "requested") =>
  j<AdminPayout[]>(`/admin/payouts?status=${status}`, {
    headers: adminHeaders(),
  });

/** Admin: manuel kredi yukleme (odeme pilotta elden alinir). */
export const adminGrantCredits = (
  userId: number,
  amount: number,
  reason = "purchase"
) =>
  j<User>(`/admin/credits/grant`, {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify({ user_id: userId, amount, reason }),
  });

/* --- Akilli link + pre-save + hayran toplama + affiliate ---------------------- */

export type SmartLink = {
  id: number;
  created_at: string;
  user_id: number;
  slug: string;
  artist: string;
  title: string;
  release_date: string | null;
  links: Record<string, string>;
  presave: number;
  views: number;
  clicks: Record<string, number>;
};

export const createSmartLink = (payload: {
  artist: string;
  title: string;
  links: Record<string, string>;
  release_date?: string;
}) =>
  j<SmartLink>(`/me/links`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });

export const mySmartLinks = () =>
  j<SmartLink[]>(`/me/links`, { headers: authHeaders() });

/** Public link sayfasi — her cagri goruntuleme sayacini artirir. */
export const getPublicLink = (slug: string) =>
  j<SmartLink>(`/public/link/${encodeURIComponent(slug)}`);

export const recordLinkClick = (slug: string, platform: string) =>
  j<SmartLink>(`/public/link/${encodeURIComponent(slug)}/click`, {
    method: "POST",
    body: JSON.stringify({ platform }),
  });

export const addLinkFan = (slug: string, email: string) =>
  j<{ added: boolean }>(`/public/link/${encodeURIComponent(slug)}/fan`, {
    method: "POST",
    body: JSON.stringify({ email }),
  });

export type LinkFan = {
  id: number;
  created_at: string;
  link_id: number;
  email: string;
  consent: number;
};

/** Sahiplik kontrollu hayran listesi (sanatci kendi linkinin fanlarini gorur). */
export const linkFans = (linkId: number) =>
  j<LinkFan[]>(`/me/links/${linkId}/fans`, { headers: authHeaders() });

/** Fan listesi disa aktarimi — pro ucretsiz, digerine kredi duser. */
export const exportLinkFans = (linkId: number) =>
  j<LinkFan[]>(`/me/links/${linkId}/fans/export`, {
    method: "POST",
    headers: authHeaders(),
  });

export type AffiliatePartner = {
  key: string;
  name: string;
  category: string;
  description: string;
  url: string;
};

export const listAffiliates = () => j<AffiliatePartner[]>(`/affiliates`);

/** Tiklamayi sayar, ortagin yonlendirme URL'ini doner. */
export const affiliateClick = (key: string) =>
  j<{ url: string }>(`/affiliates/${encodeURIComponent(key)}/click`, {
    method: "POST",
  });

/* --- Sync/lisans mini-marketplace ---------------------------------------------- */

export type SyncListing = {
  id: number;
  created_at: string;
  user_id: number;
  artist: string;
  title: string;
  track_url: string | null;
  genres: string | null;
  mood: string | null;
  description: string | null;
  price_youtube: number | null;
  price_reklam: number | null;
  price_film: number | null;
  status: "active" | "paused";
};

export type SyncRequest = {
  id: number;
  created_at: string;
  listing_id: number;
  buyer_name: string;
  buyer_email: string;
  use_kind: string;
  message: string | null;
  status: "pending" | "accepted" | "rejected" | "paid";
  price_try: number;
  commission_try: number;
  license_text: string | null;
};

export const createSyncListing = (payload: {
  artist: string;
  title: string;
  track_url?: string;
  genres?: string;
  mood?: string;
  description?: string;
  price_youtube?: number;
  price_reklam?: number;
  price_film?: number;
}) =>
  j<SyncListing>(`/me/sync/listings`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });

export const mySyncListings = () =>
  j<SyncListing[]>(`/me/sync/listings`, { headers: authHeaders() });

export const pauseSyncListing = (listingId: number) =>
  j<SyncListing>(`/me/sync/listings/${listingId}/pause`, {
    method: "POST",
    headers: authHeaders(),
  });

export const activateSyncListing = (listingId: number) =>
  j<SyncListing>(`/me/sync/listings/${listingId}/activate`, {
    method: "POST",
    headers: authHeaders(),
  });

/** Public katalog — sadece active ilanlar. use_kind: youtube|reklam|film|podcast|diger. */
export const publicSyncCatalog = (filters?: {
  use_kind?: string;
  genre?: string;
}) => {
  const params = new URLSearchParams();
  if (filters?.use_kind) params.set("use_kind", filters.use_kind);
  if (filters?.genre) params.set("genre", filters.genre);
  const qs = params.toString();
  return j<SyncListing[]>(`/public/sync${qs ? `?${qs}` : ""}`);
};

export const requestSyncLicense = (
  listingId: number,
  payload: {
    buyer_name: string;
    buyer_email: string;
    use_kind: string;
    message?: string;
  }
) =>
  j<SyncRequest>(`/public/sync/${listingId}/request`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const mySyncRequests = () =>
  j<SyncRequest[]>(`/me/sync/requests`, { headers: authHeaders() });

export const respondSyncRequest = (
  id: number,
  action: "accepted" | "rejected"
) =>
  j<SyncRequest>(`/me/sync/requests/${id}/respond`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ action }),
  });

export const adminSyncRequests = (status?: string) =>
  j<SyncRequest[]>(
    `/admin/sync/requests${status ? `?status=${status}` : ""}`,
    { headers: adminHeaders() }
  );

export const adminSyncMarkPaid = (id: number) =>
  j<SyncRequest>(`/admin/sync/requests/${id}/paid`, {
    method: "POST",
    headers: adminHeaders(),
  });

/* --- Label / A&R B2B erisimi ---------------------------------------------------- */

export type LabelLead = {
  id: number;
  created_at: string;
  company: string;
  contact_name: string;
  email: string;
  note: string;
  status: "pending" | "approved" | "rejected";
  access_token: string | null;
  expires_at: string | null;
};

export const applyLabel = (payload: {
  company: string;
  contact_name: string;
  email: string;
  note?: string;
}) =>
  j<LabelLead>(`/public/labels/apply`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const adminLabels = (status?: string) =>
  j<LabelLead[]>(`/admin/labels${status ? `?status=${status}` : ""}`, {
    headers: adminHeaders(),
  });

export const approveLabel = (id: number) =>
  j<LabelLead>(`/admin/labels/${id}/approve`, {
    method: "POST",
    headers: adminHeaders(),
  });

export const rejectLabel = (id: number) =>
  j<LabelLead>(`/admin/labels/${id}/reject`, {
    method: "POST",
    headers: adminHeaders(),
  });

export type RisingArtistEntry = {
  artist_name: string;
  latest_score: number;
  score_delta: number | null;
  accepted: number;
  verified_placements: number;
  accept_rate: number | null;
};

/** Auth gerektirmez — sureli access_token yeter (30 gun). */
export const labelReport = (token: string) =>
  j<RisingArtistEntry[]>(`/labels/report?token=${encodeURIComponent(token)}`);

/* --- Radyo airplay takibi -------------------------------------------------------- */

export type AirplayStation = {
  id: number;
  created_at: string;
  name: string;
  meta_url: string;
  kind: "icecast" | "shoutcast";
  active: number;
};

export type AirplaySubscription = {
  id: number;
  created_at: string;
  user_id: number;
  artist: string;
  title: string;
  expires_at: string;
  active: number;
};

export type AirplayHit = {
  id: number;
  created_at: string;
  station_id: number;
  subscription_id: number;
  raw_title: string | null;
  artist: string;
  title: string;
  station_name: string;
  station_kind: string;
};

export const adminAddStation = (payload: {
  name: string;
  meta_url: string;
  kind?: "icecast" | "shoutcast";
}) =>
  j<AirplayStation>(`/admin/airplay/stations`, {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify(payload),
  });

export const adminStations = () =>
  j<AirplayStation[]>(`/admin/airplay/stations`, { headers: adminHeaders() });

/** Manuel tetik: arka plandaki 10 dakikalik dongu beklenmeden yoklama yapar. */
export const adminAirplayPoll = () =>
  j<{ checked_stations: number; hits: AirplayHit[] }>(`/admin/airplay/poll`, {
    method: "POST",
    headers: adminHeaders(),
  });

export const subscribeAirplay = (artist: string, title: string) =>
  j<AirplaySubscription>(`/me/airplay/subscribe`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ artist, title }),
  });

export const myAirplaySubscriptions = () =>
  j<AirplaySubscription[]>(`/me/airplay/subscriptions`, {
    headers: authHeaders(),
  });

export const myAirplayHits = () =>
  j<AirplayHit[]>(`/me/airplay/hits`, { headers: authHeaders() });

/* --- Otomatik tanitim videosu / animasyonlu kanit karti (promo) ---------------- */

export type PromoAsset = {
  id: number;
  created_at: string;
  user_id: number;
  token: string;
  artist: string;
  title: string;
  style: "dark" | "light";
};

export const createPromo = (
  artist: string,
  title: string,
  style: "dark" | "light" = "dark"
) =>
  j<PromoAsset>(`/me/promo`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ artist, title, style }),
  });

export const myPromos = () =>
  j<{ items: PromoAsset[] }>(`/me/promo`, { headers: authHeaders() });

/** Animasyonlu SVG'yi (guncel skor/kapak ile) blob URL olarak acar. */
export const openPromoSvg = (token: string) =>
  fetchBlobUrl(`/me/promo/${encodeURIComponent(token)}.svg`);

/* --- Geri bildirim sentez raporu ------------------------------------------------ */

export type FeedbackDigest = {
  stats: {
    total_feedback: number;
    accepted: number;
    acceptance_rate: number;
    tier_breakdown: Record<string, { total: number; accepted: number }>;
  };
  top_keywords: { keyword: string; count: number }[];
  themes: { keyword: string; mentions: number; action: string }[];
  opportunity_breakdown: Record<string, number>;
  created_at: string;
};

/** Dolu geri bildirimlerden yeni sentez raporu uretir (en az 2 gerekli). */
export const createFeedbackDigest = () =>
  j<FeedbackDigest>(`/me/feedback-digest`, {
    method: "POST",
    headers: authHeaders(),
  });

/** En son uretilmis sentez raporu; hic yoksa null. */
export const latestFeedbackDigest = () =>
  j<FeedbackDigest>(`/me/feedback-digest`, { headers: authHeaders() });
