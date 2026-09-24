// Booking endpoints — POST /v1/bookings, GET /v1/users/:userId/bookings,
// GET /v1/bookings/:id. Mock-first; flip LIVE_MODE once MA-P6 ships.
//
// Mock storage: AsyncStorage at key `plnt.mock-bookings:{userId}` so a
// confirmed booking shows up in the Bookings tab end-to-end (across
// process restarts) without any real backend.
//
// Source-of-truth zod schemas are exported so MA worker can mirror them.
import { z } from "zod";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { apiGet } from "./client";
import { env } from "@/lib/env";
import { ServiceSchema, type Service } from "./venues";

const LIVE_MODE = true;

export const BookingStatusSchema = z.enum(["confirmed", "compensated", "failed"]);
export type BookingStatus = z.infer<typeof BookingStatusSchema>;

export const BookingSummarySchema = z.object({
  booking_id: z.string(),
  place_id: z.string(),
  venue_name: z.string(),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  slot: z.string().regex(/^\d{2}:\d{2}$/),
  pro_id: z.string(),
  services: z.array(ServiceSchema),
  total_cents: z.number(),
  status: BookingStatusSchema,
  created_at: z.string(),
});
export type BookingSummary = z.infer<typeof BookingSummarySchema>;

export const CreateBookingRequestSchema = z.object({
  place_id: z.string(),
  venue_name: z.string(),
  user_id: z.string(),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  slot: z.string().regex(/^\d{2}:\d{2}$/),
  pro_id: z.string(),
  service_ids: z.array(z.string()),
});
export type CreateBookingRequest = z.infer<typeof CreateBookingRequestSchema>;

export const CreateBookingResponseSchema = z.object({
  booking: BookingSummarySchema,
});
export type CreateBookingResponse = z.infer<typeof CreateBookingResponseSchema>;

export const UserBookingsResponseSchema = z.object({
  upcoming: z.array(BookingSummarySchema),
  past: z.array(BookingSummarySchema),
});
export type UserBookingsResponse = z.infer<typeof UserBookingsResponseSchema>;

// ─────────────────────────── mock store ───────────────────────────

function mockKey(userId: string): string {
  return `plnt.mock-bookings:${userId}`;
}

async function readAll(userId: string): Promise<BookingSummary[]> {
  const raw = await AsyncStorage.getItem(mockKey(userId));
  if (!raw) return [];
  try {
    return z.array(BookingSummarySchema).parse(JSON.parse(raw));
  } catch {
    return [];
  }
}

async function writeAll(userId: string, all: BookingSummary[]): Promise<void> {
  await AsyncStorage.setItem(mockKey(userId), JSON.stringify(all));
}

/** Stable per-(place, date, slot, services, pro) booking id so mock
 *  retries are idempotent — matches the saga store on the backend. */
export function mockBookingId(req: CreateBookingRequest): string {
  const key = [
    req.place_id,
    req.date,
    req.slot,
    [...req.service_ids].sort().join(","),
    req.pro_id,
  ].join("|");
  // small hash → 12 hex chars (mirrors the python saga deterministic id)
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < key.length; i++) {
    const c = key.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 2654435761);
    h2 = Math.imul(h2 ^ c, 1597334677);
  }
  const hex = (h1 >>> 0).toString(16).padStart(8, "0") + (h2 >>> 0).toString(16).padStart(4, "0").slice(0, 4);
  return `bk_${hex}`;
}

// Used by the mock createBooking to build the BookingSummary's services
// field with the same shape MA's response will carry. Callers pass the
// resolved Service objects (from the cart) — service_ids alone wouldn't
// have prices/durations after the request.
interface MockResolveContext {
  services: Service[];
  venue_name: string;
}

async function mockCreateBooking(
  req: CreateBookingRequest,
  ctx: MockResolveContext,
): Promise<CreateBookingResponse> {
  const all = await readAll(req.user_id);
  const id = mockBookingId(req);
  const existing = all.find((b) => b.booking_id === id);
  if (existing) return { booking: existing };
  const booking: BookingSummary = {
    booking_id: id,
    place_id: req.place_id,
    venue_name: ctx.venue_name,
    date: req.date,
    slot: req.slot,
    pro_id: req.pro_id,
    services: ctx.services,
    total_cents: ctx.services.reduce((a, s) => a + s.price_cents, 0),
    status: "confirmed",
    created_at: "2026-06-26T00:00:00Z", // stable for tests; live uses server time
  };
  await writeAll(req.user_id, [...all, booking]);
  return { booking };
}

async function mockUserBookings(userId: string): Promise<UserBookingsResponse> {
  const all = await readAll(userId);
  // Partition by date — treat lexicographic compare against today as
  // good-enough since "YYYY-MM-DD" sorts correctly.
  // We don't have a deterministic clock here (would break the workflow
  // sandbox rule analogue on the JS side); a real backend slices by now().
  const today = "2026-06-26"; // matches createdAt for mocks; replaced live
  const upcoming = all.filter((b) => b.date >= today);
  const past = all.filter((b) => b.date < today);
  return { upcoming, past };
}

async function mockFetchBooking(userId: string, id: string): Promise<BookingSummary | null> {
  const all = await readAll(userId);
  return all.find((b) => b.booking_id === id) ?? null;
}

// ─────────────────────────── public api ───────────────────────────

/** Create a booking. `services` and `venueName` are mock-only context. */
export async function createBooking(
  req: CreateBookingRequest,
  ctx: MockResolveContext,
): Promise<BookingSummary> {
  if (!LIVE_MODE) {
    const r = await mockCreateBooking(req, ctx);
    return r.booking;
  }
  const url = `${env.apiBase.replace(/\/$/, "")}/v1/bookings?tenant_id=${encodeURIComponent(env.tenant)}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`[bookings ${res.status}] create failed: ${await res.text().catch(() => "")}`);
  }
  const parsed = CreateBookingResponseSchema.safeParse(await res.json());
  if (!parsed.success) throw new Error(`[bookings] schema mismatch: ${parsed.error.message}`);
  return parsed.data.booking;
}

export async function fetchUserBookings(userId: string): Promise<UserBookingsResponse> {
  if (!LIVE_MODE) return mockUserBookings(userId);
  return apiGet(
    `/v1/users/${encodeURIComponent(userId)}/bookings?tenant_id=${encodeURIComponent(env.tenant)}`,
    UserBookingsResponseSchema,
  );
}

export async function fetchBooking(userId: string, id: string): Promise<BookingSummary | null> {
  if (!LIVE_MODE) return mockFetchBooking(userId, id);
  return apiGet(
    `/v1/bookings/${encodeURIComponent(id)}?tenant_id=${encodeURIComponent(env.tenant)}`,
    BookingSummarySchema,
  );
}
