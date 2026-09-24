/** @jsxImportSource preact */
import { useEffect, useState } from 'preact/hooks';
import { currentRun, selectedAgentId, skillCache } from './state';
import { getSkill } from './api';
import type { AgentView, SkillDetail, ToolCallRecord } from './types';

function fmtArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([k, v]) => {
      if (Array.isArray(v)) return `${k}=[${v.map(String).join(', ')}]`;
      if (typeof v === 'object' && v) return `${k}=${JSON.stringify(v)}`;
      return `${k}=${String(v)}`;
    })
    .join('  ');
}

function fmtTs(ms: number | null | undefined): string {
  if (!ms) return '';
  const d = new Date(ms);
  return d.toTimeString().slice(0, 8);
}

function StatusBadge({ ag }: { ag: AgentView }) {
  return <span class={`status-badge s-${ag.status}`}>{ag.status.toUpperCase()}</span>;
}

function ToolCalls({ calls }: { calls: ToolCallRecord[] }) {
  if (calls.length === 0) return <p class="dim">No tool calls yet.</p>;
  return (
    <ol class="toolcall-list">
      {calls.map((c, i) => (
        <li key={i} class="toolcall">
          <div class="toolcall-head">
            <span class="ts">{fmtTs(c.ts)}</span>
            <span class="step">step {c.step}</span>
            <span class="tool">{c.tool}</span>
            {c.resultOk !== undefined && (
              <span class={`ok ${c.resultOk ? 'good' : 'bad'}`}>
                {c.resultOk ? '✓' : '✗'} {c.resultSummary}
              </span>
            )}
          </div>
          <pre class="args">{fmtArgs(c.args)}</pre>
        </li>
      ))}
    </ol>
  );
}

function SkillView({ role }: { role: string }) {
  const cached = skillCache.value[role];
  const [, setTick] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (cached) return;
    let ok = true;
    getSkill(role)
      .then((sk: SkillDetail) => {
        if (!ok) return;
        skillCache.value = { ...skillCache.value, [role]: sk };
        setTick((n) => n + 1);
      })
      .catch((e) => { if (ok) setErr(String(e?.message ?? e)); });
    return () => { ok = false; };
  }, [role]);

  if (err) return <p class="dim">Skill {role}: {err}</p>;
  if (!cached) return <p class="dim">Loading skill…</p>;

  const inputs = cached.manifest?.requires?.inputs ?? [];
  const optional = cached.manifest?.requires?.optional ?? [];
  const canSpawn = cached.manifest?.graph?.can_spawn ?? [];

  return (
    <>
      <div class="skill-meta">
        <span class="kicker">SKILL</span>
        <span class="mono">{cached.role}</span>
        <span class="dim">model_hint={cached.model_hint}</span>
        <span class="dim">tokens={cached.budget?.tokens ?? '?'}</span>
        <span class="dim">wall={cached.budget?.wall_seconds ?? '?'}s</span>
      </div>
      {inputs.length > 0 && (
        <details open>
          <summary>required inputs</summary>
          <ul class="inputs-list">
            {inputs.map((i) => (
              <li key={i.name}><strong class="mono">{i.name}</strong> <span class="dim">({i.type})</span> — {i.description}</li>
            ))}
          </ul>
        </details>
      )}
      {optional.length > 0 && (
        <details>
          <summary>optional inputs</summary>
          <ul class="inputs-list">
            {optional.map((i) => (
              <li key={i.name}><strong class="mono">{i.name}</strong> {i.description ? `— ${i.description}` : ''}</li>
            ))}
          </ul>
        </details>
      )}
      {canSpawn.length > 0 && (
        <p class="dim mono">can_spawn → {canSpawn.join(', ')}</p>
      )}
      <details open>
        <summary>prompt.md</summary>
        <pre class="prompt-md">{cached.prompt_md || '(empty)'}</pre>
      </details>
      {cached.examples_md && (
        <details>
          <summary>examples.md</summary>
          <pre class="prompt-md">{cached.examples_md}</pre>
        </details>
      )}
    </>
  );
}

export default function AgentDrawer() {
  const run = currentRun.value;
  const id = selectedAgentId.value;
  if (!run || !id) return null;
  const ag = run.agents[id];
  if (!ag) return null;

  return (
    <div class="drawer" role="dialog" aria-modal="false">
      <header class="drawer-head">
        <div>
          <h3 class="drawer-title">
            <span class="role">{ag.role}</span>
            <span class="dim mono">{ag.id}</span>
          </h3>
          <p class="drawer-meta">
            <StatusBadge ag={ag} />
            <span class="dim mono">isolation={ag.isolation}</span>
            <span class="dim mono">depth={ag.depth}</span>
            <span class="dim mono">{ag.toolCalls.length} tool calls</span>
            <span class="dim mono">{ag.modelCalls} model calls</span>
          </p>
        </div>
        <button class="btn compact" onClick={() => { selectedAgentId.value = null; }}>close</button>
      </header>

      <section>
        <span class="kicker">RUN PATH</span>
        <p class="mono small">
          parent={ag.parentId ?? '(root)'} · workdir={ag.workdir ?? '(none)'}
        </p>
        {ag.killReason && <p class="warn">killed: {ag.killReason}</p>}
        {ag.errorReason && <p class="warn">error: {ag.errorReason}</p>}
      </section>

      <section>
        <span class="kicker">TOOL CALLS</span>
        <ToolCalls calls={ag.toolCalls} />
      </section>

      {ag.logLines.length > 0 && (
        <section>
          <span class="kicker">LOG</span>
          <pre class="logbuf">{ag.logLines.join('\n')}</pre>
        </section>
      )}

      {ag.files.length > 0 && (
        <section>
          <span class="kicker">FILES WRITTEN</span>
          <ul class="files-list mono">
            {ag.files.map((f) => <li key={f}>{f}</li>)}
          </ul>
        </section>
      )}

      {ag.output && (
        <section>
          <span class="kicker">OUTPUT</span>
          <pre class="logbuf">{JSON.stringify(ag.output, null, 2)}</pre>
        </section>
      )}

      <section>
        <SkillView role={ag.role} />
      </section>
    </div>
  );
}
