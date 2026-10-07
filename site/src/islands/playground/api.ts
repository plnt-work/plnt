// The playground's HTTP surface: /v1/playground on a real `plnt serve --playground`.
export type Agent = {
  slug: string;
  version: string;
  description: string;
  tools: string[];
  require_tool: string | null;
  config: Record<string, unknown>;
};
export type Workspace = { name: string; description: string; file_count: number; suggested_tasks: string[] };
export type DemoTenant = { id: string; name: string; blurb: string; workspace: Workspace; agents: Agent[] };
export type Info = {
  tenants: DemoTenant[];
  parent: { description: string; dynamic_roles: boolean };
  execute_enabled: boolean;
  models: { id: string; label: string; provider: string }[];
  limits: { max_message_chars: number; messages_per_10min: number; daily_tokens_left: number };
};

// The hosted playground server (render.yaml). Used when the build has no
// PUBLIC_PLNT_PLAYGROUND_URL and the page is not served from this machine.
const HOSTED_API = 'https://plnt.onrender.com';

export function apiBase(): string {
  const q = new URLSearchParams(window.location.search).get('api');
  const env = (import.meta.env.PUBLIC_PLNT_PLAYGROUND_URL as string | undefined) ?? '';
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);
  return (q || env || (local ? 'http://localhost:8787' : HOSTED_API)).replace(/\/+$/, '');
}

/** An HTTP failure with its status, so the UI can tell a rate limit from a bug. */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** True for "slow down" answers: rate limits and the shared daily budget. */
export function isLimit(e: unknown): boolean {
  return e instanceof ApiError && (e.status === 429 || (e.status === 503 && /budget/.test(e.message)));
}

export async function errText(r: Response): Promise<string> {
  try {
    const j = await r.json();
    return typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j);
  } catch {
    return `HTTP ${r.status}`;
  }
}

export async function fetchInfo(base: string): Promise<Info> {
  const r = await fetch(`${base}/v1/playground`);
  if (!r.ok) throw new Error(await errText(r));
  return (await r.json()) as Info;
}

export async function isUp(base: string): Promise<boolean> {
  // A no-cors request resolves whenever the server answers at all.
  try {
    await fetch(`${base}/v1/health`, { mode: 'no-cors' });
    return true;
  } catch {
    return false;
  }
}

export async function createSession(base: string, tenant: string, bundle = ''): Promise<{ session_id: string; token: string }> {
  const r = await fetch(`${base}/v1/playground/sessions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ tenant, bundle }),
  });
  if (!r.ok) throw new ApiError(r.status, await errText(r));
  return (await r.json()) as { session_id: string; token: string };
}

export async function sendMessage(base: string, sid: string, token: string, text: string): Promise<void> {
  const r = await fetch(`${base}/v1/playground/sessions/${encodeURIComponent(sid)}/messages?token=${token}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) throw new ApiError(r.status, await errText(r));
}

export async function killRun(base: string, sid: string, token: string): Promise<void> {
  const r = await fetch(`${base}/v1/playground/sessions/${encodeURIComponent(sid)}/kill?token=${token}`, { method: 'POST' });
  if (!r.ok) throw new ApiError(r.status, await errText(r));
}

export function streamUrl(base: string, sid: string, token: string, after: number): string {
  return `${base}/v1/playground/sessions/${encodeURIComponent(sid)}/stream?token=${token}&after=${after}`;
}

export const KINDS = [
  'user_message', 'run_started', 'parent_decision', 'agent_spawned', 'model_call', 'model_result',
  'tool_call', 'tool_result', 'guardrail', 'model_error', 'killed', 'agent_finished',
  'assistant_message', 'run_error', 'run_finished',
];
