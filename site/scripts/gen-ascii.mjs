// Deterministic ASCII texture generator for the Plnt landing hero.
// Outputs src/data/hero-ascii.txt — a 160x60 character grid layered from
// multiple sinusoidal fields with rare embedded Plnt tokens.
//
//   node scripts/gen-ascii.mjs
//
// Re-run any time to regenerate. Deterministic — no Math.random.

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const W = 160;
const H = 60;

// Density palette: index 0 is densest, last is empty.
const DENSITY = '@%#W*+=~-:.· ';

// Tokens that get embedded into the grid where the field is sparse.
// A careful reader sees real Plnt vocabulary in the noise.
const TOKENS = [
  { row: 6, col: 12, text: 'AgentSpec' },
  { row: 9, col: 86, text: 'spawn' },
  { row: 14, col: 38, text: 'tool_call' },
  { row: 18, col: 110, text: 'blackboard' },
  { row: 23, col: 22, text: 'r-2a5c42e150' },
  { row: 27, col: 64, text: 'planner' },
  { row: 31, col: 100, text: 'search()' },
  { row: 35, col: 14, text: 'execute()' },
  { row: 40, col: 70, text: 'sandbox' },
  { row: 44, col: 30, text: 'blackboard' },
  { row: 48, col: 108, text: 'finished' },
  { row: 52, col: 52, text: 'RLM' },
  { row: 55, col: 18, text: 'AgentSpec' },
];

// Layered field — gives a more organic, less-grid look than a single sine.
function field(x, y) {
  const a = Math.sin(x * 0.062 + y * 0.018);
  const b = Math.cos(y * 0.094 - x * 0.026);
  const c = Math.sin((x + y) * 0.041);
  const d = Math.cos((x - y) * 0.013);
  const e = Math.sin(Math.hypot(x - W / 2, y - H / 2) * 0.057);
  // mix → -5..5, normalize to 0..1
  const raw = (a + b + c * 0.5 + d * 0.4 + e * 0.6) / 3.5;
  return (raw + 1) / 2;
}

const grid = Array.from({ length: H }, () => Array(W).fill(' '));

for (let y = 0; y < H; y++) {
  for (let x = 0; x < W; x++) {
    const v = field(x, y);
    const idx = Math.max(0, Math.min(DENSITY.length - 1, Math.floor(v * DENSITY.length)));
    grid[y][x] = DENSITY[idx];
  }
}

// Lay tokens on top — only where the underlying field is sparse enough to read.
for (const { row, col, text } of TOKENS) {
  if (row < 0 || row >= H) continue;
  for (let i = 0; i < text.length; i++) {
    const x = col + i;
    if (x < 0 || x >= W) continue;
    grid[row][x] = text[i];
  }
}

const out = grid.map((row) => row.join('')).join('\n') + '\n';

const target = new URL('../src/data/hero-ascii.txt', import.meta.url);
mkdirSync(dirname(target.pathname), { recursive: true });
writeFileSync(target, out, 'utf8');
console.log(`wrote ${W}x${H} → ${target.pathname} (${out.length} bytes)`);
