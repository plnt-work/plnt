import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, FolderGit2, GitFork, OctagonX, Plus, Send } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, streamEvents, type RunEvent, type Session, type StreamState, type TenantDetail } from "@/lib/api";
import { Badge, Button, Card, Empty, ErrorNote, Eyebrow, Modal, Spinner, StatusLight, Tabs } from "@/components/ui";
import { AgentView, TurnView } from "@/components/run";
import { cx, fmtTime, inputClass } from "@/lib/format";
import { fmtElapsed, summary } from "@/lib/run-view";
import { filesOf, foldTurns, isRunning, type Turn } from "@/lib/transcript";

const PARENT_LABEL = "Parent (all agents)";

export function Sessions({ tenant }: { tenant: TenantDetail }) {
  const [params, setParams] = useSearchParams();
  const selected = params.get("session");
  const [starting, setStarting] = useState(false);
  const q = useQuery({
    queryKey: ["sessions", tenant.id],
    queryFn: () => api.get<{ sessions: Session[] }>(`/tenants/${tenant.id}/sessions?limit=200`),
    refetchInterval: 5_000,
  });
  const select = (sid: string) => setParams({ tab: "sessions", session: sid });
  const canStart = tenant.installs.some((i) => i.enabled);

  return (
    <div className="grid gap-4 md:grid-cols-[300px_1fr]">
      <div className="space-y-2">
        <Button variant="primary" className="w-full" onClick={() => setStarting(true)}
                disabled={!canStart} aria-describedby={canStart ? undefined : "no-agents-hint"}>
          <Plus className="size-3.5" /> New session
        </Button>
        {!canStart && (
          <p id="no-agents-hint" className="text-[12px] text-muted">
            No agent is enabled for this tenant. Enable one in the Agents tab first.
          </p>
        )}
        <ErrorNote error={q.error} />
        {q.isPending && <Spinner />}
        <ul className="space-y-1">
          {q.data?.sessions.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => select(s.id)}
                aria-current={s.id === selected ? "true" : undefined}
                className={cx(
                  "w-full rounded-md border px-3 py-2 text-left text-[13px]",
                  s.id === selected ? "border-accent bg-accent-soft/40" : "border-line bg-panel hover:bg-sunken",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-1.5 truncate font-medium">
                    {s.bundle ? <Bot className="size-3.5 shrink-0 text-muted" /> : <GitFork className="size-3.5 shrink-0 text-accent" />}
                    <span className="truncate">{s.title || "New session"}</span>
                  </span>
                  {s.status === "running" && <StatusLight state="live">running</StatusLight>}
                </div>
                <div className="mt-0.5 flex items-center gap-1 truncate text-[11px] text-muted">
                  {s.workspace && <><FolderGit2 className="size-3" /><span className="font-mono">{s.workspace}</span><span>·</span></>}
                  <span>{s.bundle || "parent"}</span>
                  <span>·</span>
                  <span>{fmtTime(s.created_at)}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
        {q.data?.sessions.length === 0 && <p className="text-[13px] text-muted">No sessions yet.</p>}
      </div>

      {selected ? (
        <SessionView key={selected} tid={tenant.id} sid={selected}
                     session={q.data?.sessions.find((s) => s.id === selected)} />
      ) : (
        <Empty title="Select a session">
          Or start one: give the parent a task on a workspace and watch which agents it
          spawns, what each one does, and the merged reply.
        </Empty>
      )}

      <StartSession tenant={tenant} open={starting} onClose={() => setStarting(false)} onStarted={select} />
    </div>
  );
}

function StartSession({ tenant, open, onClose, onStarted }: {
  tenant: TenantDetail;
  open: boolean;
  onClose: () => void;
  onStarted: (sid: string) => void;
}) {
  const qc = useQueryClient();
  const enabled = [...new Set(tenant.installs.filter((i) => i.enabled).map((i) => i.slug))];
  // "" = parent mode: the tenant's parent picks agents per message.
  const [bundle, setBundle] = useState("");
  const [workspace, setWorkspace] = useState("");
  const m = useMutation({
    mutationFn: () => api.post<{ session_id: string }>(`/tenants/${tenant.id}/sessions`,
                                                       { bundle, user_id: "console", workspace: workspace.trim() }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ["sessions", tenant.id] });
      onStarted(r.session_id);
      onClose();
    },
  });
  return (
    <Modal open={open} onClose={onClose} title="New session">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <label className="block space-y-1">
          <span className="text-[12px] font-medium">Workspace</span>
          <input className={cx(inputClass, "font-mono")} value={workspace} placeholder="demo:notes-api · /path/to/repo · https://…/repo.git"
                 onChange={(e) => setWorkspace(e.target.value)} aria-label="Workspace" />
          <span className="block text-[12px] text-muted">
            A private copy is made for this session; the agents work on that copy. Leave empty for no workspace.
          </span>
        </label>
        <label className="block space-y-1">
          <span className="text-[12px] font-medium">Who answers</span>
          <select className={inputClass} value={bundle} onChange={(e) => setBundle(e.target.value)} aria-label="Who answers">
            <option value="">{PARENT_LABEL}</option>
            {enabled.map((s) => <option key={s} value={s}>{s} only</option>)}
          </select>
          <span className="block text-[12px] text-muted">
            {bundle
              ? `Every message goes straight to ${bundle}.`
              : `The parent reads each message and spawns the agents it needs (${enabled.join(", ")}).`}
          </span>
        </label>
        <ErrorNote error={m.error} />
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" busy={m.isPending}>Start</Button>
        </div>
      </form>
    </Modal>
  );
}

type TabId = "run" | "agents" | "files" | "events";
const TABS: { id: TabId; label: string }[] = [
  { id: "run", label: "Run" }, { id: "agents", label: "Agents" }, { id: "files", label: "Files" }, { id: "events", label: "Events" },
];

function SessionView({ tid, sid, session }: { tid: string; sid: string; session?: Session }) {
  const qc = useQueryClient();
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [stream, setStream] = useState<StreamState>("connecting");
  const [streamError, setStreamError] = useState<Error | null>(null);
  const top = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");
  const [tab, setTab] = useState<TabId>("run");
  const [now, setNow] = useState(() => Date.now());
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    return streamEvents(
      tid, sid, 0,
      (e) => {
        setEvents((prev) => (prev.length && prev[prev.length - 1].seq >= e.seq ? prev : [...prev, e]));
        if (e.kind === "run_finished") void qc.invalidateQueries({ queryKey: ["sessions", tid] });
      },
      setStreamError,
      setStream,
      (history) => {
        setEvents(history);
        setLoaded(true);
      },
    );
  }, [tid, sid, qc]);

  // On a narrow screen the list sits above the session: bring the session into view.
  useEffect(() => {
    if (window.matchMedia("(max-width: 767px)").matches) top.current?.scrollIntoView({ block: "start" });
  }, [sid]);

  const turns = useMemo(() => foldTurns(events), [events]);
  const running = isRunning(turns);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [running]);
  useEffect(() => {
    if (tab === "run") bottom.current?.scrollIntoView({ block: "end" });
  }, [events.length, tab]);

  const send = useMutation({
    mutationFn: (t: string) => api.post(`/tenants/${tid}/sessions/${sid}/messages`, { text: t }),
    onSuccess: () => setText(""),
  });
  const kill = useMutation({ mutationFn: () => api.post(`/tenants/${tid}/sessions/${sid}/kill`) });

  const agents = turns.flatMap((t) => t.agents);
  const first = events.find((e) => e.kind === "user_message");
  const last = turns[turns.length - 1];
  const elapsed = first ? (running ? now / 1000 - first.ts : (last?.ts ?? first.ts) - first.ts + (last?.wall_seconds ?? 0)) : 0;
  const title = session?.title || (session ? (session.bundle || PARENT_LABEL) : "—");
  const streamLabel = { connecting: "Connecting…", live: "Live", reconnecting: "Reconnecting…", ended: "Disconnected" }[stream];

  return (
    <div ref={top} className="min-w-0 scroll-mt-4">
    <Card className="flex min-h-[520px] flex-col" title={
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate">{title}</span>
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 font-mono text-[11px] font-normal text-muted">
          {session?.workspace && <span className="flex min-w-0 items-center gap-1"><FolderGit2 className="size-3 shrink-0" /><span className="truncate">{session.workspace}</span></span>}
          <span>{session ? (session.bundle || "parent") : "—"}</span>
          <span className="truncate">{sid}</span>
          <StatusLight state={stream}>{streamLabel}</StatusLight>
        </span>
      </div>
    } actions={
      <>
        <div className="hidden gap-4 sm:flex">
          <HeadStat n={loaded ? agents.length : "—"} label="agents" />
          <HeadStat n={loaded ? turns.length : "—"} label="messages" />
          <HeadStat n={loaded && first ? fmtElapsed(elapsed) : "—"} label="elapsed" />
        </div>
        {running && (
          <Button variant="danger" busy={kill.isPending} onClick={() => kill.mutate()}>
            <OctagonX className="size-3.5" /> Kill run
          </Button>
        )}
      </>
    }>
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      <div className="flex-1 space-y-4 pt-4">
        <ErrorNote error={streamError ?? send.error ?? kill.error} />
        {!loaded && !streamError && (
          <div className="flex items-center gap-2 text-[13px] text-muted" data-loading><Spinner /> Loading the transcript…</div>
        )}
        {loaded && tab === "run" && (
          <>
            {turns.length === 0 && <p className="text-[13px] text-muted">No messages yet. Give the {session?.bundle || "parent"} a task.</p>}
            {turns.map((t) => <TurnView key={t.run_id || t.ts} turn={t} />)}
            <div ref={bottom} />
          </>
        )}
        {loaded && tab === "agents" && <AgentsTab turns={turns} />}
        {loaded && tab === "files" && <FilesTab turns={turns} />}
        {loaded && tab === "events" && <EventsTab events={events} />}
      </div>
      <form
        className="sticky bottom-0 mt-4 flex gap-2 border-t border-line bg-panel pt-3"
        onSubmit={(e) => { e.preventDefault(); if (text.trim()) send.mutate(text.trim()); }}
      >
        <input className={inputClass} value={text}
               placeholder={running ? "A run is in progress. Wait for it, or kill it." : "Give the parent a task…"}
               onChange={(e) => setText(e.target.value)} disabled={running} aria-label="Message" />
        <Button type="submit" variant="primary" busy={send.isPending} disabled={running || !text.trim()}>
          <Send className="size-3.5" /> Send
        </Button>
      </form>
    </Card>
    </div>
  );
}

function HeadStat({ n, label }: { n: number | string; label: string }) {
  return (
    <div className="flex flex-col items-end gap-1 leading-none">
      <span className="font-mono text-[13px] tabular-nums">{n}</span>
      <Eyebrow>{label}</Eyebrow>
    </div>
  );
}

function AgentsTab({ turns }: { turns: Turn[] }) {
  const agents = turns.flatMap((t) => t.agents.map((a) => ({ a, t })));
  if (agents.length === 0) return <Empty title="No agents yet">Agents appear here once the parent spawns them.</Empty>;
  return (
    <div className="space-y-3" data-agents-tab>
      {agents.map(({ a, t }) => (
        <div key={`${t.run_id}/${a.id}`}>
          <Eyebrow className="mb-1 block">turn · {t.user.text.slice(0, 60)}</Eyebrow>
          <AgentView a={a} full />
        </div>
      ))}
    </div>
  );
}

function FilesTab({ turns }: { turns: Turn[] }) {
  const rows = filesOf(turns);
  const runs = turns.flatMap((t) => t.agents.flatMap((a) => a.files.filter((f) => f.op === "run").map((f) => ({ a, f }))));
  if (rows.length === 0 && runs.length === 0) return <Empty title="No files touched yet">Files the agents list, read, search or write show up here.</Empty>;
  return (
    <div className="space-y-4" data-files-tab>
      {rows.length > 0 && (
        <div className="overflow-x-auto">
        <table className="w-full min-w-[28rem] text-[12px]">
          <thead><tr className="text-left"><th className="pb-1"><Eyebrow>path</Eyebrow></th><th className="pb-1"><Eyebrow>ops</Eyebrow></th><th className="pb-1"><Eyebrow>by</Eyebrow></th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.path} className="border-t border-line" data-file={r.path}>
                <td className="py-1 font-mono">{r.path}</td>
                <td className="py-1">{r.ops.map((o) => <Badge key={o} tone={o === "write" ? "warn" : "neutral"}>{o}</Badge>)}</td>
                <td className="py-1 text-muted">{r.agents.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
      {runs.length > 0 && (
        <div>
          <Eyebrow className="mb-1 block">commands run</Eyebrow>
          <ul className="space-y-1 font-mono text-[12px]">
            {runs.map(({ a, f }, i) => <li key={i}><span className="text-muted">{a.role} $ </span>{f.path}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function EventsTab({ events }: { events: RunEvent[] }) {
  if (events.length === 0) return <Empty title="No events yet" />;
  return (
    <ol className="font-mono text-[11px]" data-events-tab>
      {events.map((e) => (
        <li key={e.seq} className="grid grid-cols-[2rem_7.5rem_1fr] gap-2 border-t border-line py-1 sm:grid-cols-[2.5rem_6rem_8rem_1fr]" data-kind={e.kind}>
          <span className="text-muted">{e.seq}</span>
          <span className="hidden truncate text-muted sm:block">{e.agent_id || "—"}</span>
          <span className={cx(
            e.kind === "run_error" || e.kind === "model_error" ? "text-danger"
            : e.kind === "guardrail" || e.kind === "killed" ? "text-warn" : "text-accent-text",
          )}>{e.kind}</span>
          <span className="min-w-0 text-ink-2 [overflow-wrap:anywhere]">{summary(e)}</span>
        </li>
      ))}
    </ol>
  );
}
