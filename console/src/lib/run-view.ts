// Presentation helpers shared by the console (React) and the site playground
// (Preact). Same file in both places; CI checks the copies are identical.
import type { AgentCard, Ev } from "./transcript";

export function replySource(source: string): string {
  switch (source) {
    case "synth": return "merged by the parent";
    case "parent": return "parent answered directly";
    case "clarify": return "parent asked for more";
    default: return "agent answered";
  }
}

export function parentSummary(kind: string, n: number): string {
  if (kind === "agents") return `spawned ${n} agent${n === 1 ? "" : "s"}`;
  if (kind === "clarify") return "asked for more detail";
  return "answered directly";
}

export type Tone = "neutral" | "ok" | "bad" | "warn";

export function statusTone(s: AgentCard["status"]): Tone {
  return s === "done" ? "ok" : s === "failed" ? "bad" : s === "killed" ? "warn" : "neutral";
}

/** One line per raw event, for the Events tab. */
export function summary(e: Ev): string {
  const p = e.payload as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  switch (e.kind) {
    case "user_message":
    case "assistant_message":
      return String(p.text ?? "").slice(0, 100);
    case "run_started":
      return p.mode === "parent"
        ? `parent · ${(p.specialists ?? []).join(", ") || "no specialists"} · ${p.model?.model ?? "?"}`
        : `${p.bundle}@${p.version} · ${p.model?.model ?? "?"}`;
    case "parent_decision":
      return p.decision === "agents"
        ? `spawn ${(p.agents ?? []).map((a: { role: string }) => a.role).join(", ")} — ${p.reason ?? ""}`
        : `${p.decision} — ${p.reason ?? ""}`;
    case "agent_spawned":
      return `${p.role}${p.bundle ? ` (${p.bundle}@${p.version})` : " (invented)"}: ${p.intent ?? ""}`;
    case "agent_finished":
      return `${p.outcome} · ${p.tokens} tok · ${p.wall_seconds}s`;
    case "model_call":
      return `${p.purpose ? p.purpose : `step ${p.step}`} → ${p.model}`;
    case "model_result":
      return `${p.decision_kind} · ${p.tokens} tok · ${p.latency_ms} ms`;
    case "tool_call":
      return `${p.tool}(${Object.entries(p.args ?? {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})`;
    case "tool_result":
      return `${p.tool} ${p.ok ? "ok" : "failed"}`;
    case "guardrail":
      return `answered without ${p.tool}; ${p.action === "refused" ? "answer withheld" : "asked again"}`;
    case "run_error":
    case "model_error":
      return String(p.error ?? p.message ?? "");
    case "killed":
      return String(p.reason ?? "");
    case "run_finished":
      return `${p.outcome} · ${p.tokens} tok · ${p.wall_seconds}s`;
    default:
      return "";
  }
}

export function fmtElapsed(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export function shortId(id: string): string {
  return id.length > 12 ? id.slice(0, 12) : id;
}
