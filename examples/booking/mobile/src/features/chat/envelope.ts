// WS envelope builders — single source of truth for the prefix shape.
// Mirrors web Atlas's onSendRaw + ChatPanel.onSend behaviors so the
// backend doesn't see a forked client.
import type { AgentSlug } from "@web/agents/registry";

interface ScopedOpts {
  placeId: string;
  agent: AgentSlug;
  userLoc?: { lat: number; lng: number } | null;
}

interface FreeformOpts {
  userLoc?: { lat: number; lng: number } | null;
}

function appendLoc(s: string, userLoc?: { lat: number; lng: number } | null): string {
  if (!userLoc) return s;
  return `${s} [@${userLoc.lat.toFixed(5)},${userLoc.lng.toFixed(5)}]`;
}

/** [biz:X agent:Y] <text> [@lat,lng] */
export function scopedEnvelope(text: string, opts: ScopedOpts): string {
  const prefixed = `[biz:${opts.placeId} agent:${opts.agent}] ${text}`;
  return appendLoc(prefixed, opts.userLoc);
}

/** <text> [@lat,lng] — for freeform Home search that routes to classify_intent. */
export function freeformEnvelope(text: string, opts: FreeformOpts = {}): string {
  return appendLoc(text, opts.userLoc);
}
