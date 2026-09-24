/**
 * Admin REST client.
 *
 * Hits the same origin (Vite proxies /v1 → uvicorn). Open-default backend
 * (PLNT_CLOUD_REQUIRE_AUTH unset). When the backend is later gated, attach
 * VITE_ADMIN_TOKEN at build time.
 */
const BASE = "/v1/admin";

function headers(): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const token = import.meta.env.VITE_ADMIN_TOKEN as string | undefined;
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export interface TenantSummary {
  tenant_id: string;
  display_name: string;
  created_at: number;
  home: string;
  /** Present only on first provisioning (POST /v1/admin/tenants). Subsequent
   *  list responses never include it. */
  api_key?: string;
}

export interface SessionSummary {
  session_id: string;
  first_ts: number;
  last_ts: number;
  user_id: string;
  message_count: number;
  roles: string[];
}

export interface TenantMetrics {
  tenant_id: string;
  conversation_count: number;
  micro_agent_calls: Record<string, number>;
  memory_turns: number;
  bookings: Record<string, number>;
  last_activity_ts: number | null;
  recent_sessions: SessionSummary[];
}

export interface PlacesStatus {
  enabled: boolean;
  cache: { text_search_rows: number };
  hint: string;
}

export async function listTenants(): Promise<TenantSummary[]> {
  const r = await fetch(`${BASE}/tenants`, { headers: headers() });
  if (!r.ok) throw new Error(`listTenants ${r.status}`);
  return r.json();
}

export async function createTenant(tenantId: string, displayName: string): Promise<TenantSummary> {
  const r = await fetch(`${BASE}/tenants`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ tenant_id: tenantId, display_name: displayName }),
  });
  if (!r.ok) throw new Error(`createTenant ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function getMetrics(tenantId: string): Promise<TenantMetrics> {
  const r = await fetch(`${BASE}/tenants/${encodeURIComponent(tenantId)}/metrics`, {
    headers: headers(),
  });
  if (!r.ok) throw new Error(`getMetrics ${r.status}`);
  return r.json();
}

export async function getPlacesStatus(): Promise<PlacesStatus> {
  const r = await fetch(`${BASE}/services/places`, { headers: headers() });
  if (!r.ok) throw new Error(`getPlacesStatus ${r.status}`);
  return r.json();
}

export async function deleteTenant(tenantId: string): Promise<void> {
  const r = await fetch(`${BASE}/tenants/${encodeURIComponent(tenantId)}`, {
    method: "DELETE", headers: headers(),
  });
  if (!r.ok && r.status !== 404) {
    throw new Error(`deleteTenant ${r.status}: ${await r.text()}`);
  }
}
