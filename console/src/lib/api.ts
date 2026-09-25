// Thin typed client for the plnt /v1 API. Same origin in production
// (served by `plnt serve` at /console); proxied by Vite in dev.

const TOKEN_KEY = "plnt_console_token";

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(token: string): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private mode: token lives only for this page load */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function headers(json = false): HeadersInit {
  const h: Record<string, string> = {};
  const t = getToken();
  if (t) h.Authorization = `Bearer ${t}`;
  if (json) h["Content-Type"] = "application/json";
  return h;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/v1${path}`, {
    method,
    headers: headers(body !== undefined),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : text || res.statusText;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

export const api = {
  get: <T>(p: string) => request<T>("GET", p),
  post: <T>(p: string, b?: unknown) => request<T>("POST", p, b ?? {}),
  put: <T>(p: string, b: unknown) => request<T>("PUT", p, b),
  patch: <T>(p: string, b: unknown) => request<T>("PATCH", p, b),
  del: <T = void>(p: string) => request<T>("DELETE", p),
};

// ------------------------------------------------------------------ types

export type Whoami = { role: "admin" | "dev" } | { role: "tenant"; tenant_id: string };

export type TenantSummary = { id: string; name: string; created_at: number };

export type JsonSchema = {
  type?: string | string[];
  properties?: Record<string, JsonSchema>;
  required?: string[];
  items?: JsonSchema;
  enum?: unknown[];
  default?: unknown;
  description?: string;
  title?: string;
  minLength?: number;
  minimum?: number;
  maximum?: number;
};

export type Install = {
  slug: string;
  version: string;
  enabled: boolean;
  config: Record<string, unknown>;
  installed_at: number;
  source: string;
  digest: string;
  config_schema?: JsonSchema | null;
  secrets_required?: string[];
  description?: string;
  load_error?: string;
};

export type CatalogBundle = {
  slug: string;
  version: string;
  description: string;
  tags: string[];
  tools: string[];
  config_schema: JsonSchema | null;
  secrets: string[];
};

export type ModelConfig = {
  provider: "ollama" | "openai";
  base_url: string;
  model: string;
  deep_model?: string;
  api_key_secret?: string;
  num_ctx?: number;
  temperature?: number;
  cost_in_per_m?: number;
  cost_out_per_m?: number;
};

export type TenantDetail = TenantSummary & {
  installs: Install[];
  secrets: string[];
  model: ModelConfig | null;
};

export type Session = {
  id: string;
  bundle: string;
  user_id: string;
  created_at: number;
  status: "idle" | "running";
};

export type RunEvent = {
  seq: number;
  ts: number;
  run_id: string;
  kind: string;
  payload: Record<string, unknown>;
};

export type Usage = {
  model_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  by_bundle_model: {
    bundle: string;
    model: string;
    model_calls: number;
    prompt_tokens: number;
    completion_tokens: number;
    cost_usd: number;
  }[];
};

export type AuditEvent = { ts: number; action: string } & Record<string, unknown>;

export type ModelHealth = {
  ok: boolean;
  provider?: string;
  base_url?: string;
  model?: string;
  reachable?: boolean;
  model_present?: boolean | null;
  detail?: string;
  hint?: string;
};

// ------------------------------------------------------------------ SSE

/**
 * Stream a session's events. EventSource cannot send an Authorization
 * header, so this reads the SSE response body with fetch. Returns a
 * function that stops the stream.
 */
export function streamEvents(
  tenant: string,
  sid: string,
  after: number,
  onEvent: (e: RunEvent) => void,
  onError: (err: Error) => void,
): () => void {
  const ctrl = new AbortController();
  (async () => {
    const res = await fetch(`/v1/tenants/${tenant}/sessions/${sid}/stream?after=${after}`, {
      headers: headers(),
      signal: ctrl.signal,
    });
    if (!res.ok || !res.body) throw new ApiError(res.status, await res.text());
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1 || (idx = buf.indexOf("\r\n\r\n")) !== -1) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + (buf.startsWith("\r\n", idx) ? 4 : 2));
        const data = chunk
          .split(/\r?\n/)
          .filter((l) => l.startsWith("data:"))
          .map((l) => l.slice(5).trimStart())
          .join("\n");
        if (data) onEvent(JSON.parse(data) as RunEvent);
      }
    }
  })().catch((err: unknown) => {
    if (!ctrl.signal.aborted) onError(err instanceof Error ? err : new Error(String(err)));
  });
  return () => ctrl.abort();
}
