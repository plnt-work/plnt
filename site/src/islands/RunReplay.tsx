/** @jsxImportSource preact */
// Replays a recorded run (events as the runtime streamed them) with the
// same run view the playground uses. The recording is made by
// scripts/record_replay.py against a real model.
import { useEffect, useMemo, useState } from 'preact/hooks';
import recording from '../data/replay-notes-api.json';
import { foldTurns, type Ev } from '../lib/transcript';
import { TurnView } from './run';

type Recording = { workspace: string; model: string; events: Ev[] };
const rec = recording as Recording;

export default function RunReplay() {
  const [n, setN] = useState(0);
  const [playing, setPlaying] = useState(true);
  const events = rec.events;

  useEffect(() => {
    if (!playing || n >= events.length) return;
    const cur = events[n];
    const next = events[n + 1];
    // Real gaps, compressed: a 3s model call becomes 0.9s, a 10ms tool call stays quick.
    const gap = next ? Math.min(1200, Math.max(120, ((next.ts - cur.ts) * 1000) * 0.3)) : 0;
    const t = setTimeout(() => setN(n + 1), gap);
    return () => clearTimeout(t);
  }, [n, playing, events]);

  const turns = useMemo(() => foldTurns(events.slice(0, n)), [events, n]);
  const done = n >= events.length;

  return (
    <div class="replay" data-replay>
      <div class="replay-head">
        <div>
          <span class="eyebrow">{rec.workspace} · {rec.model}</span>
          <h3>{turns[0]?.user.text ?? '…'}</h3>
        </div>
        <div class="agents" style="margin:0">
          {done ? (
            <button type="button" class="btn" onClick={() => { setN(0); setPlaying(true); }}>↺ Replay</button>
          ) : (
            <button type="button" class="btn" onClick={() => (playing ? setPlaying(false) : setPlaying(true))}>{playing ? 'Pause' : 'Play'}</button>
          )}
          {!done && <button type="button" class="btn" onClick={() => setN(events.length)}>Skip to the end</button>}
        </div>
      </div>
      <div class="replay-body">
        {turns.length === 0 && <p class="muted">Starting…</p>}
        {turns.map((t) => <TurnView key={t.run_id || t.ts} turn={t} />)}
      </div>
    </div>
  );
}
