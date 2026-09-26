/**
 * useWsChat — connects to /v1/ws/{tenantId}/{sessionId}, sends user messages,
 * collects replies in arrival order. One instance per ChatPanel.
 *
 * WS protocol (Python side):
 *   { event: "session_started", workflow_id }
 *   { event: "ack", received_chars }
 *   { event: "reply", seq, role, content }
 *   { event: "error", where, detail }
 *
 * Timeline model: a single `items` array holding both user messages and
 * replies, each tagged with a local timestamp on insertion. Render in array
 * order — no merging logic needed at the component layer.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export interface Reply {
  seq: number;
  role: string;
  content: Record<string, unknown>;
}

export interface UserMessage {
  id: number;
  text: string;
}

export type TimelineItem =
  | { kind: "user"; ts: number; seq: number; text: string }
  | { kind: "reply"; ts: number; reply: Reply };

export type Status = "idle" | "connecting" | "connected" | "closed" | "error";

interface Opts {
  tenantId: string;
  sessionId: string;
  userId: string;
  enabled?: boolean;
}

/** localStorage key for the cached timeline of one (tenant, session) pair. */
function cacheKey(tenantId: string, sessionId: string): string {
  return `atlas_timeline:${tenantId}:${sessionId}`;
}

function readCache(tenantId: string, sessionId: string): TimelineItem[] {
  try {
    const raw = localStorage.getItem(cacheKey(tenantId, sessionId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as TimelineItem[]) : [];
  } catch {
    return [];
  }
}

function writeCache(tenantId: string, sessionId: string, items: TimelineItem[]) {
  try {
    // Bound at 300 items so the cache can't grow unbounded.
    const trimmed = items.slice(-300);
    localStorage.setItem(cacheKey(tenantId, sessionId), JSON.stringify(trimmed));
  } catch {
    // localStorage full or disabled — non-fatal
  }
}

export function useWsChat({ tenantId, sessionId, userId, enabled = true }: Opts) {
  // Seed status to "connecting" eagerly so the effect doesn't need to call
  // setStatus during mount — keeps react-hooks/set-state-in-effect happy.
  const [status, setStatus] = useState<Status>(enabled ? "connecting" : "idle");
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  // Hydrate from localStorage so a nav away + back shows the chat immediately
  // instead of a blank panel while the WS reconnects and replays.
  const [items, setItems] = useState<TimelineItem[]>(() => readCache(tenantId, sessionId));
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Save every change. Skipping the initial empty state because it would
  // overwrite a freshly-hydrated cache during render.
  useEffect(() => {
    if (items.length > 0) writeCache(tenantId, sessionId, items);
  }, [tenantId, sessionId, items]);

  useEffect(() => {
    if (!enabled) return;

    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    // Same-origin (Vite proxy handles /v1) — works without CORS in dev.
    const qs = new URLSearchParams({ user_id: userId });
    const url = `${proto}://${window.location.host}/v1/ws/${encodeURIComponent(
      tenantId,
    )}/${encodeURIComponent(sessionId)}?${qs.toString()}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
      setError(null);
    };
    ws.onclose = (evt) => {
      setStatus("closed");
      if (evt.reason) setError(evt.reason);
    };
    ws.onerror = () => {
      setStatus("error");
      setError("WebSocket error — is uvicorn running on :8080?");
    };
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.event === "session_started") {
          setWorkflowId(String(msg.workflow_id));
          setError(null);
        } else if (msg.event === "reply") {
          const seq = Number(msg.seq);
          const role = String(msg.role);
          const content = msg.content || {};
          setItems((prev) => {
            // Guard against duplicate seqs (StrictMode reconnect, replay overlap).
            if (prev.some((it) => it.kind === "reply" && it.reply.seq === seq) ||
                prev.some((it) => it.kind === "user" && it.seq === seq)) {
              return prev;
            }
            if (role === "user") {
              return [...prev, { kind: "user", ts: Date.now(), seq, text: String(content.text || "") }];
            }
            return [...prev, { kind: "reply", ts: Date.now(), reply: { seq, role, content } }];
          });
          setError(null);
        } else if (msg.event === "error") {
          setError(String(msg.detail || "unknown error"));
        }
        // 'ack' intentionally ignored
      } catch {
        // ignore malformed
      }
    };

    return () => {
      try { ws.close(); } catch { /* noop */ }
      wsRef.current = null;
    };
  }, [tenantId, sessionId, userId, enabled]);

  const send = useCallback((text: string) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    // No optimistic insert — the workflow echoes back as a role="user" reply
    // and the onmessage handler appends it. Avoids duplicates on reconnect.
    ws.send(text);
    return true;
  }, []);

  return { status, workflowId, items, error, send };
}
