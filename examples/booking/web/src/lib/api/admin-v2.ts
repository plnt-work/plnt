/**
 * Admin v2 client — typed wrappers around the endpoints the MA stream is
 * building under task #8. Shape matches the spec exactly; if the backend
 * renames a field, this is the one file to edit.
 *
 * Each function returns the parsed body or throws. The query hooks in
 * lib/queries/ wrap these with react-query for caching/polling.
 *
 * In dev (`VITE_ADMIN_MOCK=1` or the endpoint 404s) the hooks fall back
 * to lib/api/admin-mocks.ts. That swap is owned by the hook, not by these
 * client functions — they're the live path.
 */
const BASE = "/v1/admin";
const MARKETPLACE = "/v1/marketplace";

function headers(): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const token = import.meta.env.VITE_ADMIN_TOKEN as string | undefined;
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

/* ─── Bookings ──────────────────────────────────────────────────── */

export type BookingStatus = "pending" | "confirmed" | "failed" | "cancelled";

export interface Booking {
  booking_id: string;
  user_id: string;
  business_id: string;
  /** ISO 8601 timestamp of the slot the user actually booked. */
  slot: string;
  status: BookingStatus;
  idempotency_key: string;
  /** Unix seconds (per backend convention). */
  created_at: number;
}

export interface BookingsQuery {
  status?: BookingStatus;
  user_id?: string;
  /** Unix seconds — created_at >= since. */
  since?: number;
  limit?: number;
}

export interface BookingsResponse {
  bookings: Booking[];
  total: number;
}

export async function listBookings(
  tenantId: string,
  q: BookingsQuery = {},
): Promise<BookingsResponse> {
  const url = new URL(
    `${BASE}/tenants/${encodeURIComponent(tenantId)}/bookings`,
    window.location.origin,
  );
  if (q.status) url.searchParams.set("status", q.status);
  if (q.user_id) url.searchParams.set("user_id", q.user_id);
  if (q.since !== undefined) url.searchParams.set("since", String(q.since));
  if (q.limit !== undefined) url.searchParams.set("limit", String(q.limit));
  const r = await fetch(url.toString(), { headers: headers() });
  if (!r.ok) throw new Error(`listBookings ${r.status}`);
  return r.json();
}

/* ─── Sessions ──────────────────────────────────────────────────── */

export type SessionStatus = "active" | "idle" | "closed";

export interface SessionRow {
  session_id: string;
  user_id: string;
  business_id: string | null;
  message_count: number;
  /** Unix seconds. */
  last_message_at: number;
  started_at: number;
  status: SessionStatus;
}

export interface SessionsResponse {
  sessions: SessionRow[];
  total: number;
}

export async function listSessions(
  tenantId: string,
  q: { user_id?: string; limit?: number } = {},
): Promise<SessionsResponse> {
  const url = new URL(
    `${BASE}/tenants/${encodeURIComponent(tenantId)}/sessions`,
    window.location.origin,
  );
  if (q.user_id) url.searchParams.set("user_id", q.user_id);
  if (q.limit !== undefined) url.searchParams.set("limit", String(q.limit));
  const r = await fetch(url.toString(), { headers: headers() });
  if (!r.ok) throw new Error(`listSessions ${r.status}`);
  return r.json();
}

export interface TranscriptEntry {
  seq: number;
  role: string;
  content: Record<string, unknown>;
  action?: Record<string, unknown> | null;
  /** Unix seconds. */
  at: number;
}

export interface TranscriptResponse {
  transcript: TranscriptEntry[];
}

export async function getTranscript(
  tenantId: string,
  sessionId: string,
): Promise<TranscriptResponse> {
  const r = await fetch(
    `${BASE}/tenants/${encodeURIComponent(tenantId)}/sessions/${encodeURIComponent(sessionId)}/transcript`,
    { headers: headers() },
  );
  if (!r.ok) throw new Error(`getTranscript ${r.status}`);
  return r.json();
}

/* ─── Notifications ─────────────────────────────────────────────── */

export type NotificationKind = "booking_confirmed" | "booking_compensated";

export interface NotificationEntry {
  id: string;
  /** Unix seconds. */
  ts: number;
  kind: NotificationKind;
  title: string;
  body: string;
  data: Record<string, unknown>;
  read: boolean;
}

export interface NotificationsResponse {
  notifications: NotificationEntry[];
  unread_count: number;
}

export async function listNotifications(
  tenantId: string,
  q: { limit?: number; unread?: boolean } = {},
): Promise<NotificationsResponse> {
  const url = new URL(
    `${BASE}/tenants/${encodeURIComponent(tenantId)}/notifications`,
    window.location.origin,
  );
  if (q.limit !== undefined) url.searchParams.set("limit", String(q.limit));
  if (q.unread) url.searchParams.set("unread", "true");
  const r = await fetch(url.toString(), { headers: headers() });
  if (!r.ok) throw new Error(`listNotifications ${r.status}`);
  return r.json();
}

export async function markNotificationsRead(
  tenantId: string,
  ids: string[],
): Promise<{ updated: number }> {
  const r = await fetch(
    `${BASE}/tenants/${encodeURIComponent(tenantId)}/notifications/read`,
    { method: "POST", headers: headers(), body: JSON.stringify({ ids }) },
  );
  if (!r.ok) throw new Error(`markNotificationsRead ${r.status}`);
  return r.json();
}

/* ─── Users ─────────────────────────────────────────────────────── */

export interface UserSummary {
  user_id: string;
  first_seen: number;
  last_seen: number;
  sessions: number;
  bookings: number;
}

export interface UsersResponse {
  users: UserSummary[];
}

export async function listUsers(tenantId: string): Promise<UsersResponse> {
  const r = await fetch(
    `${BASE}/tenants/${encodeURIComponent(tenantId)}/users`,
    { headers: headers() },
  );
  if (!r.ok) throw new Error(`listUsers ${r.status}`);
  return r.json();
}

export interface UserDetail {
  user_id: string;
  bookings: Booking[];
  sessions: SessionRow[];
}

export async function getUser(tenantId: string, userId: string): Promise<UserDetail> {
  const r = await fetch(
    `${BASE}/tenants/${encodeURIComponent(tenantId)}/users/${encodeURIComponent(userId)}`,
    { headers: headers() },
  );
  if (!r.ok) throw new Error(`getUser ${r.status}`);
  return r.json();
}

/* ─── Marketplace + installed agents ────────────────────────────── */

export interface MarketplaceAgent {
  slug: string;
  display_name: string;
  description: string;
  vertical: string;
  tools: string[];
  default_config: Record<string, unknown>;
  /** Bundle version the catalog would install (semver). */
  version?: string;
  /** false = coming-soon; install returns 409. Absent = installable. */
  available?: boolean;
}

export interface MarketplaceResponse {
  agents: MarketplaceAgent[];
}

export async function listMarketplace(vertical?: string): Promise<MarketplaceResponse> {
  const url = new URL(`${MARKETPLACE}/agents`, window.location.origin);
  if (vertical) url.searchParams.set("vertical", vertical);
  const r = await fetch(url.toString(), { headers: headers() });
  if (!r.ok) throw new Error(`listMarketplace ${r.status}`);
  return r.json();
}

export interface InstalledAgent {
  slug: string;
  /** Installed bundle version (from the `<slug>@<version>` dir name). */
  version?: string;
  enabled: boolean;
  config: Record<string, unknown>;
  installed_at: number;
  last_used_at: number | null;
  conversation_count: number;
}

export interface InstalledAgentsResponse {
  agents: InstalledAgent[];
}

export async function listInstalledAgents(tenantId: string): Promise<InstalledAgentsResponse> {
  const r = await fetch(
    `${BASE}/tenants/${encodeURIComponent(tenantId)}/agents`,
    { headers: headers() },
  );
  if (!r.ok) throw new Error(`listInstalledAgents ${r.status}`);
  return r.json();
}

export async function installAgent(tenantId: string, slug: string): Promise<InstalledAgent> {
  const r = await fetch(
    `${BASE}/tenants/${encodeURIComponent(tenantId)}/agents/${encodeURIComponent(slug)}`,
    { method: "POST", headers: headers() },
  );
  if (!r.ok) throw new Error(`installAgent ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function patchAgent(
  tenantId: string,
  slug: string,
  body: { enabled?: boolean; config?: Record<string, unknown> },
): Promise<InstalledAgent> {
  const r = await fetch(
    `${BASE}/tenants/${encodeURIComponent(tenantId)}/agents/${encodeURIComponent(slug)}`,
    { method: "PATCH", headers: headers(), body: JSON.stringify(body) },
  );
  if (!r.ok) throw new Error(`patchAgent ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function uninstallAgent(tenantId: string, slug: string): Promise<void> {
  const r = await fetch(
    `${BASE}/tenants/${encodeURIComponent(tenantId)}/agents/${encodeURIComponent(slug)}`,
    { method: "DELETE", headers: headers() },
  );
  if (!r.ok && r.status !== 404) throw new Error(`uninstallAgent ${r.status}`);
}

/* ─── Docs (menu upload — slice 8 backend, slice 6 merchant auth) ── */

export interface UploadedDoc {
  name: string;
  size: number;
  uploaded_at: number;
  chunks: number;
}

export async function uploadDoc(tenantId: string, file: File): Promise<UploadedDoc> {
  const form = new FormData();
  form.append("file", file);
  // No Content-Type header — the browser sets the multipart boundary.
  const h: Record<string, string> = {};
  const token = import.meta.env.VITE_ADMIN_TOKEN as string | undefined;
  if (token) h["Authorization"] = `Bearer ${token}`;
  const r = await fetch(`${BASE}/tenants/${encodeURIComponent(tenantId)}/docs`, {
    method: "POST",
    headers: h,
    body: form,
  });
  if (!r.ok) {
    let detail = "";
    try {
      detail = ((await r.json()) as { detail?: string }).detail ?? "";
    } catch {
      /* non-JSON body */
    }
    throw new Error(detail || `uploadDoc ${r.status}`);
  }
  return r.json();
}
