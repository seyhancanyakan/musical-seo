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
  // İletişim kaynağı — nereden bulundu (manuel doğrulama için).
  contact_source?: string | null;
  source_url?: string | null;
  contact_confidence?: number | null;
};

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
}) => j<Curator>(`/curators/apply`, { method: "POST", body: JSON.stringify(payload) });

export const listCurators = () => j<Curator[]>(`/curators`);

/** Admin: tüm curator'lar (pending + approved + rejected). status="" → API None → hepsi. */
export const listAllCurators = () => j<Curator[]>(`/curators?status=`);

/** Admin: bir curator'ın başvuru durumunu değiştir. */
export const setCuratorStatus = (id: number, status: CuratorStatus) =>
  j<Curator>(`/curators/${id}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });

export const createSubmission = (payload: {
  artist: string;
  title: string;
  curator_id: number;
}) => j<Submission>(`/submissions`, { method: "POST", body: JSON.stringify(payload) });

export const listSubmissions = (curatorId?: number) =>
  j<Submission[]>(
    `/submissions${curatorId ? `?curator_id=${curatorId}` : ""}`
  );

export const respondSubmission = (
  id: number,
  action: "accepted" | "rejected",
  feedback = ""
) =>
  j<Submission>(`/submissions/${id}/respond`, {
    method: "POST",
    body: JSON.stringify({ action, feedback }),
  });

export const verifyPlacement = (id: number) =>
  j<Submission & { placement_checked: boolean }>(
    `/submissions/${id}/verify-placement`,
    { method: "POST" }
  );

/* --- Hesap / kredi / cekirdek dongu ------------------------------------- */

export type User = {
  id: number;
  created_at: string;
  email: string;
  role: "artist" | "curator" | "admin";
  name: string;
  curator_id: number | null;
  credits: number;
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
  curatorId: number
) =>
  j<Submission>(`/me/submissions`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ artist, title, curator_id: curatorId }),
  });

export const myInbox = () =>
  j<Submission[]>(`/me/inbox`, { headers: authHeaders() });

export const myRespond = (
  id: number,
  action: "accepted" | "rejected",
  feedback = ""
) =>
  j<Submission>(`/me/submissions/${id}/respond`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ action, feedback }),
  });

export const myEarnings = () =>
  j<Earnings>(`/me/earnings`, { headers: authHeaders() });
