// Pure date helpers — kept separate from the React component so the
// availability-determinism test can import them without dragging RN in.

export interface DayCell {
  /** ISO YYYY-MM-DD. */
  date: string;
  /** "Mon", "Tue", ... */
  dow: string;
  /** Day of month, e.g. 12. */
  dom: number;
}

const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** Format a Date as YYYY-MM-DD in local time. */
export function ymd(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Seven-day strip starting at `today`. */
export function buildDateStrip(today: Date, days = 7): DayCell[] {
  const out: DayCell[] = [];
  for (let i = 0; i < days; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    out.push({
      date: ymd(d),
      dow: DOW[d.getDay()],
      dom: d.getDate(),
    });
  }
  return out;
}
