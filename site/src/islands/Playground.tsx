/** @jsxImportSource preact */
// Live playground: talks to a real `plnt serve --playground` over
// /v1/playground. No canned replies. If the server is unreachable, it says so.
import { useEffect, useMemo, useRef, useState } from 'preact/hooks';
import { foldTurns, isRunning, layers, type AgentCard, type Ev, type Turn } from '../lib/transcript';

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
  parent?: { description: string; dynamic_roles: boolean };
  limits: { max_message_chars: number; messages_per_10min: number; daily_tokens_left: number };
};
type Session = { session_id: string; token: string };

const KINDS = [
  'user_message', 'run_started', 'parent_decision', 'agent_spawned', 'model_call', 'model_result',
  'tool_call', 'tool_result', 'guardrail', 'model_error', 'killed', 'agent_finished',
  'assistant_message', 'run_error', 'run_finished',
];

// "" is the parent: it reads each message and decides which agents run.
const PARENT = '';

const PROMPTS: Record<string, string[]> = {
  [PARENT]: [
    'Are you open on Saturday, and can I get a table for 2 at 7:30pm?',
    'Do you have parking?',
    'Book 4 of us for Friday 8pm',
  ],
  'support-desk': ['When are you open?', 'Do you take walk-ins on Mondays?', 'Is there parking?'],
  'booking-desk': ['Table for 2 this Saturday at 7:30pm?', 'Can 10 of us come Friday?', 'Cancel my booking'],
};

// The hosted playground server (render.yaml). Used when the build has no
// PUBLIC_PLNT_PLAYGROUND_URL and the page is not served from this machine.
const HOSTED_API = 'https://plnt.onrender.com';

function apiBase(): string {
  const q = new URLSearchParams(window.location.search).get('api');
  const env = (import.meta.env.PUBLIC_PLNT_PLAYGROUND_URL as string | undefined) ?? '';
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);
  return (q || env || (local ? 'http://localhost:8787' : HOSTED_API)).replace(/\/+$/, '');
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
      return p.mode === 'parent'
        ? `parent on ${p.model?.model ?? '?'} (${p.model?.provider ?? '?'})`
        : `${p.bundle}@${p.version} on ${p.model?.model ?? '?'} (${p.model?.provider ?? '?'})`;
    case 'parent_decision':
      return p.decision === 'agents'
        ? `spawn ${(p.agents ?? []).map((a: { role: string }) => a.role).join(', ')} — ${p.reason ?? ''}`
        : `${p.decision} — ${p.reason ?? ''}`;
    case 'agent_spawned':
      return `${p.role}${p.bundle ? ` (${p.bundle}@${p.version})` : ''}: ${p.intent ?? ''}`;
    case 'agent_finished':
      return `${p.outcome} · ${p.tokens} tok · ${p.wall_seconds}s`;
    case 'model_call':
      return `${p.purpose ? p.purpose : `step ${p.step}`} → ${p.model}`;
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

function replySource(source: string): string {
  switch (source) {
    case 'synth': return 'merged by the parent';
    case 'parent': return 'parent answered directly';
    case 'clarify': return 'parent asked for more';
    default: return 'agent answered';
  }
}

function TurnView({ turn }: { turn: Turn }) {
  const p = turn.parent;
  const n = p?.plan.length ?? 0;
  const ls = layers(turn.agents);
  const showPlan = turn.agents.length > 1;
  return (
    <div class="turn" data-turn={turn.run_id}>
      <div class="msg user">{turn.user.text}</div>
      {p && (
        <div class="run-parent" data-parent={p.kind}>
          <b>Parent</b>{' '}
          {p.kind === 'agents'
            ? `spawned ${n} agent${n === 1 ? '' : 's'}`
            : p.kind === 'clarify' ? 'asked the customer for more' : 'answered directly'}
          {p.reason && <span class="muted"> · {p.reason}</span>}
        </div>
      )}
      {showPlan && (
        <div class="run-plan" data-plan>
          {ls.map((layer, i) => (
            <>
              {i > 0 && <span class="arrow">→</span>}
              <div class="layer">
                {layer.map((a) => <span key={a.id} class={`node ${a.status}`}>{a.role}</span>)}
              </div>
            </>
          ))}
        </div>
      )}
      {turn.agents.length > 0 && (
        <div class="run-agents">
          {turn.agents.map((a) => <AgentView key={a.id} a={a} />)}
        </div>
      )}
      {turn.reply && (
        <div class="reply">
          <div class="msg agent">{turn.reply.text}</div>
          <span class="muted small">{replySource(turn.reply.source)}</span>
        </div>
      )}
      {turn.error && (
        <div class={`msg note ${turn.error.stopped === 'killed' ? 'killed' : 'run_error'}`}>
          {turn.error.stopped === 'killed' ? 'stopped: ' : 'error: '}
          {turn.error.error}
          {turn.error.hint ? ` (${turn.error.hint})` : ''}
        </div>
      )}
      {turn.outcome !== null && (
        <div class="run-meta muted small">
          {turn.outcome} · {turn.tokens} tok · {turn.wall_seconds}s
        </div>
      )}
    </div>
  );
}

function AgentView({ a }: { a: AgentCard }) {
  const calls = a.steps.filter((s) => s.kind === 'tool_call').length;
  return (
    <div class={`run-agent ${a.status}`} data-agent={a.id}>
      <div class="head">
        <span class="role">{a.role}</span>
        {a.bundle && <span class="muted small mono">{a.bundle}@{a.version}</span>}
        <span class={`status ${a.status}`}>{a.status}</span>
      </div>
      {a.intent && <p class="intent muted small">{a.intent}</p>}
      <details class="spec small">
        <summary>spec · {a.tools.length} tool{a.tools.length === 1 ? '' : 's'}{a.model?.model ? ` · ${a.model.model}` : ''}</summary>
        <dl class="pg-config">
          <div><dt>bundle</dt><dd>{a.bundle ?? '(dynamic role)'}</dd></div>
          <div><dt>tools</dt><dd>{a.tools.join(', ') || 'none'}</dd></div>
          <div><dt>model</dt><dd>{a.model ? `${a.model.provider} ${a.model.model} (${a.model.source})` : '?'}</dd></div>
          <div><dt>depends_on</dt><dd>{a.depends_on.join(', ') || '—'}</dd></div>
        </dl>
      </details>
      {a.steps.length > 0 && (
        <ol class="steps small">
          {a.steps.map((s, i) =>
            s.kind === 'guardrail' ? (
              <li key={i} class="guardrail">
                {s.action === 'refused' ? `answer withheld: skipped ${s.tool} twice` : `answered without ${s.tool}; asked to look it up`}
              </li>
            ) : (
              <li key={i}>
                <details>
                  <summary>
                    <span class="mono">{s.tool}</span>
                    {s.ok === false && <span class="bad"> failed</span>}
                    {s.ok === null && ' …'}
                  </summary>
                  <pre>{JSON.stringify(s.args, null, 2)}</pre>
                </details>
              </li>
            ),
          )}
        </ol>
      )}
      {a.answer && a.status !== 'running' && <p class="answer">{a.answer}</p>}
      {a.error && <p class="bad small">{a.error}</p>}
      <p class="muted small">
        {calls} call{calls === 1 ? '' : 's'} · {a.tokens} tok{a.wall_seconds != null ? ` · ${a.wall_seconds}s` : ''}
      </p>
    </div>
  );
}

export default function Playground() {
  const [api, setApi] = useState('');
  const [info, setInfo] = useState<Info | null>(null);
  const [offline, setOffline] = useState<string | null>(null);
  const [reachable, setReachable] = useState(false);
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
  const parentMode = slug === PARENT;

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
        setSlug(first.agents.length > 1 ? PARENT : (first.agents[0]?.slug ?? PARENT));
      }
    } catch (e) {
      // Tell "server down" apart from "server up, but not serving this page".
      // A no-cors request resolves whenever the server answers at all.
      let up = false;
      try {
        await fetch(`${base}/v1/health`, { mode: 'no-cors' });
        up = true;
      } catch {
        up = false;
      }
      setReachable(up);
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

  const turns = useMemo(() => foldTurns(evs), [evs]);
  const busy = isRunning(turns);

  const send = async (text: string) => {
    const body = text.trim();
    if (!body || !tenant || (!agent && !parentMode) || busy || sending) return;
    setNotice(null);
    setSending(true);
    try {
      let s = session;
      if (!s) {
        const r = await fetch(`${api}/v1/playground/sessions`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ tenant: tenant.id, bundle: slug }),
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
        {reachable ? (
          <>
            <h1>The playground is not enabled on this server</h1>
            <p>
              The plnt server at <code>{api}</code> is running, but it did not serve the
              playground to this page ({offline}). Either playground mode is off (start it with{' '}
              <code>PLNT_PLAYGROUND=1</code> or <code>--playground</code>), or this site&rsquo;s
              origin <code>{typeof window !== 'undefined' ? window.location.origin : ''}</code> is
              not in <code>PLNT_PLAYGROUND_ORIGINS</code>.
            </p>
          </>
        ) : (
          <>
            <h1>The playground server is offline</h1>
            <p>
              This page talks to a real plnt server at <code>{api}</code> and could not reach it
              ({offline}). There are no pre-written answers to fall back on.
            </p>
          </>
        )}
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

  const model = [...evs].reverse().find((e) => e.kind === 'run_started')?.payload.model as
    | { model?: string; provider?: string }
    | undefined;
  const who = parentMode ? 'parent' : slug;

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
              {[PARENT, ...t.agents.map((a) => a.slug)].map((s) => (
                <button
                  type="button"
                  key={s || 'parent'}
                  class={`chip ${s === PARENT ? 'parent' : ''} ${t.id === tenantId && s === slug ? 'on' : ''}`}
                  title={s === PARENT ? info.parent?.description : undefined}
                  onClick={() => {
                    setTenantId(t.id);
                    setSlug(s);
                    setNotice(null);
                  }}
                >
                  {s === PARENT ? 'parent' : s}
                </button>
              ))}
            </div>
          </div>
        ))}
        {parentMode && tenant && (
          <details class="pg-install" open>
            <summary>{tenant.name}’s parent</summary>
            <p class="muted small">
              One model call per message decides: answer itself, ask for more, or spawn some of{' '}
              {tenant.agents.map((a) => a.slug).join(', ')} with an intent each, in dependency
              order. Their results are merged into the one reply you see.
            </p>
          </details>
        )}
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
            <b>{tenant?.name}</b> <span class="muted">· {who}</span>
          </div>
          <div class="muted small">{model ? `${model.model} · ${model.provider}` : 'model chosen by the server'}</div>
        </header>
        <div class="pg-messages" aria-live="polite">
          {turns.length === 0 && (
            <div class="pg-empty">
              <p class="muted">
                {parentMode
                  ? 'Ask for two things at once and watch the parent split the work between agents.'
                  : 'Ask something. Then switch to the other customer and ask the same thing: same agent code, different config, separate conversation.'}
              </p>
              <div class="agents">
                {(PROMPTS[slug] ?? []).map((p) => (
                  <button type="button" class="chip" key={p} onClick={() => void send(p)}>{p}</button>
                ))}
              </div>
            </div>
          )}
          {turns.map((t) => <TurnView key={t.run_id || t.ts} turn={t} />)}
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
