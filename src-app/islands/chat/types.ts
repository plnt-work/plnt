// Plnt event + state types mirroring plnt-tui/internal/ui/agents.go.

export type EventKind =
  | 'intent'
  | 'triage_start'
  | 'triage'
  | 'plan'
  | 'spawn'
  | 'started'
  | 'tool_call'
  | 'tool_result'
  | 'log'
  | 'model_call'
  | 'model_result'
  | 'budget_tick'
  | 'result'
  | 'error'
  | 'killed'
  | 'finished'
  | 'answer'
  | 'fs_change'
  | 'planner_start'
  | 'synth_start';

export interface Event {
  ts: number;
  run_id: string;
  kind: EventKind | string;
  agent_id?: string;
  payload?: Record<string, unknown> & { _spilled?: string; _bytes?: number };
}

export type AgentStatus = 'pending' | 'spawned' | 'running' | 'done' | 'killed' | 'error';

export interface ToolCallRecord {
  step: number;
  tool: string;
  args: Record<string, unknown>;
  ts: number;
  resultOk?: boolean;
  resultSummary?: string;
  resultTs?: number;
}

export interface AgentView {
  id: string;
  role: string;
  parentId: string | null;
  depth: number;
  status: AgentStatus;
  isolation: string;
  modelHint: string;
  dependsOn: string[];
  toolCalls: ToolCallRecord[];
  modelCalls: number;
  logLines: string[];
  workdir: string | null;
  files: string[];
  fileCount: number;
  killReason: string | null;
  errorReason: string | null;
  output: Record<string, unknown> | null;
  startedAt: number | null;
  finishedAt: number | null;
}

export interface RunState {
  runId: string;
  prompt: string;
  startedAt: number;
  finishedAt: number | null;
  triageKind: string | null;
  triageReason: string | null;
  estimatedAgents: number;
  spawned: number;
  completed: number;
  killed: number;
  agents: Record<string, AgentView>;
  agentOrder: string[]; // for stable rendering
  answer: string | null;
  answerSource: string | null;
}

export interface TurnSummary {
  runId: string;
  prompt: string;
  answer: string | null;
}

export interface SkillDetail {
  role: string;
  tools: string[];
  model_hint: string;
  budget: Record<string, number>;
  manifest: SkillManifestDump | null;
  prompt_md: string;
  examples_md: string | null;
}

export interface SkillManifestDump {
  meta?: { name?: string; version?: string; description?: string; tags?: string[] };
  runtime?: { model_hint?: string; tools?: string[]; default_isolation?: string };
  budget?: { tokens?: number; wall_seconds?: number; joules?: number };
  requires?: {
    inputs?: Array<{ name: string; type?: string; description?: string; example?: string }>;
    optional?: Array<{ name: string; default?: unknown; description?: string }>;
  };
  output?: Record<string, unknown>;
  graph?: { can_spawn?: string[] };
}

export interface IntegrationsMap {
  [skillRole: string]: Record<string, string | number | boolean | string[]>;
}

export function newAgentView(partial: Partial<AgentView> & { id: string; role: string }): AgentView {
  return {
    parentId: null,
    depth: 0,
    status: 'pending',
    isolation: 'process',
    modelHint: 'auto',
    dependsOn: [],
    toolCalls: [],
    modelCalls: 0,
    logLines: [],
    workdir: null,
    files: [],
    fileCount: 0,
    killReason: null,
    errorReason: null,
    output: null,
    startedAt: null,
    finishedAt: null,
    ...partial,
  };
}
