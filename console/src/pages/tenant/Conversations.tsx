import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight, Bot, ChevronRight, GitFork, OctagonX, Plus, Send, ShieldAlert, Wrench,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, streamEvents, type RunEvent, type Session, type TenantDetail } from "@/lib/api";
import { Badge, Button, Card, Empty, ErrorNote, Modal, Spinner } from "@/components/ui";
import { cx, fmtTime, inputClass } from "@/lib/format";
import {
  foldTurns, isRunning, layers, type AgentCard, type Step, type Turn,
} from "@/lib/transcript";

const PARENT_LABEL = "Parent (all agents)";

export function Conversations({ tenant }: { tenant: TenantDetail }) {
  const [params, setParams] = useSearchParams();
  const selected = params.get("session");
  const [starting, setStarting] = useState(false);
  const q = useQuery({
    queryKey: ["sessions", tenant.id],
    queryFn: () => api.get<{ sessions: Session[] }>(`/tenants/${tenant.id}/sessions?limit=200`),
    refetchInterval: 5_000,
  });
  const select = (sid: string) => setParams({ tab: "conversations", session: sid });

  return (
    <div className="grid gap-4 md:grid-cols-[280px_1fr]">
      <div className="space-y-2">
        <Button variant="primary" className="w-full" onClick={() => setStarting(true)}
                disabled={!tenant.installs.some((i) => i.enabled)}>
          <Plus className="size-3.5" /> New conversation
        </Button>
        <ErrorNote error={q.error} />
        {q.isPending && <Spinner />}
        <ul className="space-y-1">
          {q.data?.sessions.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => select(s.id)}
                className={cx(
                  "w-full rounded-md border px-3 py-2 text-left text-[13px]",
                  s.id === selected ? "border-accent bg-accent-soft/40" : "border-line bg-panel hover:bg-sunken",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-1.5 truncate font-medium">
                    {s.bundle ? <Bot className="size-3.5 shrink-0 text-muted" /> : <GitFork className="size-3.5 shrink-0 text-muted" />}
                    {s.bundle || "parent"}
                  </span>
                  {s.status === "running" && <Badge tone="warn">running</Badge>}
                </div>
                <div className="mt-0.5 truncate text-[12px] text-muted">
                  {fmtTime(s.created_at)}{s.user_id && ` · ${s.user_id}`}
                </div>
              </button>
            </li>
          ))}
        </ul>
        {q.data?.sessions.length === 0 && <p className="text-[13px] text-muted">No conversations yet.</p>}
      </div>

      {selected ? (
        <Transcript key={selected} tid={tenant.id} sid={selected}
                    session={q.data?.sessions.find((s) => s.id === selected)} />
      ) : (
        <Empty title="Select a conversation">
          Or start one to try this tenant’s agents as its customer would. A parent conversation
          lets the tenant’s parent decide, per message, which agents run.
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
  const m = useMutation({
    mutationFn: () => api.post<{ session_id: string }>(`/tenants/${tenant.id}/sessions`,
                                                       { bundle, user_id: "console" }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ["sessions", tenant.id] });
      onStarted(r.session_id);
      onClose();
    },
  });
  return (
    <Modal open={open} onClose={onClose} title="New conversation">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        <label className="block space-y-1">
          <span className="text-[12px] font-medium">Who answers</span>
          <select className={inputClass} value={bundle} onChange={(e) => setBundle(e.target.value)}>
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

function Transcript({ tid, sid, session }: { tid: string; sid: string; session?: Session }) {
  const qc = useQueryClient();
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [streamError, setStreamError] = useState<Error | null>(null);
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    return streamEvents(
      tid, sid, 0,
      (e) => {
        setEvents((prev) => (prev.length && prev[prev.length - 1].seq >= e.seq ? prev : [...prev, e]));
        if (e.kind === "run_finished") void qc.invalidateQueries({ queryKey: ["sessions", tid] });
      },
      setStreamError,
    );
  }, [tid, sid, qc]);

  const turns = useMemo(() => foldTurns(events), [events]);
  const running = isRunning(turns);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [events.length]);

  const send = useMutation({
    mutationFn: (t: string) => api.post(`/tenants/${tid}/sessions/${sid}/messages`, { text: t }),
    onSuccess: () => setText(""),
  });
  const kill = useMutation({ mutationFn: () => api.post(`/tenants/${tid}/sessions/${sid}/kill`) });
  const title = session ? (session.bundle || PARENT_LABEL) : "Conversation";

  return (
    <Card
      title={<span>{title} <span className="ml-1 font-mono font-normal text-muted">{sid}</span></span>}
      actions={running && (
        <Button variant="danger" busy={kill.isPending} onClick={() => kill.mutate()}>
          <OctagonX className="size-3.5" /> Kill run
        </Button>
      )}
      className="flex min-h-[480px] flex-col"
    >
      <div className="space-y-4">
        <ErrorNote error={streamError ?? send.error ?? kill.error} />
        {turns.length === 0 && <p className="text-[13px] text-muted">No messages yet. Say hello below.</p>}
        {turns.map((t) => <TurnView key={t.run_id || t.ts} turn={t} />)}
        <div ref={bottom} />
      </div>
      <form
        className="sticky bottom-0 mt-4 flex gap-2 border-t border-line bg-panel pt-3"
        onSubmit={(e) => { e.preventDefault(); if (text.trim()) send.mutate(text.trim()); }}
      >
        <input className={inputClass} placeholder="Message as this tenant’s customer…" value={text}
               onChange={(e) => setText(e.target.value)} disabled={running} />
        <Button type="submit" variant="primary" busy={send.isPending} disabled={running || !text.trim()}>
          <Send className="size-3.5" /> Send
        </Button>
      </form>
    </Card>
  );
}

// ------------------------------------------------------------------ run view

export function TurnView({ turn }: { turn: Turn }) {
  const open = turn.outcome === null;
  return (
    <div className="space-y-2" data-turn={turn.run_id}>
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-lg bg-accent px-3 py-2 text-[13px] text-accent-ink">
          {turn.user.text}
        </div>
      </div>

      {turn.parent && <ParentRow turn={turn} />}
      {turn.agents.length > 0 && <Plan turn={turn} />}
      {turn.agents.length > 0 && (
        <div className="grid gap-2 md:grid-cols-2">
          {turn.agents.map((a) => <AgentView key={a.id} a={a} />)}
        </div>
      )}

      {turn.reply && (
        <div className="flex items-end gap-2">
          <div className="max-w-[80%] whitespace-pre-wrap rounded-lg border border-line bg-sunken px-3 py-2 text-[13px]">
            {turn.reply.text}
          </div>
          <span className="pb-1 text-[11px] text-muted">{replySource(turn.reply.source)}</span>
        </div>
      )}
      {turn.error && turn.error.stopped !== "killed" && (
        <Note tone="bad">
          {turn.error.error}
          {turn.error.hint && <span className="block text-muted">Fix: {turn.error.hint}</span>}
        </Note>
      )}
      {turn.error?.stopped === "killed" && (
        <Note tone="bad" icon={<OctagonX className="size-3.5" />}>Run stopped: {turn.error.error}</Note>
      )}
      {open ? (
        <div className="flex items-center gap-2 text-[12px] text-muted"><Spinner /> working…</div>
      ) : (
        <Meta>{`${turn.outcome} · ${turn.tokens} tokens · ${turn.wall_seconds ?? "?"}s`}</Meta>
      )}
    </div>
  );
}

function replySource(source: string): string {
  switch (source) {
    case "synth": return "merged by the parent";
    case "parent": return "parent answered directly";
    case "clarify": return "parent asked for more";
    default: return "agent answered";
  }
}

function ParentRow({ turn }: { turn: Turn }) {
  const p = turn.parent!;
  const n = p.plan.length;
  const what =
    p.kind === "agents" ? `spawned ${n} agent${n === 1 ? "" : "s"}`
    : p.kind === "clarify" ? "asked the customer for more"
    : "answered directly";
  return (
    <div className="flex items-start gap-2 rounded-md border border-dashed border-line px-3 py-2 text-[12px]" data-parent={p.kind}>
      <GitFork className="mt-0.5 size-3.5 shrink-0 text-muted" />
      <div>
        <span className="font-medium">Parent</span> {what}
        {p.reason && <span className="text-muted"> · {p.reason}</span>}
      </div>
    </div>
  );
}

function Plan({ turn }: { turn: Turn }) {
  const ls = layers(turn.agents);
  if (ls.length === 1 && ls[0].length === 1) return null;
  return (
    <div className="flex flex-wrap items-center gap-1 text-[12px]" data-plan>
      {ls.map((layer, i) => (
        <div key={i} className="contents">
          {i > 0 && <ArrowRight className="size-3.5 text-muted" />}
          <div className="flex flex-col gap-1">
            {layer.map((a) => (
              <span key={a.id} className={cx("rounded-full border px-2 py-0.5 font-mono", statusRing(a.status))}>
                {a.role}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function statusRing(s: AgentCard["status"]): string {
  switch (s) {
    case "done": return "border-accent text-accent";
    case "failed": return "border-danger text-danger";
    case "killed": return "border-warn text-warn";
    default: return "border-line text-muted";
  }
}

function statusTone(s: AgentCard["status"]): "good" | "bad" | "warn" | "neutral" {
  return s === "done" ? "good" : s === "failed" ? "bad" : s === "killed" ? "warn" : "neutral";
}

export function AgentView({ a }: { a: AgentCard }) {
  const [showSpec, setShowSpec] = useState(false);
  const calls = a.steps.filter((s) => s.kind === "tool_call").length;
  return (
    <div className="rounded-md border border-line bg-panel p-3 text-[12px]" data-agent={a.id}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1.5 font-medium">
          <Bot className="size-3.5 shrink-0 text-muted" />
          <span className="truncate">{a.role}</span>
          {a.bundle && (
            <span className="truncate font-mono font-normal text-muted">
              {a.bundle}{a.version ? `@${a.version}` : ""}
            </span>
          )}
        </span>
        <Badge tone={statusTone(a.status)}>{a.status}</Badge>
      </div>
      {a.intent && <p className="mt-1 text-muted">{a.intent}</p>}
      {a.depends_on.length > 0 && (
        <p className="mt-1 text-muted">after {a.depends_on.join(", ")}</p>
      )}

      <button onClick={() => setShowSpec(!showSpec)} className="mt-2 flex items-center gap-1 text-muted hover:text-ink">
        <ChevronRight className={cx("size-3 transition-transform", showSpec && "rotate-90")} />
        spec · {a.tools.length} tool{a.tools.length === 1 ? "" : "s"}
        {a.model?.model && ` · ${a.model.model}`}
      </button>
      {showSpec && (
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded-md bg-sunken p-2 font-mono text-[11px]">
          <dt className="text-muted">bundle</dt><dd>{a.bundle ?? "(dynamic role)"}</dd>
          <dt className="text-muted">tools</dt><dd>{a.tools.join(", ") || "none"}</dd>
          <dt className="text-muted">model</dt><dd>{a.model ? `${a.model.provider} ${a.model.model} (${a.model.source})` : "?"}</dd>
          <dt className="text-muted">depends_on</dt><dd>{a.depends_on.join(", ") || "—"}</dd>
        </dl>
      )}

      {a.steps.length > 0 && (
        <ol className="mt-2 space-y-1">
          {a.steps.map((s, i) => <StepRow key={i} s={s} />)}
        </ol>
      )}

      {a.answer && a.status !== "running" && (
        <p className="mt-2 whitespace-pre-wrap border-t border-line pt-2">{a.answer}</p>
      )}
      {a.error && <p className="mt-2 text-danger">{a.error}</p>}
      <p className="mt-2 text-[11px] text-muted">
        {calls} call{calls === 1 ? "" : "s"} · {a.tokens} tokens{a.wall_seconds != null && ` · ${a.wall_seconds}s`}
      </p>
    </div>
  );
}

function StepRow({ s }: { s: Step }) {
  const [open, setOpen] = useState(false);
  if (s.kind === "guardrail") {
    return (
      <li className="flex items-center gap-1 text-warn">
        <ShieldAlert className="size-3" />
        {s.action === "refused"
          ? `answer withheld: skipped ${s.tool} twice`
          : `answered without ${s.tool}; asked to look it up`}
      </li>
    );
  }
  return (
    <li>
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 text-muted hover:text-ink">
        <ChevronRight className={cx("size-3 transition-transform", open && "rotate-90")} />
        <Wrench className="size-3" /> <span className="font-mono">{s.tool}</span>
        {s.ok === false && <span className="text-danger">failed</span>}
        {s.ok === null && <span>…</span>}
      </button>
      {open && (
        <pre className="mt-1 overflow-x-auto rounded-md bg-sunken p-2 font-mono text-[11px]">
          {JSON.stringify(s.args, null, 2)}
        </pre>
      )}
    </li>
  );
}

function Note({ tone, icon, children }: { tone: "warn" | "bad"; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className={cx("flex gap-2 rounded-md px-3 py-2 text-[12px]",
                       tone === "warn" ? "bg-warn-soft text-warn" : "bg-danger-soft text-danger")}>
      {icon && <span className="mt-0.5">{icon}</span>}
      <div>{children}</div>
    </div>
  );
}

function Meta({ children }: { children: React.ReactNode }) {
  return <div className="text-center text-[11px] text-muted">{children}</div>;
}

