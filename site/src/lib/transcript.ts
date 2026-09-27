// A session's events folded into turns: what the parent decided, which
// agents ran (their spec and steps), and the reply. This is a line-for-line
// port of plnt/tenancy/transcript.py so a live view built event by event
// shows the same thing as GET .../sessions/{sid}/transcript.
//
// The same file lives in console/src/lib and site/src/lib; CI checks that the
// two copies are identical.

export type Ev = {
  seq: number;
  ts: number;
  run_id?: string | null;
  agent_id?: string;
  kind: string;
  payload: Record<string, unknown>;
};

// Payload fields are read with explicit casts below; typing them loosely
// here keeps the fold readable.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Loose = Record<string, any>;

export type ModelInfo = {
  provider?: string;
  model?: string;
  base_url?: string;
  source?: string;
  reason?: string;
};

export type Step =
  | { kind: "tool_call"; step?: number; tool: string; args: unknown; ok: boolean | null }
  | { kind: "guardrail"; tool: string; action: string };

export type AgentStatus = "running" | "done" | "failed" | "killed";

export type AgentCard = {
  id: string;
  role: string;
  bundle: string | null;
  version: string | null;
  intent: string;
  depends_on: string[];
  tools: string[];
  model: ModelInfo | null;
  status: AgentStatus;
  steps: Step[];
  tokens: number;
  wall_seconds: number | null;
  answer: string | null;
  error: string | null;
};

export type PlanEntry = {
  id: string;
  role: string;
  intent: string;
  bundle?: string | null;
  depends_on?: string[];
};

export type ParentDecision = {
  kind: "chat" | "clarify" | "agents" | string;
  reason: string;
  reply: string;
  plan: PlanEntry[];
};

export type Turn = {
  run_id: string;
  ts: number;
  user: { text: string };
  parent: ParentDecision | null;
  agents: AgentCard[];
  reply: { text: string; source: string } | null;
  outcome: string | null;
  tokens: number;
  wall_seconds: number | null;
  error?: { error: string; hint: string; stopped: string };
};

export type Transcript = {
  session_id: string;
  mode: "parent" | "agent";
  bundle: string | null;
  user_id: string;
  title: string;
  workspace: string;
  turns: Turn[];
};

export const PARENT_ID = "parent";

export function foldTurns(events: Ev[]): Turn[] {
  const turns: Turn[] = [];
  let cur: Turn | null = null;
  let agents: Record<string, AgentCard> = {};

  const agent = (aid: string): AgentCard => {
    if (!agents[aid]) {
      agents[aid] = {
        id: aid, role: aid, bundle: null, version: null, intent: "",
        depends_on: [], tools: [], model: null, status: "running",
        steps: [], tokens: 0, wall_seconds: null, answer: null, error: null,
      };
      if (cur) cur.agents.push(agents[aid]);
    }
    return agents[aid];
  };

  for (const e of events) {
    const k = e.kind;
    const p: Loose = e.payload ?? {};
    const aid = e.agent_id ?? "";
    if (k === "user_message") {
      cur = {
        run_id: e.run_id ?? "", ts: e.ts, user: { text: String(p.text ?? "") },
        parent: null, agents: [], reply: null, outcome: null, tokens: 0, wall_seconds: null,
      };
      agents = {};
      turns.push(cur);
      continue;
    }
    if (!cur) continue;
    if (k === "parent_decision") {
      cur.parent = {
        kind: String(p.decision ?? ""), reason: String(p.reason ?? ""),
        reply: String(p.reply ?? ""), plan: (p.agents ?? []) as PlanEntry[],
      };
    } else if (k === "agent_spawned") {
      const a = agent(String(p.agent_id ?? aid));
      Object.assign(a, {
        role: String(p.role ?? a.role), bundle: p.bundle ?? null, version: p.version ?? null,
        intent: String(p.intent ?? ""), depends_on: (p.depends_on ?? []) as string[],
        tools: (p.tools ?? []) as string[], model: (p.model ?? null) as ModelInfo | null,
        status: "running" as AgentStatus,
      });
    } else if (k === "run_started" && cur.agents.length === 0 && p.bundle) {
      // Single-agent session: the bundle itself is the one agent.
      const a = agent(String(p.bundle));
      Object.assign(a, {
        bundle: String(p.bundle), version: p.version ?? null,
        tools: (p.tools ?? []) as string[], model: (p.model ?? null) as ModelInfo | null,
      });
    } else if (aid && aid !== PARENT_ID) {
      const a = agent(aid);
      if (k === "tool_call") {
        a.steps.push({ kind: "tool_call", step: p.step, tool: String(p.tool ?? ""), args: p.args, ok: null });
      } else if (k === "tool_result") {
        for (let i = a.steps.length - 1; i >= 0; i--) {
          const s = a.steps[i];
          if (s.kind === "tool_call" && s.tool === p.tool && s.ok === null) {
            s.ok = Boolean(p.ok);
            break;
          }
        }
      } else if (k === "model_result") {
        a.tokens += Number(p.tokens ?? 0);
      } else if (k === "guardrail") {
        a.steps.push({ kind: "guardrail", tool: String(p.tool ?? ""), action: String(p.action ?? "") });
      } else if (k === "killed") {
        a.status = "killed";
        a.error = p.reason == null ? null : String(p.reason);
      } else if (k === "agent_finished") {
        if (p.outcome === "ok") a.status = "done";
        else if (a.status !== "killed") a.status = "failed";
        a.answer = p.answer == null ? null : String(p.answer);
        a.error = p.error ? String(p.error) : a.error;
        a.tokens = Number(p.tokens ?? a.tokens);
        a.wall_seconds = p.wall_seconds ?? null;
      }
    }
    if (k === "assistant_message") {
      cur.reply = { text: String(p.text ?? ""), source: String(p.source ?? "agent") };
      // Single-agent turns have no agent_finished; the reply closes the agent.
      for (const a of cur.agents) {
        if (a.status === "running") {
          a.status = "done";
          a.answer = a.answer || String(p.text ?? "");
        }
      }
    } else if (k === "run_error") {
      for (const a of cur.agents) {
        if (a.status === "running") {
          a.status = "failed";
          a.error = a.error || String(p.error ?? "");
        }
      }
      cur.error = { error: String(p.error ?? ""), hint: String(p.hint ?? ""), stopped: String(p.stopped ?? "") };
    } else if (k === "run_finished") {
      cur.outcome = String(p.outcome ?? "");
      cur.tokens = Number(p.tokens ?? 0);
      cur.wall_seconds = p.wall_seconds ?? null;
    }
  }
  return turns;
}

/** A turn is open from its user_message until run_finished. */
export function isRunning(turns: Turn[]): boolean {
  const last = turns[turns.length - 1];
  return !!last && last.outcome === null;
}

/** Group a plan/agents list into dependency layers for a left-to-right DAG. */
export function layers<T extends { id: string; depends_on?: string[] }>(items: T[]): T[][] {
  const out: T[][] = [];
  const placed = new Set<string>();
  let rest = items.slice();
  while (rest.length) {
    const ready = rest.filter((a) => (a.depends_on ?? []).every((d) => placed.has(d)));
    const layer = ready.length ? ready : rest; // a cycle never happens; be safe anyway
    out.push(layer);
    layer.forEach((a) => placed.add(a.id));
    rest = rest.filter((a) => !layer.includes(a));
  }
  return out;
}
