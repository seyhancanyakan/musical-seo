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

export const generatePitches = (query: string, limit = 5) =>
  j<{ playlist: PlaylistMatch; message: string }[]>(`/pitch/generate`, {
    method: "POST",
    body: JSON.stringify({ query, limit }),
  });

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
