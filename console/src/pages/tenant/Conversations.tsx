import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, OctagonX, Plus, Send, ShieldAlert, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, streamEvents, type RunEvent, type Session, type TenantDetail } from "@/lib/api";
import { Badge, Button, Card, Empty, ErrorNote, Modal, Spinner } from "@/components/ui";
import { cx, fmtTime, inputClass } from "@/lib/format";

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
                  <span className="truncate font-medium">{s.bundle}</span>
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
          Or start one to try an installed agent as this tenant’s customer would.
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
  const [bundle, setBundle] = useState("");
  const m = useMutation({
    mutationFn: () => api.post<{ session_id: string }>(`/tenants/${tenant.id}/sessions`,
                                                       { bundle: bundle || enabled[0], user_id: "console" }),
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
          <span className="text-[12px] font-medium">Agent</span>
          <select className={inputClass} value={bundle || enabled[0]} onChange={(e) => setBundle(e.target.value)}>
            {enabled.map((s) => <option key={s}>{s}</option>)}
          </select>
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

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [events.length]);

  // Every turn starts with user_message and ends with run_finished.
  const count = (k: string) => events.filter((e) => e.kind === k).length;
  const running = count("user_message") > count("run_finished");

  const send = useMutation({
    mutationFn: (t: string) => api.post(`/tenants/${tid}/sessions/${sid}/messages`, { text: t }),
    onSuccess: () => setText(""),
  });
  const kill = useMutation({ mutationFn: () => api.post(`/tenants/${tid}/sessions/${sid}/kill`) });

  return (
    <Card
      title={<span>{session?.bundle ?? "Conversation"} <span className="ml-1 font-mono font-normal text-muted">{sid}</span></span>}
      actions={running && (
        <Button variant="danger" busy={kill.isPending} onClick={() => kill.mutate()}>
          <OctagonX className="size-3.5" /> Kill run
        </Button>
      )}
      className="flex min-h-[480px] flex-col"
    >
      <div className="space-y-3">
        <ErrorNote error={streamError ?? send.error ?? kill.error} />
        {events.length === 0 && <p className="text-[13px] text-muted">No messages yet. Say hello below.</p>}
        {events.map((e) => <EventRow key={e.seq} e={e} />)}
        {running && <div className="flex items-center gap-2 text-[12px] text-muted"><Spinner /> working…</div>}
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

function EventRow({ e }: { e: RunEvent }) {
  const p = e.payload as Record<string, unknown>;
  switch (e.kind) {
    case "user_message":
      return (
        <div className="flex justify-end">
          <div className="max-w-[80%] whitespace-pre-wrap rounded-lg bg-accent px-3 py-2 text-[13px] text-accent-ink">
            {String(p.text)}
          </div>
        </div>
      );
    case "assistant_message":
      return (
        <div className="max-w-[80%] whitespace-pre-wrap rounded-lg border border-line bg-sunken px-3 py-2 text-[13px]">
          {String(p.text)}
        </div>
      );
    case "tool_call":
      return <ToolRow name={String(p.tool)} args={p.args} />;
    case "tool_result":
      return p.ok ? null : <div className="pl-6 text-[12px] text-danger">tool returned an error</div>;
    case "guardrail":
      return (
        <Note tone="warn" icon={<ShieldAlert className="size-3.5" />}>
          {p.action === "refused"
            ? `Answer withheld: the model skipped the required ${String(p.tool)} lookup twice.`
            : `The model answered without calling ${String(p.tool)}; asked it to look it up first.`}
          {typeof p.skipped_answer === "string" && p.skipped_answer && (
            <span className="block text-muted">Skipped answer: “{p.skipped_answer}”</span>
          )}
        </Note>
      );
    case "killed":
      return <Note tone="bad" icon={<OctagonX className="size-3.5" />}>Run stopped: {String(p.reason)}</Note>;
    case "run_error":
      return (
        <Note tone="bad">
          {String(p.error)}
          {typeof p.hint === "string" && p.hint && <span className="block text-muted">Fix: {p.hint}</span>}
        </Note>
      );
    case "run_started": {
      const m = (p.model ?? {}) as Record<string, string>;
      return <Meta>{`${String(p.bundle)}@${String(p.version)} · ${m.provider} ${m.model} (${m.source})`}</Meta>;
    }
    case "run_finished":
      return <Meta>{`${String(p.outcome)} · ${String(p.tokens)} tokens · ${String(p.wall_seconds)}s`}</Meta>;
    default:
      return null;
  }
}

function ToolRow({ name, args }: { name: string; args: unknown }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="pl-2 text-[12px]">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 text-muted hover:text-ink">
        <ChevronRight className={cx("size-3 transition-transform", open && "rotate-90")} />
        <Wrench className="size-3" /> called <span className="font-mono">{name}</span>
      </button>
      {open && (
        <pre className="mt-1 overflow-x-auto rounded-md bg-sunken p-2 font-mono text-[11px]">
          {JSON.stringify(args, null, 2)}
        </pre>
      )}
    </div>
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
