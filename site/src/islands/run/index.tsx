/** @jsxImportSource preact */
// The run view (Preact twin of console/src/components/run): one turn = the
// task, what the parent decided, the plan, one card per agent, the reply.
// Same names and data attributes as the console so the e2e tests match.
import { useState } from 'preact/hooks';
import { parentSummary, replySource } from '../../lib/run-view';
import { layers, type AgentCard, type Step, type Turn } from '../../lib/transcript';

export function TurnView({ turn }: { turn: Turn }) {
  const open = turn.outcome === null;
  return (
    <div class="turn" data-turn={turn.run_id}>
      <div class="msg user">{turn.user.text}</div>
      {turn.parent && (
        <div class="run-parent" data-parent={turn.parent.kind}>
          <span class="glyph" aria-hidden="true">⑂</span>
          <b>Parent</b> {parentSummary(turn.parent.kind, turn.parent.plan.length)}
          {turn.parent.reason && <span class="muted"> · {turn.parent.reason}</span>}
        </div>
      )}
      {turn.agents.length > 1 && <Plan turn={turn} />}
      {turn.agents.length > 0 && (
        <div class="run-agents">
          {turn.agents.map((a) => <AgentView key={a.id} a={a} />)}
        </div>
      )}
      {turn.reply && (
        <div class="reply">
          <div class="msg agent">{turn.reply.text}</div>
          <span class="eyebrow">{replySource(turn.reply.source)}</span>
        </div>
      )}
      {turn.error && (
        <div class={`msg note ${turn.error.stopped === 'killed' ? 'killed' : 'run_error'}`}>
          {turn.error.stopped === 'killed' ? 'stopped: ' : 'error: '}
          {turn.error.error}
          {turn.error.hint ? ` (${turn.error.hint})` : ''}
        </div>
      )}
      {open ? (
        <div class="msg agent pending">working…</div>
      ) : (
        <div class="run-meta eyebrow">{turn.outcome} · {turn.tokens} tokens · {turn.wall_seconds}s</div>
      )}
    </div>
  );
}

function Plan({ turn }: { turn: Turn }) {
  const ls = layers(turn.agents);
  return (
    <div class="run-plan" data-plan>
      <span class="eyebrow">plan</span>
      {ls.map((layer, i) => (
        <>
          {i > 0 && <span class="arrow">→</span>}
          <div class="layer">
            {layer.map((a) => <span key={a.id} class={`node ${a.status}`}>{a.role}</span>)}
          </div>
        </>
      ))}
    </div>
  );
}

export function AgentView({ a, full }: { a: AgentCard; full?: boolean }) {
  const [showSpec, setShowSpec] = useState(!!full);
  const calls = a.steps.filter((s) => s.kind === 'tool_call').length;
  return (
    <div class={`run-agent ${a.status}`} data-agent={a.id}>
      <div class="head">
        <span class="role">{a.role}</span>
        <span class="mono muted">{a.bundle ? `${a.bundle}@${a.version}` : 'invented role'}</span>
        <span class={`status ${a.status}`}>{a.status}</span>
      </div>
      {a.intent && <p class="intent">{a.intent}</p>}
      {a.depends_on.length > 0 && <p class="muted small">after {a.depends_on.join(', ')}</p>}
      <button type="button" class="linkish" onClick={() => setShowSpec(!showSpec)}>
        <span class={`chev ${showSpec ? 'open' : ''}`}>›</span> spec · {a.tools.length} tool{a.tools.length === 1 ? '' : 's'}
        {a.model?.model ? ` · ${a.model.model}` : ''}
      </button>
      {showSpec && (
        <dl class="spec">
          <div><dt>id</dt><dd>{a.id}</dd></div>
          <div><dt>bundle</dt><dd>{a.bundle ?? '(invented by the parent)'}</dd></div>
          <div><dt>tools</dt><dd>{a.tools.join(', ') || 'none'}</dd></div>
          <div><dt>model</dt><dd>{a.model ? `${a.model.provider} ${a.model.model} (${a.model.source})` : '?'}</dd></div>
          <div><dt>depends_on</dt><dd>{a.depends_on.join(', ') || '—'}</dd></div>
        </dl>
      )}
      {a.steps.length > 0 && (
        <ol class="steps">
          {a.steps.map((s, i) => <StepRow key={i} s={s} />)}
        </ol>
      )}
      {a.answer && a.status !== 'running' && <p class={`answer ${full ? '' : 'clamp'}`}>{a.answer}</p>}
      {a.error && <p class="bad small">{a.error}</p>}
      <p class="eyebrow">
        {calls} call{calls === 1 ? '' : 's'} · {a.tokens} tokens{a.wall_seconds != null ? ` · ${a.wall_seconds}s` : ''}
      </p>
    </div>
  );
}

function argSummary(args: unknown): string {
  if (!args || typeof args !== 'object') return '';
  const a = args as Record<string, unknown>;
  const v = a.path ?? a.pattern ?? (Array.isArray(a.argv) ? a.argv.join(' ') : undefined);
  return v === undefined ? '' : String(v).slice(0, 60);
}

export function StepRow({ s }: { s: Step }) {
  if (s.kind === 'guardrail') {
    return (
      <li class="guardrail">
        {s.action === 'refused' ? `answer withheld: skipped ${s.tool} twice` : `answered without ${s.tool}; asked to look first`}
      </li>
    );
  }
  return (
    <li>
      <details>
        <summary>
          <span class="mono">{s.tool}</span> <span class="mono muted">{argSummary(s.args)}</span>
          {s.ok === false && <span class="bad"> failed</span>}
          {s.ok === null && ' …'}
        </summary>
        <pre>{JSON.stringify(s.args, null, 2)}</pre>
      </details>
    </li>
  );
}
