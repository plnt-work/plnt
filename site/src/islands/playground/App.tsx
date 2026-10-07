/** @jsxImportSource preact */
// Live playground: a real `plnt serve --playground` over /v1/playground.
// No canned replies. If the server is unreachable, it says so.
import { useEffect, useMemo, useRef, useState } from 'preact/hooks';
import { fmtElapsed, summary } from '../../lib/run-view';
import { filesOf, foldTurns, isRunning, type Ev, type Turn } from '../../lib/transcript';
import { AgentView, TurnView } from '../run';
import { apiBase, createSession, fetchInfo, isLimit, isUp, killRun, sendMessage, streamUrl, KINDS, type Info } from './api';
import { loadSessions, saveSessions, type Stored } from './store';

type Tab = 'run' | 'agents' | 'files' | 'events';
const TABS: { id: Tab; label: string }[] = [
  { id: 'run', label: 'Run' }, { id: 'agents', label: 'Agents' }, { id: 'files', label: 'Files' }, { id: 'events', label: 'Events' },
];

export default function Playground() {
  const [api, setApi] = useState('');
  const [info, setInfo] = useState<Info | null>(null);
  const [offline, setOffline] = useState<string | null>(null);
  const [reachable, setReachable] = useState(false);
  const [sessions, setSessions] = useState<Stored[]>([]);
  const [current, setCurrent] = useState<string | null>(null); // session_id
  const [events, setEvents] = useState<Record<string, Ev[]>>({});
  const [tab, setTab] = useState<Tab>('run');
  const [draft, setDraft] = useState('');
  const [notice, setNotice] = useState<{ text: string; limit?: boolean } | null>(null);
  // Event stream state for the open session, shown as the status light.
  const [stream, setStream] = useState<'live' | 'reconnecting' | 'ended'>('ended');
  const [sending, setSending] = useState(false);
  const [composing, setComposing] = useState<{ tenant: string; bundle: string } | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const chatEnd = useRef<HTMLDivElement>(null);

  const session = sessions.find((s) => s.session_id === current) ?? null;
  const evs = (current ? events[current] : undefined) ?? [];
  const turns = useMemo(() => foldTurns(evs), [evs]);
  const busy = isRunning(turns);
  const tenant = info?.tenants.find((t) => t.id === (session?.tenant ?? composing?.tenant));

  const load = async (base: string) => {
    setOffline(null);
    try {
      const data = await fetchInfo(base);
      setInfo(data);
      const stored = loadSessions();
      setSessions(stored);
      const params = new URLSearchParams(window.location.search);
      const wantTenant = params.get('tenant');
      const wantTask = params.get('task');
      if (wantTenant && data.tenants.some((t) => t.id === wantTenant)) {
        setComposing({ tenant: wantTenant, bundle: '' });
        if (wantTask) setDraft(wantTask);
      } else if (stored.length && !stored[0].expired) {
        setCurrent(stored[0].session_id);
      } else {
        setComposing({ tenant: data.tenants[0]?.id ?? '', bundle: '' });
      }
    } catch (e) {
      setReachable(await isUp(base));
      setOffline(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    const base = apiBase();
    setApi(base);
    void load(base);
  }, []);

  // Live event stream for the open session.
  useEffect(() => {
    if (!session || !api || session.expired) return;
    const sid = session.session_id;
    const last = (events[sid] ?? []).at(-1)?.seq ?? 0;
    const es = new EventSource(streamUrl(api, sid, session.token, last));
    es.onopen = () => setStream('live');
    const onEvent = (m: MessageEvent) => {
      const e: Ev = JSON.parse(m.data);
      setEvents((all) => {
        const cur = all[sid] ?? [];
        if (cur.some((x) => x.seq === e.seq)) return all; // reconnects replay
        return { ...all, [sid]: [...cur, e] };
      });
    };
    es.onerror = () => {
      // CONNECTING: the browser is retrying a dropped connection; say so.
      // CLOSED: the server refused the stream (restarted, or the token
      // expired), so the session is gone; keep its title, mark it expired.
      if (es.readyState === EventSource.CLOSED) {
        setStream('ended');
        markExpired(sid);
      } else {
        setStream('reconnecting');
      }
    };
    KINDS.forEach((kind) => es.addEventListener(kind, onEvent as EventListener));
    return () => {
      es.close();
      setStream('ended');
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.session_id, api]);

  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [busy]);

  useEffect(() => {
    if (tab === 'run') chatEnd.current?.scrollIntoView({ block: 'nearest' });
  }, [evs.length, tab]);

  const markExpired = (sid: string) =>
    setSessions((all) => {
      const next = all.map((s) => (s.session_id === sid ? { ...s, expired: true } : s));
      saveSessions(next);
      return next;
    });

  const startSession = async (tenantId: string, bundle: string, firstMessage?: string) => {
    if (!api || !info) return null;
    const t = info.tenants.find((x) => x.id === tenantId);
    if (!t) return null;
    const s = await createSession(api, tenantId, bundle);
    const stored: Stored = {
      session_id: s.session_id, token: s.token, tenant: tenantId, workspace: t.workspace.name,
      bundle, title: firstMessage ?? '', created: Date.now(),
    };
    setSessions((all) => {
      const next = [stored, ...all.filter((x) => x.session_id !== stored.session_id)];
      saveSessions(next);
      return next;
    });
    setCurrent(stored.session_id);
    setComposing(null);
    setTab('run');
    return stored;
  };

  const send = async (text: string) => {
    const body = text.trim();
    if (!body || busy || sending) return;
    setNotice(null);
    setSending(true);
    try {
      let s = session;
      if (!s || s.expired) {
        const c = composing ?? { tenant: s?.tenant ?? info?.tenants[0]?.id ?? '', bundle: s?.bundle ?? '' };
        s = await startSession(c.tenant, c.bundle, body);
        if (!s) return;
      } else if (!s.title) {
        const sid = s.session_id;
        setSessions((all) => {
          const next = all.map((x) => (x.session_id === sid ? { ...x, title: body } : x));
          saveSessions(next);
          return next;
        });
      }
      try {
        await sendMessage(api, s.session_id, s.token, body);
      } catch (e) {
        if (String(e).includes('unknown playground session')) {
          markExpired(s.session_id);
          throw new Error('This session expired on the server. Start a new one.');
        }
        throw e;
      }
      setDraft('');
    } catch (e) {
      setNotice({ text: e instanceof Error ? e.message : String(e), limit: isLimit(e) });
    } finally {
      setSending(false);
    }
  };

  const restart = async () => {
    if (!session) return;
    setComposing({ tenant: session.tenant, bundle: session.bundle });
    setCurrent(null);
    setDraft('');
    setNotice(null);
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

  const agents = turns.flatMap((t) => t.agents);
  const first = evs.find((e) => e.kind === 'user_message');
  const lastTurn = turns[turns.length - 1];
  const elapsed = first
    ? busy ? now / 1000 - first.ts : (lastTurn?.ts ?? first.ts) - first.ts + (lastTurn?.wall_seconds ?? 0)
    : 0;
  const model = info.models[0];
  const showComposeCard = !session || session.expired;
  const active = !!session && !session.expired;
  const budgetGone = info.limits.daily_tokens_left <= 0;
  const blocked = busy
    ? 'A run is in progress. Wait for it to finish, or kill it.'
    : budgetGone
      ? 'The shared daily budget is used up.'
      : '';
  const kill = async () => {
    if (!session) return;
    try {
      await killRun(api, session.session_id, session.token);
    } catch (e) {
      setNotice({ text: `Could not stop the run: ${e instanceof Error ? e.message : String(e)}` });
    }
  };

  return (
    <div class="pg">
      <aside class="pg-side" aria-label="Sessions">
        <div class="pg-current">
          <span class="eyebrow">{showComposeCard ? 'New session' : 'Current session'}</span>
          {showComposeCard ? (
            <NewSession
              info={info}
              tenant={composing?.tenant ?? tenant?.id ?? info.tenants[0]?.id ?? ''}
              bundle={composing?.bundle ?? ''}
              onChange={(t, b) => setComposing({ tenant: t, bundle: b })}
              onPreset={(task) => setDraft(task)}
            />
          ) : (
            <>
              <h2 class="pg-title">{session.title || 'Untitled'}</h2>
              <div class="pg-facts">
                <div><span class="eyebrow">workspace</span><span class="mono">{session.workspace}</span></div>
                <div><span class="eyebrow">mode</span><span>{session.bundle ? `${session.bundle} only` : 'parent decides'}</span></div>
                <div><span class="eyebrow">model</span><span class="mono">{model ? model.id : 'server default'}</span></div>
                <div><span class="eyebrow">tools</span><span>{info.execute_enabled ? 'read, write, run' : 'read-only here'}</span></div>
              </div>
              {tenant && (
                <details class="pg-install">
                  <summary>{tenant.workspace.name}: {tenant.workspace.file_count} files, {tenant.agents.length} agents installed</summary>
                  <p class="muted small">{tenant.workspace.description}</p>
                  <ul class="small">
                    {tenant.agents.map((a) => (
                      <li key={a.slug}><b>{a.slug}</b> <span class="muted">{a.description}</span></li>
                    ))}
                  </ul>
                </details>
              )}
              <button type="button" class="btn primary wide" onClick={() => void restart()}>+ New session</button>
            </>
          )}
        </div>

        {sessions.length > 0 && (
          <div class="pg-list">
            <span class="eyebrow">Your sessions</span>
            <ul>
              {sessions.map((s) => (
                <li key={s.session_id}>
                  <button
                    type="button"
                    aria-current={s.session_id === current ? 'true' : undefined}
                    class={`row ${s.session_id === current ? 'on' : ''} ${s.expired ? 'expired' : ''}`}
                    onClick={() => { setCurrent(s.session_id); setComposing(null); setNotice(null); setTab('run'); }}
                  >
                    <span class="t">{s.title || 'Untitled'}</span>
                    <span class="mono muted small">{s.workspace} · {s.bundle || 'parent'}{s.expired ? ' · expired' : ''}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        <p class="muted small pg-limits">
          {info.limits.max_message_chars} chars per message · {info.limits.messages_per_10min} messages per 10 min ·{' '}
          {info.limits.daily_tokens_left.toLocaleString()} tokens left today for all visitors.
        </p>
      </aside>

      <section class="pg-main" aria-label="Session">
        <header class="pg-head">
          <div class="min">
            <span class="eyebrow">{active ? `session · ${session.session_id.split('.').pop()}` : 'new session'}</span>
            <h1>{active ? session.title || 'Untitled' : tenant ? `${tenant.workspace.name} — give the parent a task` : 'Give the parent a task'}</h1>
            {active && (
              <span class="status-light" data-state={stream} data-stream={stream}>
                {stream === 'live' ? 'Live' : stream === 'reconnecting' ? 'Reconnecting…' : 'Not connected'}
              </span>
            )}
          </div>
          <div class="stats">
            <div><b>{active ? agents.length : '—'}</b><span class="eyebrow">agents</span></div>
            <div><b>{active ? turns.length : '—'}</b><span class="eyebrow">messages</span></div>
            <div><b class="mono">{active && first ? fmtElapsed(elapsed) : '—'}</b><span class="eyebrow">elapsed</span></div>
            {busy ? (
              <button type="button" class="btn danger" onClick={() => void kill()}>Kill run</button>
            ) : (
              session && !session.expired && <button type="button" class="btn" onClick={() => void restart()}>↺ Restart</button>
            )}
          </div>
        </header>

        <nav class="pg-tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t.id} role="tab" type="button" aria-selected={tab === t.id} class={tab === t.id ? 'on' : ''} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>

        <div class="pg-body" aria-live="polite">
          {tab === 'run' && (
            <>
              {turns.length === 0 && (
                <div class="pg-empty">
                  <p class="muted">
                    {tenant
                      ? `The parent reads your task, decides which of ${tenant.agents.map((a) => a.slug).join(', ')} to spawn (and what each should do), runs them on a private copy of ${tenant.workspace.name}, and merges the result.`
                      : 'Pick a workspace on the left.'}
                  </p>
                  {tenant && (
                    <div class="agents">
                      {tenant.workspace.suggested_tasks.map((p) => (
                        <button type="button" class="chip" key={p} onClick={() => void send(p)}>{p}</button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {turns.map((t) => <TurnView key={t.run_id || t.ts} turn={t} />)}
              <div ref={chatEnd} />
            </>
          )}
          {tab === 'agents' && <AgentsTab turns={turns} />}
          {tab === 'files' && <FilesTab turns={turns} />}
          {tab === 'events' && <EventsTab evs={evs} />}
        </div>

        {budgetGone && !notice && (
          <div class="pg-notice info" role="status">
            The playground&rsquo;s shared model budget for today is used up. It resets tomorrow. Meanwhile you can run
            the same playground on your machine: <a href="/docs/getting-started/quickstart/">quickstart</a>.
          </div>
        )}
        {notice && (
          <div class={`pg-notice ${notice.limit ? 'info' : ''}`} role="alert">
            {notice.limit ? `Slow down: ${notice.text}.` : notice.text}
          </div>
        )}
        <form
          class="pg-composer"
          onSubmit={(ev) => {
            ev.preventDefault();
            void send(draft);
          }}
        >
          <textarea
            value={draft}
            rows={2}
            maxLength={info.limits.max_message_chars}
            disabled={budgetGone}
            placeholder={blocked || (active ? 'Follow up…' : `Give the parent a task on ${tenant?.workspace.name ?? 'the workspace'}…`)}
            aria-label="Message"
            onInput={(ev) => setDraft((ev.target as HTMLTextAreaElement).value)}
            onKeyDown={(ev) => {
              if (ev.key === 'Enter' && !ev.shiftKey) {
                ev.preventDefault();
                void send(draft);
              }
            }}
          />
          <button type="submit" class="btn primary" disabled={!draft.trim() || sending || busy || budgetGone} title={blocked || (draft.trim() ? undefined : 'Type a task first')}>
            {sending ? 'Sending…' : 'Send'}
          </button>
        </form>
      </section>
    </div>
  );
}

function NewSession({ info, tenant, bundle, onChange, onPreset }: {
  info: Info;
  tenant: string;
  bundle: string;
  onChange: (tenant: string, bundle: string) => void;
  onPreset: (task: string) => void;
}) {
  const t = info.tenants.find((x) => x.id === tenant) ?? info.tenants[0];
  const model = info.models[0];
  return (
    <div class="pg-new">
      <label>
        <span class="eyebrow">Workspace</span>
        <select value={t?.id} onChange={(e) => onChange((e.target as HTMLSelectElement).value, bundle)} aria-label="Workspace">
          {info.tenants.map((x) => <option key={x.id} value={x.id}>{x.workspace.name} · {x.workspace.file_count} files</option>)}
        </select>
      </label>
      {t && <p class="muted small">{t.workspace.description}</p>}
      <label>
        <span class="eyebrow">Who answers</span>
        <select value={bundle} onChange={(e) => onChange(t?.id ?? tenant, (e.target as HTMLSelectElement).value)} aria-label="Who answers">
          <option value="">parent decides which agents run</option>
          {t?.agents.map((a) => <option key={a.slug} value={a.slug}>{a.slug} only</option>)}
        </select>
      </label>
      <label>
        <span class="eyebrow">Model</span>
        <select disabled aria-label="Model" aria-describedby="pg-model-why"><option>{model ? `${model.id} (${model.provider})` : 'server default'}</option></select>
        <span id="pg-model-why" class="muted small">Set by the server for everyone on the playground.</span>
      </label>
      {t && (
        <div class="presets">
          <span class="eyebrow">Try</span>
          {t.workspace.suggested_tasks.map((p) => (
            <button type="button" class="chip" key={p} onClick={() => onPreset(p)}>{p}</button>
          ))}
        </div>
      )}
      <p class="muted small">Type a task below and press Send to start.</p>
    </div>
  );
}

function AgentsTab({ turns }: { turns: Turn[] }) {
  const agents = turns.flatMap((t) => t.agents.map((a) => ({ a, t })));
  if (agents.length === 0) return <p class="muted pg-empty">Agents appear here once the parent spawns them.</p>;
  return (
    <div class="pg-agents-tab" data-agents-tab>
      {agents.map(({ a, t }) => (
        <div key={`${t.run_id}/${a.id}`}>
          <span class="eyebrow">turn · {t.user.text.slice(0, 60)}</span>
          <AgentView a={a} full />
        </div>
      ))}
    </div>
  );
}

function FilesTab({ turns }: { turns: Turn[] }) {
  const rows = filesOf(turns);
  const runs = turns.flatMap((t) => t.agents.flatMap((a) => a.files.filter((f) => f.op === 'run').map((f) => ({ a, f }))));
  if (rows.length === 0 && runs.length === 0) return <p class="muted pg-empty">Files the agents list, read, search or write show up here.</p>;
  return (
    <div class="pg-files" data-files-tab>
      {rows.length > 0 && (
        <table>
          <thead><tr><th class="eyebrow">path</th><th class="eyebrow">ops</th><th class="eyebrow">by</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.path} data-file={r.path}>
                <td class="mono">{r.path}</td>
                <td>{r.ops.map((o) => <span key={o} class={`pill ${o === 'write' ? 'warn' : ''}`}>{o}</span>)}</td>
                <td class="muted">{r.agents.join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {runs.length > 0 && (
        <div>
          <span class="eyebrow">commands run</span>
          <ul class="mono small">
            {runs.map(({ a, f }, i) => <li key={i}><span class="muted">{a.role} $ </span>{f.path}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function EventsTab({ evs }: { evs: Ev[] }) {
  if (evs.length === 0) return <p class="muted pg-empty">No events yet.</p>;
  return (
    <ol class="pg-trace" data-events-tab>
      {evs.map((e) => (
        <li key={e.seq} class={`k-${e.kind}`} data-kind={e.kind}>
          <span class="seq">{e.seq}</span>
          <span class="who">{e.agent_id || '—'}</span>
          <span class="kind">{e.kind}</span>
          <span class="sum">{summary(e)}</span>
        </li>
      ))}
    </ol>
  );
}
