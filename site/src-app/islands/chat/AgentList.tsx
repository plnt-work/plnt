/** @jsxImportSource preact */
import { currentRun, selectedAgentId } from './state';
import type { AgentView } from './types';

const STATUS_GLYPH: Record<string, string> = {
  pending: '○',
  spawned: '◌',
  running: '●',
  done: '✓',
  killed: '✗',
  error: '!',
};

function elapsed(ag: AgentView): string {
  if (!ag.startedAt) return '';
  const end = ag.finishedAt ?? Date.now();
  const s = Math.max(0, (end - ag.startedAt) / 1000);
  return `${s.toFixed(1)}s`;
}

function dim(s: string) {
  return s.length > 32 ? s.slice(0, 31) + '…' : s;
}

export default function AgentList() {
  const run = currentRun.value;
  if (!run) {
    return (
      <aside class="agents empty">
        <header class="agents-head"><span class="kicker">SPAWNED AGENTS</span></header>
        <p class="dim">No active run. Submit a message to spawn a swarm.</p>
      </aside>
    );
  }

  const ids = run.agentOrder;
  const selected = selectedAgentId.value;

  return (
    <aside class="agents">
      <header class="agents-head">
        <span class="kicker">SPAWNED AGENTS</span>
        <span class="count">{ids.length}</span>
      </header>
      {ids.length === 0 && run.finishedAt === null && (
        <p class="dim">Waiting for triage + plan…</p>
      )}
      {ids.length === 0 && run.finishedAt !== null && (
        <p class="dim">No agents spawned. Triage replied directly.</p>
      )}
      <ul class="agent-list">
        {ids.map((id) => {
          const ag = run.agents[id];
          if (!ag) return null;
          const isSel = selected === id;
          const last = ag.toolCalls[ag.toolCalls.length - 1];
          return (
            <li
              key={id}
              class={`agent-row ${isSel ? 'is-selected' : ''} status-${ag.status}`}
              onClick={() => { selectedAgentId.value = isSel ? null : id; }}
            >
              <div class="agent-row-main">
                <span class={`glyph s-${ag.status}`}>{STATUS_GLYPH[ag.status] ?? '·'}</span>
                <span class="role">{ag.role}</span>
                <span class="id">{ag.id}</span>
              </div>
              <div class="agent-row-meta">
                {last && (
                  <span class="last-call">
                    {last.tool}{' '}
                    <span class="dim">
                      {dim(Object.values(last.args || {}).map(String).join(' · ') || '')}
                    </span>
                  </span>
                )}
                {ag.modelCalls > 0 && <span class="pill mono">{ag.modelCalls} model</span>}
                {ag.toolCalls.length > 0 && (
                  <span class="pill mono">{ag.toolCalls.length} tool</span>
                )}
                {ag.fileCount > 0 && <span class="pill mono">{ag.fileCount} file</span>}
                {elapsed(ag) && <span class="pill mono">{elapsed(ag)}</span>}
              </div>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
