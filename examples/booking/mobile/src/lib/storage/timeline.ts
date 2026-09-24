// AsyncStorage-backed timeline cache — the RN analogue of web Atlas's
// localStorage hydration. Useful for the offline-open case: app opens,
// last-session chat renders immediately, WS reconnect's replay backfills.
import AsyncStorage from "@react-native-async-storage/async-storage";
import type { TimelineItem } from "@/features/chat/useWsChat";

const MAX_ITEMS = 300;

function cacheKey(tenantId: string, sessionId: string): string {
  return `plnt.timeline:${tenantId}:${sessionId}`;
}

export async function readTimeline(
  tenantId: string,
  sessionId: string,
): Promise<TimelineItem[]> {
  try {
    const raw = await AsyncStorage.getItem(cacheKey(tenantId, sessionId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as TimelineItem[]) : [];
  } catch {
    return [];
  }
}

export async function writeTimeline(
  tenantId: string,
  sessionId: string,
  items: TimelineItem[],
): Promise<void> {
  try {
    const trimmed = items.slice(-MAX_ITEMS);
    await AsyncStorage.setItem(
      cacheKey(tenantId, sessionId),
      JSON.stringify(trimmed),
    );
  } catch {
    // bounded storage / quota — non-fatal
  }
}
