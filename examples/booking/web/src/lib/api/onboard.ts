/**
 * Onboard client — typed wrappers around /v1/onboard (slice-5a backend,
 * surface/onboard.py). Mirrors the lib/api/admin-v2.ts pattern.
 *
 * Auth is the httponly `plnt_onboard` cookie set by the OAuth callback;
 * we never read it — same-origin fetches carry it automatically. Any 401
 * means "sign in again"; callers branch on OnboardApiError.status.
 */
const BASE = "/v1/onboard";

export class OnboardApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`onboard ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init);
  if (!r.ok) {
    let detail = "";
    try {
      const body = (await r.json()) as { detail?: string; error?: string };
      detail = body.detail ?? body.error ?? "";
    } catch {
      /* non-JSON body */
    }
    throw new OnboardApiError(r.status, detail || `HTTP ${r.status}`);
  }
  return r.json() as Promise<T>;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/* ─── Google sign-in ────────────────────────────────────────────── */

/** Full-page navigation target — never fetch this for the real flow. */
export const GOOGLE_START_URL = `${BASE}/google/start`;

/**
 * Probe /google/start without following the redirect. 503 means OAuth
 * isn't configured on the server (dev-mode reality); anything else
 * (opaqueredirect on the 302) means it's safe to navigate.
 */
export async function probeGoogleStart(): Promise<"ok" | "unconfigured"> {
  const r = await fetch(GOOGLE_START_URL, { redirect: "manual" });
  return r.status === 503 ? "unconfigured" : "ok";
}

/* ─── me ────────────────────────────────────────────────────────── */

export interface OwnedTenant {
  tenant_id: string;
  business_name: string;
}

export interface Me {
  email: string;
  tenants: OwnedTenant[];
}

export function getMe(): Promise<Me> {
  return request<Me>("/me");
}

/* ─── business search ───────────────────────────────────────────── */

export interface Candidate {
  place_id: string;
  name: string;
  address: string;
  lat: number;
  lng: number;
  category: string;
}

export interface SearchResponse {
  candidates: Candidate[];
}

export function searchBusiness(q: string): Promise<SearchResponse> {
  return request<SearchResponse>(`/search?q=${encodeURIComponent(q)}`);
}

/* ─── claim / create / install ──────────────────────────────────── */

export interface ClaimRequest {
  place_id: string;
  name: string;
  address?: string;
  suggested_slug?: string;
}

export interface ClaimResponse {
  slug: string;
  available: boolean;
}

export function claimBusiness(body: ClaimRequest): Promise<ClaimResponse> {
  return post<ClaimResponse>("/claim", body);
}

export interface CreateRequest {
  slug: string;
  place_id: string;
  name: string;
  address: string;
  lat?: number;
  lng?: number;
}

export interface CreateResponse {
  tenant_id: string;
  /** Shown exactly once — never persisted client-side. */
  api_key: string;
}

export function createTenant(body: CreateRequest): Promise<CreateResponse> {
  return post<CreateResponse>("/create", body);
}

export interface InstallRequest {
  tenant_id: string;
  slug?: string;
  config?: Record<string, unknown>;
}

export function installFirstAgent(body: InstallRequest): Promise<unknown> {
  return post<unknown>("/install", body);
}
