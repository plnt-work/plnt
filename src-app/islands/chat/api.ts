// Same-origin API client. The chat is served from http://127.0.0.1:7777/app/,
// so /v1/* is on the same origin and cookies travel automatically.
import type { Event, IntegrationsMap, SkillDetail, TurnSummary } from './types';

const credentialsSameOrigin: RequestCredentials = 'same-origin';

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (res.status === 401) throw new AuthError('unauthenticated');
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {}
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json() as Promise<T>;
}

export class AuthError extends Error {}

export async function me(): Promise<{ authenticated: boolean; username?: string }> {
  const res = await fetch('/v1/auth/me', { credentials: credentialsSameOrigin });
  return jsonOrThrow(res);
}

export async function login(username: string, password: string): Promise<void> {
  const res = await fetch('/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: credentialsSameOrigin,
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json())?.detail ?? detail;
    } catch {}
    throw new Error(detail);
  }
}

export async function logout(): Promise<void> {
  await fetch('/v1/auth/logout', { method: 'POST', credentials: credentialsSameOrigin });
}

export async function submitIntent(text: string, history: TurnSummary[]): Promise<{ run_id: string }> {
  const res = await fetch('/v1/intents', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: credentialsSameOrigin,
    body: JSON.stringify({
      text,
      history: history.map((t) => ({ prompt: t.prompt, answer: t.answer ?? '' })),
    }),
  });
  return jsonOrThrow(res);
}

export async function listSkills(): Promise<{ skills: string[] }> {
  return jsonOrThrow(await fetch('/v1/skills', { credentials: credentialsSameOrigin }));
}

export async function getSkill(role: string): Promise<SkillDetail> {
  return jsonOrThrow(await fetch(`/v1/skills/${encodeURIComponent(role)}`, { credentials: credentialsSameOrigin }));
}

export async function getIntegrations(): Promise<{ integrations: IntegrationsMap }> {
  return jsonOrThrow(await fetch('/v1/integrations', { credentials: credentialsSameOrigin }));
}

export async function setIntegration(role: string, values: Record<string, unknown>): Promise<void> {
  await jsonOrThrow(
    await fetch(`/v1/integrations/${encodeURIComponent(role)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: credentialsSameOrigin,
      body: JSON.stringify({ values }),
    }),
  );
}

// Open an SSE stream for one run. Returns a cleanup fn.
export function streamRun(
  runId: string,
  onEvent: (e: Event) => void,
  onClose: () => void,
  onAuthError: () => void,
): () => void {
  const es = new EventSource(`/v1/runs/${encodeURIComponent(runId)}/stream`, {
    withCredentials: true,
  });

  const handle = (evt: MessageEvent) => {
    try {
      const data = JSON.parse(evt.data) as Event;
      onEvent(data);
      if (data.kind === 'finished' && !data.agent_id) {
        es.close();
        onClose();
      }
    } catch {
      // ignore malformed
    }
  };

  // sse-starlette emits `event: <kind>` lines so we listen for ALL kinds.
  // Listening on `message` catches the generic `log` kind; named listeners
  // catch the rest.
  const kinds = [
    'intent', 'triage_start', 'triage', 'plan', 'spawn', 'started',
    'tool_call', 'tool_result', 'log', 'model_call', 'model_result',
    'budget_tick', 'result', 'error', 'killed', 'finished', 'answer',
    'fs_change', 'planner_start', 'synth_start',
  ];
  for (const k of kinds) es.addEventListener(k, handle as EventListener);
  es.addEventListener('message', handle as EventListener);

  es.onerror = () => {
    // EventSource auto-reconnects on transient errors. A 401 closes the
    // stream entirely; we don't get a status code, so treat readyState=CLOSED
    // as the auth-failed signal.
    if (es.readyState === EventSource.CLOSED) {
      onAuthError();
    }
  };

  return () => es.close();
}
