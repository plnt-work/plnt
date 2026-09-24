// Derive the inline action card from the latest say-reply, same logic
// as web Atlas's deriveAction(). Lives in features/chat so the screen
// just consumes the typed result.
import type { TimelineItem } from "./useWsChat";

export type ChatAction =
  | { kind: "offer_slots"; slots: string[]; business_name?: string }
  | { kind: "booking_confirmed"; business_name: string; slot: string; booking_id: string }
  | { kind: "booking_failed"; reason: string }
  | { kind: "search_results"; place_ids: string[] }
  | null;

export function deriveAction(items: TimelineItem[]): ChatAction {
  for (let i = items.length - 1; i >= 0; i--) {
    const it = items[i];
    if (it.kind !== "reply") continue;
    const r = it.reply;
    if (r.role !== "say") continue;
    const a = (r.content as { action?: unknown }).action as
      | Record<string, unknown>
      | null
      | undefined;
    if (!a) continue;
    const kind = String(a.kind || "");
    if (kind === "offer_slots") {
      return {
        kind,
        slots: Array.isArray(a.slots) ? (a.slots as unknown[]).map(String) : [],
        business_name: a.business_name ? String(a.business_name) : undefined,
      };
    }
    if (kind === "booking_confirmed") {
      return {
        kind,
        business_name: String(a.business_name || ""),
        slot: String(a.slot || ""),
        booking_id: String(a.booking_id || ""),
      };
    }
    if (kind === "booking_failed") {
      return { kind, reason: String(a.reason || "unknown error") };
    }
    if (kind === "search_results") {
      return {
        kind,
        place_ids: Array.isArray(a.place_ids) ? (a.place_ids as unknown[]).map(String) : [],
      };
    }
  }
  return null;
}
