/** @jsxImportSource preact */
import { currentRun, history } from './state';

function fmtWall(start: number, end: number | null): string {
  const s = ((end ?? Date.now()) - start) / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${(s - m * 60).toFixed(0)}s`;
}

export default function Parent() {
  const run = currentRun.value;
  const turns = history.value;

  return (
    <section class="parent">
      <div class="history">
        {turns.length === 0 && (
          <p class="dim small">No turns yet. Your first prompt starts a run.</p>
        )}
        {turns.map((t, i) => (
          <article class={`turn ${i === turns.length - 1 ? 'is-current' : ''}`} key={t.runId}>
            <p class="who you">you</p>
            <p class="msg">{t.prompt}</p>
            {t.answer && <>
              <p class="who plnt">plnt</p>
              <p class="msg">{t.answer}</p>
            </>}
            {!t.answer && i === turns.length - 1 && run && (
              <p class="dim small">
                {run.triageKind ? `triage: ${run.triageKind}` : 'triaging…'}
              </p>
            )}
          </article>
        ))}
      </div>

      {run && (
        <div class="run-details">
          <header class="run-details-head">
            <span class="kicker">RUN</span>
            <span class="mono">{run.runId}</span>
          </header>
          <dl class="kv">
            <div><dt>TRIAGE</dt><dd>{run.triageKind ?? '…'}</dd></div>
            <div><dt>AGENTS</dt><dd>
              {Object.keys(run.agents).length} spawned
              {run.completed > 0 && <span class="dim">, {run.completed} done</span>}
              {run.killed > 0 && <span class="dim">, {run.killed} killed</span>}
            </dd></div>
            <div><dt>WALL</dt><dd>{fmtWall(run.startedAt, run.finishedAt)}</dd></div>
            <div><dt>COST</dt><dd>$0 · local</dd></div>
            {run.answerSource && <div><dt>ANSWER FROM</dt><dd class="mono">{run.answerSource}</dd></div>}
          </dl>
        </div>
      )}
    </section>
  );
}
