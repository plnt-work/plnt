// Venue detail data — services + team + reviews + availability.
// Mock-first per Console v2 pattern. When MA-P6 endpoints ship,
// flip LIVE_MODE and the components keep their typed contract.
//
// Endpoint shapes (source of truth — coordinate with MA worker before
// changing field names):
//   GET /v1/venues/:placeId/services      → { services: Service[] }
//   GET /v1/venues/:placeId/team          → { team: TeamMember[] }
//   GET /v1/venues/:placeId/reviews       → { reviews: Review[] }
//   GET /v1/venues/:placeId/availability  → { date, slots: string[] }
//     query: ?date=YYYY-MM-DD&service_id=…(repeatable)&pro_id=…
import { z } from "zod";
import { apiGet } from "./client";
import { env } from "@/lib/env";

const LIVE_MODE = true;

export const ServiceSchema = z.object({
  id: z.string(),
  name: z.string(),
  duration_min: z.number(),
  price_cents: z.number(),
  description: z.string().optional(),
});
export type Service = z.infer<typeof ServiceSchema>;

export const TeamMemberSchema = z.object({
  id: z.string(),
  name: z.string(),
  role: z.string(),
  avatar_uri: z.string().optional(),
});
export type TeamMember = z.infer<typeof TeamMemberSchema>;

export const ReviewSchema = z.object({
  id: z.string(),
  author: z.string(),
  rating: z.number(),
  text: z.string(),
  at: z.string(),
});
export type Review = z.infer<typeof ReviewSchema>;

const ServicesResponse = z.object({ services: z.array(ServiceSchema) });
const TeamResponse = z.object({ team: z.array(TeamMemberSchema) });
const ReviewsResponse = z.object({ reviews: z.array(ReviewSchema) });

/** "HH:mm" 24h time of day in the venue's local zone. */
export const SlotSchema = z.string().regex(/^\d{2}:\d{2}$/);
export type Slot = z.infer<typeof SlotSchema>;

export const AvailabilityResponseSchema = z.object({
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  slots: z.array(SlotSchema),
});
export type AvailabilityResponse = z.infer<typeof AvailabilityResponseSchema>;

// ───────────────────────────── mocks ─────────────────────────────

function mockServices(placeId: string): Service[] {
  const seed = placeId.length;
  return [
    { id: "s1", name: "Consultation", duration_min: 30, price_cents: 5000 + seed * 100 },
    { id: "s2", name: "Standard appointment", duration_min: 45, price_cents: 8000 + seed * 100 },
    { id: "s3", name: "Premium appointment", duration_min: 60, price_cents: 12000 + seed * 100 },
  ];
}

function mockTeam(): TeamMember[] {
  return [
    { id: "t1", name: "Asha Iyer", role: "Lead practitioner" },
    { id: "t2", name: "Vikram Rao", role: "Senior associate" },
    { id: "t3", name: "Mira Shah", role: "Associate" },
  ];
}

// Deterministic availability — same inputs → same slot list.
// Hash (date, placeId, sortedServiceIds, proId) → seed a tiny LCG →
// pick slots from a fixed 30-min grid between 09:00 and 19:00.
const SLOT_GRID: Slot[] = (() => {
  const out: Slot[] = [];
  for (let h = 9; h < 19; h++) {
    out.push(`${String(h).padStart(2, "0")}:00`);
    out.push(`${String(h).padStart(2, "0")}:30`);
  }
  return out;
})();

function hashStr(s: string): number {
  // djb2; deterministic across runs.
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
  }
  return h;
}

export function mockAvailability(
  placeId: string,
  date: string,
  serviceIds: string[],
  proId: string,
): AvailabilityResponse {
  const key = `${placeId}|${date}|${[...serviceIds].sort().join(",")}|${proId}`;
  let seed = hashStr(key);
  const out: Slot[] = [];
  for (const slot of SLOT_GRID) {
    // LCG step — deterministic per (key, slot index).
    seed = (seed * 1664525 + 1013904223) >>> 0;
    if (seed % 3 !== 0) out.push(slot); // ~66% availability
  }
  return { date, slots: out };
}

function mockReviews(placeId: string): Review[] {
  return [
    {
      id: `${placeId}-r1`,
      author: "Priya M.",
      rating: 5,
      text: "Easy to book, friendly staff. Will return.",
      at: "2026-05-12",
    },
    {
      id: `${placeId}-r2`,
      author: "Rohan G.",
      rating: 4,
      text: "Solid experience, slightly slow at the front desk.",
      at: "2026-04-28",
    },
  ];
}

// ───────────────────────────── public api ─────────────────────────────

function tenantQS(extra?: Record<string, string> | URLSearchParams): string {
  const qs = new URLSearchParams();
  qs.set("tenant_id", env.tenant);
  if (extra instanceof URLSearchParams) {
    extra.forEach((v, k) => qs.append(k, v));
  } else if (extra) {
    for (const [k, v] of Object.entries(extra)) qs.append(k, v);
  }
  return qs.toString();
}

export async function fetchServices(placeId: string): Promise<Service[]> {
  if (!LIVE_MODE) return mockServices(placeId);
  const r = await apiGet(
    `/v1/venues/${encodeURIComponent(placeId)}/services?${tenantQS()}`,
    ServicesResponse,
  );
  return r.services;
}

export async function fetchTeam(placeId: string): Promise<TeamMember[]> {
  if (!LIVE_MODE) return mockTeam();
  const r = await apiGet(
    `/v1/venues/${encodeURIComponent(placeId)}/team?${tenantQS()}`,
    TeamResponse,
  );
  return r.team;
}

export async function fetchReviews(placeId: string): Promise<Review[]> {
  if (!LIVE_MODE) return mockReviews(placeId);
  const r = await apiGet(
    `/v1/venues/${encodeURIComponent(placeId)}/reviews?${tenantQS()}`,
    ReviewsResponse,
  );
  return r.reviews;
}

export async function fetchAvailability(
  placeId: string,
  date: string,
  serviceIds: string[],
  proId: string,
): Promise<AvailabilityResponse> {
  if (!LIVE_MODE) return mockAvailability(placeId, date, serviceIds, proId);
  const qs = new URLSearchParams();
  qs.set("tenant_id", env.tenant);
  qs.set("date", date);
  qs.set("pro_id", proId);
  for (const id of serviceIds) qs.append("service_id", id);
  return apiGet(
    `/v1/venues/${encodeURIComponent(placeId)}/availability?${qs.toString()}`,
    AvailabilityResponseSchema,
  );
}
