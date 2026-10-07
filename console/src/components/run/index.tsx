// The run view: one turn = the task, what the parent decided, the plan, one
// card per agent, and the reply. The site playground has a Preact twin with
// the same names and data attributes (data-turn, data-parent, data-agent).
import { ArrowRight, Bot, ChevronRight, GitFork, OctagonX, ShieldAlert, Wrench } from "lucide-react";
import { useState } from "react";
import { Badge, Eyebrow, Spinner } from "@/components/ui";
import { cx } from "@/lib/format";
import { dash, parentSummary, replySource, statusGlyph, statusTone } from "@/lib/run-view";
import { layers, type AgentCard, type Step, type Turn } from "@/lib/transcript";

export function TurnView({ turn }: { turn: Turn }) {
  const open = turn.outcome === null;
  return (
    <div className="space-y-3" data-turn={turn.run_id}>
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-lg bg-ink px-3 py-2 text-[13px] text-bg">
          {turn.user.text}
        </div>
      </div>

      {turn.parent && <ParentRow turn={turn} />}
      {turn.agents.length > 1 && <Plan turn={turn} />}
      {turn.agents.length > 0 && (
        <div className="grid gap-2 md:grid-cols-2">
          {turn.agents.map((a) => <AgentView key={a.id} a={a} />)}
        </div>
      )}

      {turn.reply && (
        <div className="space-y-1">
          <div className="max-w-[85%] whitespace-pre-wrap rounded-lg border border-line bg-panel px-3 py-2 text-[13px]">
            {turn.reply.text}
          </div>
          <Eyebrow>{replySource(turn.reply.source)}</Eyebrow>
        </div>
      )}
      {turn.error && (
        <Note tone={turn.error.stopped === "killed" ? "warn" : "bad"}
              icon={turn.error.stopped === "killed" ? <OctagonX className="size-3.5" /> : undefined}>
          {turn.error.stopped === "killed" ? `Run stopped: ${turn.error.error}` : turn.error.error}
          {turn.error.hint && <span className="block text-muted">Fix: {turn.error.hint}</span>}
        </Note>
      )}
      {open ? (
        <div className="flex items-center gap-2 text-[12px] text-muted"><Spinner /> working…</div>
      ) : (
        <div className="text-center"><Eyebrow>{`${dash(turn.outcome)} · ${dash(turn.tokens, " tokens")} · ${dash(turn.wall_seconds, "s")}`}</Eyebrow></div>
      )}
    </div>
  );
}

function ParentRow({ turn }: { turn: Turn }) {
  const p = turn.parent!;
  return (
    <div className="flex items-start gap-2 rounded-md border border-dashed border-line-strong px-3 py-2 text-[12px]"
         data-parent={p.kind}>
      <GitFork className="mt-0.5 size-3.5 shrink-0 text-accent" />
      <div>
        <span className="font-medium">Parent</span> {parentSummary(p.kind, p.plan.length)}
        {p.reason && <span className="text-muted"> · {p.reason}</span>}
      </div>
    </div>
  );
}

function Plan({ turn }: { turn: Turn }) {
  const ls = layers(turn.agents);
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-[12px]" data-plan>
      <Eyebrow className="mr-1">plan</Eyebrow>
      {ls.map((layer, i) => (
        <div key={i} className="contents">
          {i > 0 && <ArrowRight className="size-3.5 text-muted" />}
          <div className="flex flex-col gap-1">
            {layer.map((a) => (
              <span key={a.id} className={cx("rounded-full border px-2 py-0.5 font-mono text-[11px]", ring(a.status))}
                    title={`${a.role}: ${a.status}`}>
                <span aria-hidden="true">{statusGlyph(a.status)}</span> {a.role}
                <span className="sr-only"> ({a.status})</span>
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function ring(s: AgentCard["status"]): string {
  switch (s) {
    case "done": return "border-ok text-ok";
    case "failed": return "border-danger text-danger";
    case "killed": return "border-warn text-warn";
    default: return "border-line-strong text-muted";
  }
}

export function AgentView({ a, full }: { a: AgentCard; full?: boolean }) {
  const [showSpec, setShowSpec] = useState(!!full);
  const calls = a.steps.filter((s) => s.kind === "tool_call").length;
  return (
    <div className={cx("rounded-md border bg-panel p-3 text-[12px]", a.status === "running" ? "border-dashed border-line-strong" : "border-line")}
         data-agent={a.id}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1.5 font-medium">
          <Bot className="size-3.5 shrink-0 text-muted" />
          <span className="truncate">{a.role}</span>
          <span className="truncate font-mono text-[11px] font-normal text-muted">
            {a.bundle ? `${a.bundle}${a.version ? `@${a.version}` : ""}` : "invented role"}
          </span>
        </span>
        <Badge tone={statusTone(a.status)}>{a.status}</Badge>
      </div>
      {a.intent && <p className="mt-1 text-ink-2">{a.intent}</p>}
      {a.depends_on.length > 0 && <p className="mt-1 text-muted">after {a.depends_on.join(", ")}</p>}

      <button type="button" aria-expanded={showSpec} onClick={() => setShowSpec(!showSpec)}
              className="-mx-1 mt-1 flex items-center gap-1 rounded-sm px-1 py-1 text-muted hover:text-ink">
        <ChevronRight className={cx("size-3 motion-safe:transition-transform", showSpec && "rotate-90")} />
        spec · {a.tools.length} tool{a.tools.length === 1 ? "" : "s"}
        {a.model?.model && ` · ${a.model.model}`}
      </button>
      {showSpec && (
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded-md bg-sunken p-2 font-mono text-[11px]">
          <dt className="text-muted">id</dt><dd>{a.id}</dd>
          <dt className="text-muted">bundle</dt><dd>{a.bundle ?? "(invented by the parent)"}</dd>
          <dt className="text-muted">tools</dt><dd>{a.tools.join(", ") || "none"}</dd>
          <dt className="text-muted">model</dt><dd>{a.model ? `${a.model.provider} ${a.model.model} (${a.model.source})` : "—"}</dd>
          <dt className="text-muted">depends_on</dt><dd>{a.depends_on.join(", ") || "—"}</dd>
        </dl>
      )}

      {a.steps.length > 0 && (
        <ol className="mt-2 space-y-1">
          {a.steps.map((s, i) => <StepRow key={i} s={s} />)}
        </ol>
      )}

      {a.answer && a.status !== "running" && (
        <p className={cx("mt-2 whitespace-pre-wrap border-t border-line pt-2", !full && "line-clamp-6")}>{a.answer}</p>
      )}
      {a.error && <p className="mt-2 text-danger">{a.error}</p>}
      <p className="mt-2"><Eyebrow>
        {calls} call{calls === 1 ? "" : "s"} · {dash(a.tokens, " tokens")}{a.wall_seconds != null && ` · ${a.wall_seconds}s`}
      </Eyebrow></p>
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
          : `answered without ${s.tool}; asked to look first`}
      </li>
    );
  }
  return (
    <li>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
              className="-mx-1 flex max-w-full items-center gap-1 rounded-sm px-1 py-0.5 text-muted hover:text-ink">
        <ChevronRight className={cx("size-3 shrink-0 motion-safe:transition-transform", open && "rotate-90")} />
        <Wrench className="size-3" /> <span className="font-mono">{s.tool}</span>
        <span className="truncate font-mono text-[11px] text-muted">{argSummary(s.args)}</span>
        {s.ok === false && <span className="text-danger">failed</span>}
        {s.ok === null && <span>running</span>}
      </button>
      {open && (
        <pre className="mt-1 overflow-x-auto rounded-md bg-sunken p-2 font-mono text-[11px]">
          {JSON.stringify(s.args, null, 2)}
        </pre>
      )}
    </li>
  );
}

function argSummary(args: unknown): string {
  if (!args || typeof args !== "object") return "";
  const a = args as Record<string, unknown>;
  const v = a.path ?? a.pattern ?? (Array.isArray(a.argv) ? a.argv.join(" ") : undefined);
  return v === undefined ? "" : String(v).slice(0, 60);
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
