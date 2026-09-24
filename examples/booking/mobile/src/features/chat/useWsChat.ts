/**
 * useWsChat — React Native port of web/src/features/chat/useWsChat.ts.
 *
 * Differences from the web version:
 *   - URL: built from EXPO_PUBLIC_WS_BASE (cloudflared hostname),
 *     not window.location.host. There is no Vite proxy on device.
 *   - Cache: AsyncStorage instead of localStorage; async hydration on
 *     mount instead of lazy useState initializer.
 *
 * Wire protocol is otherwise IDENTICAL — same event names, same Reply
 * shape, same dedup-by-seq rule. The backend must not have to fork to
 * tell us apart from the web client.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { env } from "@/lib/env";
import { readTimeline, writeTimeline } from "@/lib/storage/timeline";

export interface Reply {
  seq: number;
  role: string;
  content: Record<string, unknown>;
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

export function useWsChat({ tenantId, sessionId, userId, enabled = true }: Opts) {
  const [status, setStatus] = useState<Status>(enabled ? "connecting" : "idle");
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [items, setItems] = useState<TimelineItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const hydratedRef = useRef(false);

  // Async hydrate — RN has no synchronous localStorage equivalent.
  useEffect(() => {
    let alive = true;
    (async () => {
      const cached = await readTimeline(tenantId, sessionId);
      if (!alive) return;
      if (cached.length > 0) setItems(cached);
      hydratedRef.current = true;
    })();
    return () => {
      alive = false;
    };
  }, [tenantId, sessionId]);

  // Persist after every change once hydrated. Skipping pre-hydration
  // writes prevents wiping the cache during the initial empty render.
  useEffect(() => {
    if (!hydratedRef.current) return;
    if (items.length === 0) return;
    void writeTimeline(tenantId, sessionId, items);
  }, [tenantId, sessionId, items]);

  useEffect(() => {
    if (!enabled) return;

    const base = env.wsBase.replace(/\/$/, "");
    const qs = `user_id=${encodeURIComponent(userId)}`;
    const url = `${base}/v1/ws/${encodeURIComponent(tenantId)}/${encodeURIComponent(
      sessionId,
    )}?${qs}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      setStatus("connected");
      setError(null);
    };
    ws.onclose = (evt: WebSocketCloseEvent) => {
      setStatus("closed");
      if (evt.reason) setError(evt.reason);
    };
    ws.onerror = () => {
      setStatus("error");
      setError("WebSocket error — is the tunnel up and CORS configured?");
    };
    ws.onmessage = (evt: WebSocketMessageEvent) => {
      try {
        const msg = JSON.parse(String(evt.data));
        if (msg.event === "session_started") {
          setWorkflowId(String(msg.workflow_id));
          setError(null);
        } else if (msg.event === "reply") {
          const seq = Number(msg.seq);
          const role = String(msg.role);
          const content = msg.content || {};
          setItems((prev) => {
            if (
              prev.some((it) => it.kind === "reply" && it.reply.seq === seq) ||
              prev.some((it) => it.kind === "user" && it.seq === seq)
            ) {
              return prev;
            }
            if (role === "user") {
              return [
                ...prev,
                { kind: "user", ts: Date.now(), seq, text: String(content.text || "") },
              ];
            }
            return [
              ...prev,
              { kind: "reply", ts: Date.now(), reply: { seq, role, content } },
            ];
          });
          setError(null);
        } else if (msg.event === "error") {
          setError(String(msg.detail || "unknown error"));
        }
        // 'ack' intentionally ignored
      } catch {
        // malformed frame — drop
      }
    };

    return () => {
      try {
        ws.close();
      } catch {
        // noop
      }
      wsRef.current = null;
    };
  }, [tenantId, sessionId, userId, enabled]);

  const send = useCallback((text: string) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== 1) return false;
    ws.send(text);
    return true;
  }, []);

  return { status, workflowId, items, error, send };
}
