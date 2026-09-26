/** @jsxImportSource preact */
// Live playground: talks to a real `plnt serve --playground` over
// /v1/playground. No canned replies. If the server is unreachable, it says so.
import { useEffect, useMemo, useRef, useState } from 'preact/hooks';

type Agent = {
  slug: string;
  version: string;
  description: string;
  tools: string[];
  require_tool: string | null;
  config: Record<string, unknown>;
};
type DemoTenant = { id: string; name: string; blurb: string; agents: Agent[] };
type Info = {
  tenants: DemoTenant[];
  limits: { max_message_chars: number; messages_per_10min: number; daily_tokens_left: number };
};
type Ev = { seq: number; ts: number; run_id: string | null; kind: string; payload: Record<string, any> };
type Session = { session_id: string; token: string };

const KINDS = [
  'user_message', 'run_started', 'model_call', 'model_result', 'tool_call', 'tool_result',
  'guardrail', 'model_error', 'killed', 'assistant_message', 'run_error', 'run_finished',
];

const PROMPTS: Record<string, string[]> = {
  'support-desk': ['When are you open?', 'Do you take walk-ins on Mondays?', 'Is there parking?'],
  'booking-desk': ['Table for 2 this Saturday at 7:30pm?', 'Can 10 of us come Friday?', 'Cancel my booking'],
};

function apiBase(): string {
  const q = new URLSearchParams(window.location.search).get('api');
  const env = (import.meta.env.PUBLIC_PLNT_PLAYGROUND_URL as string | undefined) ?? '';
  return (q || env || 'http://localhost:8787').replace(/\/+$/, '');
}

async function errText(r: Response): Promise<string> {
  try {
    const j = await r.json();
    return typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j);
  } catch {
    return `HTTP ${r.status}`;
  }
}

function summary(e: Ev): string {
  const p = e.payload;
  switch (e.kind) {
    case 'user_message':
    case 'assistant_message':
      return String(p.text ?? '').slice(0, 80);
    case 'run_started':
      return `${p.bundle}@${p.version} on ${p.model?.model ?? '?'} (${p.model?.provider ?? '?'})`;
    case 'model_call':
      return `step ${p.step} → ${p.model}`;
    case 'model_result':
      return `${p.decision_kind} · ${p.tokens} tok · ${p.latency_ms} ms`;
    case 'tool_call':
      return `${p.tool}(${Object.entries(p.args ?? {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ')})`;
    case 'tool_result':
      return `${p.tool} ${p.ok ? 'ok' : 'failed'}`;
    case 'guardrail':
      return `model answered without calling ${p.tool}; ${p.action === 'refused' ? 'answer withheld' : 'asked again'}`;
    case 'run_error':
    case 'model_error':
      return String(p.error ?? p.message ?? '');
    case 'killed':
      return String(p.reason ?? '');
    case 'run_finished':
      return `${p.outcome} · ${p.tokens} tok · ${p.wall_seconds}s`;
    default:
      return '';
  }
}

function ConfigView({ config }: { config: Record<string, unknown> }) {
  const entries = Object.entries(config).filter(([, v]) => v !== '' && v !== null);
  return (
    <dl class="pg-config">
      {entries.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>
            {Array.isArray(v) && v.every((x) => x && typeof x === 'object' && 'q' in x) ? (
              <ul>
                {(v as { q: string; a: string }[]).map((f) => (
                  <li key={f.q}>
                    <b>{f.q}</b> {f.a}
                  </li>
                ))}
              </ul>
            ) : typeof v === 'object' ? (
              JSON.stringify(v)
            ) : (
              String(v)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default function Playground() {
  const [api, setApi] = useState('');
  const [info, setInfo] = useState<Info | null>(null);
  const [offline, setOffline] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState('');
  const [slug, setSlug] = useState('');
  // One conversation per (tenant, agent), so switching back keeps it: the
  // isolation demo is asking two tenants the same question.
  const [sessions, setSessions] = useState<Record<string, Session>>({});
  const [events, setEvents] = useState<Record<string, Ev[]>>({});
  const [draft, setDraft] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);

  const key = `${tenantId}/${slug}`;
  const session = sessions[key];
  const evs = events[key] ?? [];
  const tenant = info?.tenants.find((t) => t.id === tenantId);
  const agent = tenant?.agents.find((a) => a.slug === slug);

  const load = async (base: string) => {
    setOffline(null);
    try {
      const r = await fetch(`${base}/v1/playground`);
      if (!r.ok) throw new Error(await errText(r));
      const data: Info = await r.json();
      setInfo(data);
      const first = data.tenants[0];
      if (first) {
        setTenantId(first.id);
        setSlug(first.agents.find((a) => a.slug === 'support-desk')?.slug ?? first.agents[0]?.slug ?? '');
      }
    } catch (e) {
      setOffline(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    const base = apiBase();
    setApi(base);
    void load(base);
  }, []);

  // Live event stream for the open conversation.
  useEffect(() => {
    if (!session || !api) return;
    const k = key;
    const last = (events[k] ?? []).at(-1)?.seq ?? 0;
    const url =
      `${api}/v1/playground/sessions/${encodeURIComponent(session.session_id)}/stream` +
      `?token=${session.token}&after=${last}`;
    const es = new EventSource(url);
    const onEvent = (m: MessageEvent) => {
      const e: Ev = JSON.parse(m.data);
      setEvents((all) => {
        const cur = all[k] ?? [];
        if (cur.some((x) => x.seq === e.seq)) return all; // reconnects replay
        return { ...all, [k]: [...cur, e] };
      });
    };
    KINDS.forEach((kind) => es.addEventListener(kind, onEvent as EventListener));
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.session_id, api]);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ block: 'nearest' });
  }, [evs.length]);

  const busy = useMemo(() => {
    let open = false;
    for (const e of evs) {
      if (e.kind === 'user_message') open = true;
      if (e.kind === 'run_finished') open = false;
    }
    return open;
  }, [evs]);

  const send = async (text: string) => {
    const body = text.trim();
    if (!body || !tenant || !agent || busy || sending) return;
    setNotice(null);
    setSending(true);
    try {
      let s = session;
      if (!s) {
        const r = await fetch(`${api}/v1/playground/sessions`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ tenant: tenant.id, bundle: agent.slug }),
        });
        if (!r.ok) throw new Error(await errText(r));
        s = (await r.json()) as Session;
        setSessions((all) => ({ ...all, [key]: s! }));
      }
      const r = await fetch(
        `${api}/v1/playground/sessions/${encodeURIComponent(s.session_id)}/messages?token=${s.token}`,
        { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text: body }) },
      );
      if (!r.ok) throw new Error(await errText(r));
      setDraft('');
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  };

  const kill = async () => {
    if (!session) return;
    await fetch(
      `${api}/v1/playground/sessions/${encodeURIComponent(session.session_id)}/kill?token=${session.token}`,
      { method: 'POST' },
    ).catch(() => undefined);
  };

  if (offline !== null) {
    return (
      <div class="pg-offline container">
        <h1>The playground server is offline</h1>
        <p>
          This page talks to a real plnt server at <code>{api}</code> and could not reach it
          ({offline}). There are no pre-written answers to fall back on.
        </p>
        <p>Run the same playground on your machine with any model:</p>
        <pre><code>{`pip install "git+https://github.com/plnt-work/plnt"
ollama pull qwen2.5:7b          # or set PLNT_CLOUD_URL / PLNT_CLOUD_API_KEY
plnt serve --playground --port 8787`}</code></pre>
        <p>
          then open <a href="?api=http://localhost:8787">this page with <code>?api=http://localhost:8787</code></a>.
        </p>
        <button class="btn" type="button" onClick={() => void load(api)}>Try again</button>
      </div>
    );
  }

  if (!info) return <div class="pg-loading container muted">Connecting to {api}…</div>;

  // A kill already shows as its own note; its run_error would repeat it.
  const chat = evs.filter(
    (e) =>
      ['user_message', 'assistant_message', 'run_error', 'killed', 'guardrail'].includes(e.kind) &&
      !(e.kind === 'run_error' && e.payload.stopped === 'killed'),
  );
  const model = [...evs].reverse().find((e) => e.kind === 'run_started')?.payload.model;

  return (
    <div class="pg">
      <aside class="pg-tenants" aria-label="Demo customers">
        <h2>Customers</h2>
        <p class="muted small">Separate tenants on one server. Each has its own installs, config, data and audit log.</p>
        {info.tenants.map((t) => (
          <div key={t.id} class={`pg-tenant ${t.id === tenantId ? 'on' : ''}`}>
            <div class="name">{t.name}</div>
            <div class="muted small">{t.blurb}</div>
            <div class="agents">
              {t.agents.map((a) => (
                <button
                  type="button"
                  key={a.slug}
                  class={`chip ${t.id === tenantId && a.slug === slug ? 'on' : ''}`}
                  onClick={() => {
                    setTenantId(t.id);
                    setSlug(a.slug);
                    setNotice(null);
                  }}
                >
                  {a.slug}
                </button>
              ))}
            </div>
          </div>
        ))}
        {agent && (
          <details class="pg-install" open>
            <summary>{tenant?.name}’s {agent.slug} install</summary>
            <p class="muted small">
              v{agent.version} · tools: {agent.tools.join(', ') || 'none'}
              {agent.require_tool && <> · must call <code>{agent.require_tool}</code> before answering</>}
            </p>
            <ConfigView config={agent.config} />
          </details>
        )}
      </aside>

      <section class="pg-chat" aria-label="Conversation">
        <header>
          <div>
            <b>{tenant?.name}</b> <span class="muted">· {slug}</span>
          </div>
          <div class="muted small">{model ? `${model.model} · ${model.provider}` : 'model chosen by the server'}</div>
        </header>
        <div class="pg-messages" aria-live="polite">
          {chat.length === 0 && (
            <div class="pg-empty">
              <p class="muted">
                Ask something. Then switch to the other customer and ask the same thing: same agent
                code, different config, separate conversation.
              </p>
              <div class="agents">
                {(PROMPTS[slug] ?? []).map((p) => (
                  <button type="button" class="chip" key={p} onClick={() => void send(p)}>{p}</button>
                ))}
              </div>
            </div>
          )}
          {chat.map((e) =>
            e.kind === 'user_message' ? (
              <div key={e.seq} class="msg user">{e.payload.text}</div>
            ) : e.kind === 'assistant_message' ? (
              <div key={e.seq} class="msg agent">{e.payload.text}</div>
            ) : (
              <div key={e.seq} class={`msg note ${e.kind}`}>
                {e.kind === 'guardrail' ? 'guardrail: ' : e.kind === 'killed' ? 'stopped: ' : 'error: '}
                {summary(e)}
                {e.payload.hint ? ` (${e.payload.hint})` : ''}
              </div>
            ),
          )}
          {busy && <div class="msg agent pending">working…</div>}
          <div ref={chatEnd} />
        </div>
        {notice && <div class="pg-notice" role="alert">{notice}</div>}
        <form
          class="pg-composer"
          onSubmit={(ev) => {
            ev.preventDefault();
            void send(draft);
          }}
        >
          <input
            value={draft}
            maxLength={info.limits.max_message_chars}
            placeholder={`Message ${tenant?.name ?? ''}`}
            aria-label="Message"
            onInput={(ev) => setDraft((ev.target as HTMLInputElement).value)}
          />
          {busy ? (
            <button type="button" class="btn danger" onClick={() => void kill()}>Kill run</button>
          ) : (
            <button type="submit" class="btn primary" disabled={!draft.trim() || sending}>Send</button>
          )}
        </form>
      </section>

      <section class="pg-trace" aria-label="Event trace">
        <h2>Live trace</h2>
        <p class="muted small">Every event the runtime records for this conversation, streamed as it happens.</p>
        <ol>
          {evs.map((e) => (
            <li key={e.seq} class={`k-${e.kind}`}>
              <span class="seq">{e.seq}</span>
              <span class="kind">{e.kind}</span>
              <span class="sum">{summary(e)}</span>
            </li>
          ))}
        </ol>
        {evs.length === 0 && <p class="muted small">No events yet.</p>}
        <p class="muted small pg-limits">
          Limits: {info.limits.max_message_chars} chars per message, {info.limits.messages_per_10min} messages
          per 10 min, {info.limits.daily_tokens_left.toLocaleString()} tokens left today across all visitors.
        </p>
      </section>
    </div>
  );
}
