/**
 * Small format helpers shared across the new Console tabs.
 * Unix-seconds in, formatted string out — no inline `new Date(t*1000)`
 * sprinkled through the JSX.
 */
import { formatDistanceToNow, format as formatDate, isValid } from "date-fns";

import { SAMPLE_BUSINESSES } from "@/features/places/sample-businesses";

const BIZ_NAME: Record<string, string> = Object.fromEntries(
  SAMPLE_BUSINESSES.map((b) => [b.place_id, b.display_name]),
);

export function businessNameOf(id: string | null | undefined): string {
  if (!id) return "—";
  return BIZ_NAME[id] ?? id;
}

export function relativeFromSeconds(ts: number | null | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  if (!isValid(d)) return "—";
  return formatDistanceToNow(d, { addSuffix: true });
}

export function absoluteFromSeconds(ts: number | null | undefined): string {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  if (!isValid(d)) return "—";
  return formatDate(d, "PP HH:mm");
}

export function slotFromIso(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (!isValid(d)) return iso || "—";
  return formatDate(d, "EEE MMM d, h:mm a");
}

export function truncate(text: string, max = 64): string {
  return text.length <= max ? text : text.slice(0, max - 1) + "…";
}
