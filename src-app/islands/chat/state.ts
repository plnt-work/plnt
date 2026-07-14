import { signal } from '@preact/signals';
import type { Event, RunState, SkillDetail, TurnSummary } from './types';
import { newAgentView } from './types';

export const currentRun = signal<RunState | null>(null);
export const history = signal<TurnSummary[]>([]);
export const selectedAgentId = signal<string | null>(null);
export const composerBusy = signal<boolean>(false);
export const skillCache = signal<Record<string, SkillDetail>>({});

export function startRun(runId: string, prompt: string): void {
  const state: RunState = {
    runId,
    prompt,
    startedAt: Date.now(),
    finishedAt: null,
    triageKind: null,
    triageReason: null,
    estimatedAgents: 0,
    spawned: 0,
    completed: 0,
    killed: 0,
    agents: {},
    agentOrder: [],
    answer: null,
    answerSource: null,
  };
  currentRun.value = state;
  selectedAgentId.value = null;
  composerBusy.value = true;
  history.value = [...history.value, { runId, prompt, answer: null }];
}

function asString(v: unknown, fallback = ''): string {
  return typeof v === 'string' ? v : fallback;
}

function asNumber(v: unknown, fallback = 0): number {
  return typeof v === 'number' && Number.isFinite(v) ? v : fallback;
}

function summariseToolResult(payload: Record<string, unknown> | undefined): string {
  if (!payload) return '';
  if (payload.ok === false) return 'err';
  if (typeof payload.hits === 'number') return `${payload.hits} hits`;
  if (typeof payload.exit_code === 'number') return `exit=${payload.exit_code}`;
  if (typeof payload.output_bytes === 'number') return `${payload.output_bytes}B`;
  if (payload.ok === true) return 'ok';
  return '';
}

function summariseLog(payload: Record<string, unknown> | undefined): string {
  if (!payload) return '';
  const raw = (payload.raw as string) || (payload.stderr as string) || (payload.text as string);
  return raw ? String(raw).split('\n').slice(0, 6).join('\n') : '';
}

export function applyEvent(e: Event): void {
  const run = currentRun.value;
  if (!run || run.runId !== e.run_id) return;
  const next = { ...run, agents: { ...run.agents } };

  switch (e.kind) {
    case 'triage': {
      const p = e.payload ?? {};
      next.triageKind = asString(p.kind, null) || null;
      next.triageReason = asString(p.reason, null) || null;
      next.estimatedAgents = asNumber(p.estimated_agents, 0);
      break;
    }
    case 'plan': {
      const p = e.payload ?? {};
      const agents = (p.agents as Array<Record<string, unknown>>) ?? [];
      next.estimatedAgents = asNumber(p.agent_count, agents.length);
      // Pre-create placeholders if planner emitted them with ids.
      for (const a of agents) {
        const id = asString(a.id);
        if (!id || next.agents[id]) continue;
        next.agents[id] = newAgentView({
          id,
          role: asString(a.role, 'agent'),
          dependsOn: Array.isArray(a.depends_on) ? (a.depends_on as string[]) : [],
        });
        next.agentOrder = [...next.agentOrder, id];
      }
      break;
    }
    case 'spawn': {
      const id = e.agent_id ?? asString(e.payload?.id);
      if (!id) break;
      const p = e.payload ?? {};
      const existing = next.agents[id];
      const ag = existing
        ? { ...existing }
        : newAgentView({ id, role: asString(p.role, 'agent') });
      ag.role = asString(p.role, ag.role);
      ag.parentId = asString(p.parent_id, null) || null;
      ag.depth = asNumber(p.depth, 0);
      ag.isolation = asString(p.isolation, 'process');
      ag.modelHint = asString(p.model_hint, 'auto');
      ag.workdir = asString(p.workdir, ag.workdir ?? '') || ag.workdir;
      ag.status = 'spawned';
      next.agents[id] = ag;
      if (!existing) next.agentOrder = [...next.agentOrder, id];
      next.spawned = Object.values(next.agents).length;
      break;
    }
    case 'started': {
      const id = e.agent_id;
      if (id && next.agents[id]) {
        const ag = { ...next.agents[id], status: 'running' as const, startedAt: e.ts * 1000 };
        next.agents[id] = ag;
      }
      break;
    }
    case 'tool_call': {
      const id = e.agent_id;
      if (!id || !next.agents[id]) break;
      const p = e.payload ?? {};
      const ag = { ...next.agents[id], toolCalls: [...next.agents[id].toolCalls] };
      ag.toolCalls.push({
        step: asNumber(p.step, ag.toolCalls.length + 1),
        tool: asString(p.tool, '?'),
        args: (p.args as Record<string, unknown>) ?? {},
        ts: e.ts * 1000,
      });
      const wd = asString(p.workdir, '');
      if (wd && !ag.workdir) ag.workdir = wd;
      next.agents[id] = ag;
      break;
    }
    case 'tool_result': {
      const id = e.agent_id;
      if (!id || !next.agents[id]) break;
      const p = e.payload ?? {};
      const step = asNumber(p.step, 0);
      const ag = { ...next.agents[id], toolCalls: [...next.agents[id].toolCalls] };
      // Match by step number, falling back to the most recent open call.
      let idx = ag.toolCalls.findIndex(
        (c) => c.step === step && c.resultOk === undefined,
      );
      if (idx === -1) {
        for (let i = ag.toolCalls.length - 1; i >= 0; i--) {
          if (ag.toolCalls[i].resultOk === undefined) { idx = i; break; }
        }
      }
      if (idx >= 0) {
        ag.toolCalls[idx] = {
          ...ag.toolCalls[idx],
          resultOk: p.ok === false ? false : true,
          resultSummary: summariseToolResult(p),
          resultTs: e.ts * 1000,
        };
      }
      next.agents[id] = ag;
      break;
    }
    case 'model_call': {
      const id = e.agent_id;
      if (id && next.agents[id]) {
        next.agents[id] = { ...next.agents[id], modelCalls: next.agents[id].modelCalls + 1 };
      }
      break;
    }
    case 'log': {
      const id = e.agent_id;
      if (!id || !next.agents[id]) break;
      const txt = summariseLog(e.payload);
      if (!txt) break;
      const lines = [...next.agents[id].logLines, txt];
      next.agents[id] = { ...next.agents[id], logLines: lines.slice(-50) };
      break;
    }
    case 'fs_change': {
      const id = e.agent_id;
      if (!id || !next.agents[id]) break;
      const p = e.payload ?? {};
      const files = Array.isArray(p.files) ? (p.files as string[]) : next.agents[id].files;
      next.agents[id] = {
        ...next.agents[id],
        files,
        fileCount: asNumber(p.file_count, files.length),
        workdir: asString(p.workdir, next.agents[id].workdir ?? '') || next.agents[id].workdir,
      };
      break;
    }
    case 'killed': {
      const id = e.agent_id;
      if (!id || !next.agents[id]) break;
      next.agents[id] = {
        ...next.agents[id],
        status: 'killed',
        killReason: asString(e.payload?.reason, null) || asString(e.payload?.kill_reason, null),
        finishedAt: e.ts * 1000,
      };
      next.killed += 1;
      break;
    }
    case 'error': {
      const id = e.agent_id;
      if (id && next.agents[id]) {
        next.agents[id] = {
          ...next.agents[id],
          status: 'error',
          errorReason: asString(e.payload?.reason, null),
          finishedAt: e.ts * 1000,
        };
      }
      break;
    }
    case 'result': {
      const id = e.agent_id;
      if (!id || !next.agents[id]) break;
      next.agents[id] = {
        ...next.agents[id],
        status: 'done',
        output: (e.payload?.output as Record<string, unknown>) ?? null,
      };
      break;
    }
    case 'finished': {
      const id = e.agent_id;
      if (id) {
        // per-agent finished
        if (next.agents[id]) {
          const p = e.payload ?? {};
          next.agents[id] = {
            ...next.agents[id],
            finishedAt: e.ts * 1000,
            workdir: asString(p.workdir, next.agents[id].workdir ?? '') || next.agents[id].workdir,
            files: Array.isArray(p.files_written) ? (p.files_written as string[]) : next.agents[id].files,
            fileCount: asNumber(p.file_count, next.agents[id].fileCount),
          };
          if (next.agents[id].status !== 'killed' && next.agents[id].status !== 'error') {
            next.agents[id].status = 'done';
          }
        }
      } else {
        // run-level finished
        const p = e.payload ?? {};
        next.finishedAt = e.ts * 1000;
        next.spawned = asNumber(p.spawned, next.spawned);
        next.completed = asNumber(p.completed, next.completed);
        next.killed = asNumber(p.killed, next.killed);
        composerBusy.value = false;
      }
      break;
    }
    case 'answer': {
      const p = e.payload ?? {};
      next.answer = asString(p.text, '');
      next.answerSource = asString(p.source, '');
      const last = history.value[history.value.length - 1];
      if (last && last.runId === next.runId) {
        history.value = [
          ...history.value.slice(0, -1),
          { ...last, answer: next.answer },
        ];
      }
      break;
    }
  }

  currentRun.value = next;
}

export function resetForNewSession(): void {
  currentRun.value = null;
  history.value = [];
  selectedAgentId.value = null;
  composerBusy.value = false;
}
