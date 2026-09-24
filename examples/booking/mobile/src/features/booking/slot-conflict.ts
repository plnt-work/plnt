// Pure slot-conflict helpers — kept independent of any UI / API so a
// Jest test can pin behavior before the real availability fetch is
// wired in P2. Slot strings are ISO local timestamps without zone, e.g.
// "2026-07-04T19:30". Duration is in minutes.
export interface Slot {
  start: string; // ISO local "YYYY-MM-DDTHH:mm"
  duration_min: number;
}

const ISO_LOCAL = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;

export function parseSlotStart(s: string): number {
  const m = ISO_LOCAL.exec(s);
  if (!m) throw new Error(`bad slot: ${s}`);
  // Treat as UTC so the math is portable; "conflicts" don't care about
  // wall-clock zone — two slots on the same local clock for the same
  // venue overlap iff their minute offsets overlap.
  return Date.UTC(
    Number(m[1]),
    Number(m[2]) - 1,
    Number(m[3]),
    Number(m[4]),
    Number(m[5]),
  );
}

export function endOf(slot: Slot): number {
  return parseSlotStart(slot.start) + slot.duration_min * 60_000;
}

export function overlaps(a: Slot, b: Slot): boolean {
  const aStart = parseSlotStart(a.start);
  const aEnd = endOf(a);
  const bStart = parseSlotStart(b.start);
  const bEnd = endOf(b);
  return aStart < bEnd && bStart < aEnd;
}

/** Returns true if `candidate` collides with any slot in `existing`. */
export function hasConflict(candidate: Slot, existing: Slot[]): boolean {
  return existing.some((e) => overlaps(candidate, e));
}

/** Filters `candidates` down to those that don't conflict with `existing`. */
export function filterAvailable(candidates: Slot[], existing: Slot[]): Slot[] {
  return candidates.filter((c) => !hasConflict(c, existing));
}
