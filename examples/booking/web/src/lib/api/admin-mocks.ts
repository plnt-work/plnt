/**
 * Admin v2 mocks — same shape as lib/api/admin-v2.ts, served from a
 * deterministic in-memory store. Lets us land the UX before the MA
 * stream ships task #8.
 *
 * Determinism rules:
 *   - All timestamps are derived from MOCK_NOW (a fixed unix-seconds
 *     anchor) so the screenshots in PRs and the dev surface don't churn
 *     across reloads.
 *   - Random-ish picks use a small LCG seeded by record index, NOT
 *     Math.random — keeps the lint-purity rule happy and yields the
 *     same data set on every reload.
 *
 * Swap behavior: the query hooks in lib/queries/ call into here when
 * VITE_ADMIN_MOCK=1, or always if the live endpoint 404s. Either way
 * the component layer sees the same typed shape.
 */
import type {
  Booking,
  BookingsQuery,
  BookingsResponse,
  InstalledAgent,
  InstalledAgentsResponse,
  MarketplaceAgent,
  MarketplaceResponse,
  NotificationEntry,
  NotificationsResponse,
  SessionRow,
  SessionsResponse,
  TranscriptEntry,
  TranscriptResponse,
  UserDetail,
  UserSummary,
  UsersResponse,
} from "./admin-v2";

import { SAMPLE_BUSINESSES } from "@/features/places/sample-businesses";
import { AGENTS } from "@/features/agents/registry";

const MOCK_NOW = 1_782_400_000; // June 25 2026 evening, matches the slice timeline
const HOUR = 3600;

/* ─── tiny seeded LCG ───────────────────────────────────────────── */
function lcg(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

/* ─── synthetic users ───────────────────────────────────────────── */
const USERS = [
  { user_id: "user-aanya", display: "Aanya" },
  { user_id: "user-rohan", display: "Rohan" },
  { user_id: "user-priya", display: "Priya" },
  { user_id: "user-kabir", display: "Kabir" },
  { user_id: "user-meera", display: "Meera" },
  { user_id: "user-arjun", display: "Arjun" },
  { user_id: "user-ishaan", display: "Ishaan" },
];

/* ─── synthetic bookings ────────────────────────────────────────── */
const BOOKING_STATUSES: Array<Booking["status"]> = ["confirmed", "confirmed", "confirmed", "pending", "failed", "cancelled"];

const BOOKINGS_STORE: Booking[] = (() => {
  const rng = lcg(42);
  const out: Booking[] = [];
  let bid = 1001;
  for (let i = 0; i < 24; i++) {
    const u = USERS[Math.floor(rng() * USERS.length)]!;
    const biz = SAMPLE_BUSINESSES[Math.floor(rng() * SAMPLE_BUSINESSES.length)]!;
    const status = BOOKING_STATUSES[Math.floor(rng() * BOOKING_STATUSES.length)]!;
    const ageHours = Math.floor(rng() * 96);
    const slotHourOffset = Math.floor(rng() * 96) - 24; // -24h to +72h from MOCK_NOW
    out.push({
      booking_id: `bkg_${bid++}`,
      user_id: u.user_id,
      business_id: biz.place_id,
      slot: new Date((MOCK_NOW + slotHourOffset * HOUR) * 1000).toISOString(),
      status,
      idempotency_key: `idem-${u.user_id}-${biz.place_id}-${i}`,
      created_at: MOCK_NOW - ageHours * HOUR,
    });
  }
  return out.sort((a, b) => b.created_at - a.created_at);
})();

/* ─── synthetic sessions ────────────────────────────────────────── */
const SESSIONS_STORE: SessionRow[] = (() => {
  const rng = lcg(7);
  const out: SessionRow[] = [];
  let sid = 5001;
  for (let i = 0; i < 28; i++) {
    const u = USERS[Math.floor(rng() * USERS.length)]!;
    const biz = SAMPLE_BUSINESSES[Math.floor(rng() * SAMPLE_BUSINESSES.length)]!;
    const ageHours = Math.floor(rng() * 120);
    const msgCount = 2 + Math.floor(rng() * 18);
    const started = MOCK_NOW - ageHours * HOUR;
    const lastAt = started + Math.floor(rng() * 1200);
    const status: SessionRow["status"] =
      ageHours < 1 ? "active" : ageHours < 12 ? "idle" : "closed";
    out.push({
      session_id: `sess_${sid++}`,
      user_id: u.user_id,
      business_id: rng() > 0.2 ? biz.place_id : null,
      message_count: msgCount,
      last_message_at: lastAt,
      started_at: started,
      status,
    });
  }
  return out.sort((a, b) => b.last_message_at - a.last_message_at);
})();

/* ─── canned transcripts ────────────────────────────────────────── */
function makeTranscript(sess: SessionRow): TranscriptEntry[] {
  const out: TranscriptEntry[] = [];
  const start = sess.started_at;
  const bizName = sess.business_id
    ? (SAMPLE_BUSINESSES.find((b) => b.place_id === sess.business_id)?.display_name ?? sess.business_id)
    : "a place";
  out.push({
    seq: 1,
    role: "user",
    content: { text: `table for two at ${bizName} tonight at 8pm` },
    at: start,
  });
  out.push({
    seq: 2,
    role: "system",
    content: { note: `Looking up ${bizName}…` },
    at: start + 1,
  });
  out.push({
    seq: 3,
    role: "resolve_business",
    content: { best_match: { name: bizName, address: "Colaba, Mumbai" } },
    at: start + 2,
  });
  out.push({
    seq: 4,
    role: "system",
    content: { note: `Checking availability at ${bizName}…` },
    at: start + 3,
  });
  const slotIso = new Date((start + 4 * HOUR) * 1000).toISOString();
  out.push({
    seq: 5,
    role: "check_availability",
    content: { slots: [slotIso] },
    at: start + 5,
  });
  out.push({
    seq: 6,
    role: "say",
    content: {
      say: `${bizName} has a table for two at 8pm tonight. Want me to confirm?`,
      action: { kind: "offer_slots", slots: [slotIso], business_name: bizName },
    },
    at: start + 6,
  });
  if (sess.message_count >= 8) {
    out.push({ seq: 7, role: "user", content: { text: "yes book it" }, at: start + 14 });
    out.push({
      seq: 8,
      role: "say",
      content: {
        say: `Done — your table at ${bizName} is held for 8pm.`,
        action: {
          kind: "booking_confirmed",
          business_name: bizName,
          slot: slotIso,
          booking_id: `bkg_${1000 + (sess.message_count % 50)}`,
        },
      },
      at: start + 22,
    });
  }
  return out;
}

/* ─── installed-agents store (mutable) ──────────────────────────── */
const INSTALLED: InstalledAgent[] = AGENTS.slice(0, 4).map((a, i) => ({
  slug: a.slug,
  enabled: true,
  config: {},
  installed_at: MOCK_NOW - (10 + i * 4) * HOUR * 24,
  last_used_at: MOCK_NOW - (1 + i * 3) * HOUR,
  conversation_count: 12 + i * 7,
}));

const MARKETPLACE_AGENTS: MarketplaceAgent[] = AGENTS.map((a) => ({
  slug: a.slug,
  display_name: a.label,
  description: a.hint,
  vertical: a.verticals.join(","),
  tools: a.slug === "reservations" || a.slug === "appointments"
    ? ["check_availability", "create_booking", "cancel_booking"]
    : a.slug === "menu" ? ["fetch_menu"]
    : a.slug === "inventory" ? ["stock_query", "refill_request"]
    : a.slug === "membership" ? ["plans_query", "signup"]
    : ["lookup_hours", "lookup_address"],
  default_config: {
    confirm_before_mutation: true,
    max_steps: 1,
  },
}));

/* ─── delay helper to mimic network feel ────────────────────────── */
function delay<T>(value: T, ms = 250): Promise<T> {
  return new Promise((res) => setTimeout(() => res(value), ms));
}

/* ─── public mock API ───────────────────────────────────────────── */

export async function mockListBookings(_tid: string, q: BookingsQuery = {}): Promise<BookingsResponse> {
  let rows = BOOKINGS_STORE.slice();
  if (q.status) rows = rows.filter((b) => b.status === q.status);
  if (q.user_id) rows = rows.filter((b) => b.user_id === q.user_id);
  if (q.since !== undefined) rows = rows.filter((b) => b.created_at >= q.since!);
  const total = rows.length;
  if (q.limit !== undefined) rows = rows.slice(0, q.limit);
  return delay({ bookings: rows, total });
}

export async function mockListSessions(
  _tid: string,
  q: { user_id?: string; limit?: number } = {},
): Promise<SessionsResponse> {
  let rows = SESSIONS_STORE.slice();
  if (q.user_id) rows = rows.filter((s) => s.user_id === q.user_id);
  const total = rows.length;
  if (q.limit !== undefined) rows = rows.slice(0, q.limit);
  return delay({ sessions: rows, total });
}

export async function mockGetTranscript(_tid: string, sessionId: string): Promise<TranscriptResponse> {
  const sess = SESSIONS_STORE.find((s) => s.session_id === sessionId);
  if (!sess) return delay({ transcript: [] });
  return delay({ transcript: makeTranscript(sess) });
}

export async function mockListUsers(_tid: string): Promise<UsersResponse> {
  const users: UserSummary[] = USERS.map((u) => {
    const userBookings = BOOKINGS_STORE.filter((b) => b.user_id === u.user_id);
    const userSessions = SESSIONS_STORE.filter((s) => s.user_id === u.user_id);
    return {
      user_id: u.user_id,
      first_seen: userSessions.length
        ? Math.min(...userSessions.map((s) => s.started_at))
        : MOCK_NOW,
      last_seen: userSessions.length
        ? Math.max(...userSessions.map((s) => s.last_message_at))
        : MOCK_NOW,
      sessions: userSessions.length,
      bookings: userBookings.length,
    };
  }).sort((a, b) => b.last_seen - a.last_seen);
  return delay({ users });
}

export async function mockGetUser(_tid: string, userId: string): Promise<UserDetail> {
  return delay({
    user_id: userId,
    bookings: BOOKINGS_STORE.filter((b) => b.user_id === userId),
    sessions: SESSIONS_STORE.filter((s) => s.user_id === userId),
  });
}

export async function mockListMarketplace(vertical?: string): Promise<MarketplaceResponse> {
  const agents = vertical
    ? MARKETPLACE_AGENTS.filter((a) => a.vertical.split(",").includes(vertical))
    : MARKETPLACE_AGENTS;
  return delay({ agents });
}

export async function mockListInstalledAgents(_tid: string): Promise<InstalledAgentsResponse> {
  return delay({ agents: INSTALLED.slice() });
}

export async function mockInstallAgent(_tid: string, slug: string): Promise<InstalledAgent> {
  const existing = INSTALLED.find((a) => a.slug === slug);
  if (existing) {
    existing.enabled = true;
    return delay(existing, 350);
  }
  const fresh: InstalledAgent = {
    slug,
    enabled: true,
    config: { ...(MARKETPLACE_AGENTS.find((m) => m.slug === slug)?.default_config ?? {}) },
    installed_at: MOCK_NOW,
    last_used_at: null,
    conversation_count: 0,
  };
  INSTALLED.push(fresh);
  return delay(fresh, 350);
}

export async function mockPatchAgent(
  _tid: string,
  slug: string,
  body: { enabled?: boolean; config?: Record<string, unknown> },
): Promise<InstalledAgent> {
  const existing = INSTALLED.find((a) => a.slug === slug);
  if (!existing) throw new Error(`mockPatchAgent: ${slug} not installed`);
  if (body.enabled !== undefined) existing.enabled = body.enabled;
  if (body.config) existing.config = { ...existing.config, ...body.config };
  return delay(existing, 200);
}

export async function mockUninstallAgent(_tid: string, slug: string): Promise<void> {
  const idx = INSTALLED.findIndex((a) => a.slug === slug);
  if (idx >= 0) INSTALLED.splice(idx, 1);
  return delay(undefined, 200);
}

/* ─── notifications derived from confirmed/cancelled bookings ───── */

const NOTIFICATIONS_STORE: NotificationEntry[] = BOOKINGS_STORE
  .filter((b) => b.status === "confirmed" || b.status === "cancelled")
  .slice(0, 8)
  .map((b, i) => {
    const kind = b.status === "confirmed" ? "booking_confirmed" as const : "booking_compensated" as const;
    return {
      id: `ntf_mock_${b.booking_id}`,
      ts: b.created_at,
      kind,
      title: kind === "booking_confirmed" ? "Booking confirmed" : "Booking cancelled (compensated)",
      body: `Booking ${b.booking_id} for ${new Date(b.slot).toLocaleString()} is ${b.status}.`,
      data: { booking_id: b.booking_id, business_name: b.business_id, slot: b.slot },
      read: i >= 3,
    };
  })
  .sort((a, b) => b.ts - a.ts);

export async function mockListNotifications(
  _tid: string,
  q: { limit?: number; unread?: boolean } = {},
): Promise<NotificationsResponse> {
  let rows = NOTIFICATIONS_STORE.slice();
  if (q.unread) rows = rows.filter((n) => !n.read);
  if (q.limit !== undefined) rows = rows.slice(0, q.limit);
  return delay({
    notifications: rows,
    unread_count: NOTIFICATIONS_STORE.filter((n) => !n.read).length,
  });
}

export async function mockMarkNotificationsRead(
  _tid: string,
  ids: string[],
): Promise<{ updated: number }> {
  let updated = 0;
  for (const n of NOTIFICATIONS_STORE) {
    if (ids.includes(n.id) && !n.read) {
      n.read = true;
      updated += 1;
    }
  }
  return delay({ updated }, 150);
}

/* ─── overview KPIs derived from the same data ──────────────────── */
export interface OverviewKpis {
  conversations_24h: number;
  bookings_24h: number;
  active_users_24h: number;
  avg_messages: number;
  bookings_by_status: Record<Booking["status"], number>;
  recent_sessions: SessionRow[];
}

export async function mockOverviewKpis(_tid: string): Promise<OverviewKpis> {
  const since = MOCK_NOW - 24 * HOUR;
  const recentSess = SESSIONS_STORE.filter((s) => s.last_message_at >= since);
  const recentBook = BOOKINGS_STORE.filter((b) => b.created_at >= since);
  const activeUsers = new Set(recentSess.map((s) => s.user_id)).size;
  const avgMsg = recentSess.length
    ? recentSess.reduce((sum, s) => sum + s.message_count, 0) / recentSess.length
    : 0;
  const byStatus: Record<Booking["status"], number> = {
    pending: 0, confirmed: 0, failed: 0, cancelled: 0,
  };
  for (const b of BOOKINGS_STORE) byStatus[b.status] += 1;
  return delay({
    conversations_24h: recentSess.length,
    bookings_24h: recentBook.length,
    active_users_24h: activeUsers,
    avg_messages: Number(avgMsg.toFixed(1)),
    bookings_by_status: byStatus,
    recent_sessions: SESSIONS_STORE.slice(0, 8),
  });
}
