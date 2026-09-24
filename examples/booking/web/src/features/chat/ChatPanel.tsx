/**
 * ChatPanel — scoped to (business, agent).
 *
 * Lives inside the right rail (Atlas), under BusinessHeader + AgentStrip.
 * Owns its own composer + log; the WS connection itself lives one level up
 * so the same socket survives business/agent swaps.
 *
 * Visibility rule (preserved from prior layout): only the synthesizer's
 * `say` and `system` status bubbles render here. Intermediate trace replies
 * (classify_intent / resolve_business / etc.) drive UI side-effects in
 * Atlas instead of leaking into the log.
 *
 * Outgoing envelope — every user message is prefixed with
 *   `[biz:<place_id> agent:<slug>] <user text>`
 * so the backend MA router can scope downstream micro-agent calls. The
 * current Gemini synth ignores the bracket prefix but includes it in
 * context, which is fine for the demo.
 */
import { useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { Button } from "@/components/ui/Button";

import DisconnectSkeleton from "./DisconnectSkeleton";
import type { Status, TimelineItem } from "./useWsChat";
import type { Business } from "../places/types";
import type { AgentDef } from "../agents/registry";
import { metaFor } from "../places/verticals";

export interface SearchMatch {
  place_id: string;
  display_name: string;
  vertical: string;
}

export type ChatAction =
  | { kind: "offer_slots"; slots: string[]; business_name?: string }
  | { kind: "booking_confirmed"; business_name: string; slot: string; booking_id: string }
  | { kind: "booking_failed"; reason: string }
  | { kind: "search_results"; note?: string; place_ids: string[]; matches?: SearchMatch[] }
  | null;

interface Props {
  business: Business;
  agent: AgentDef;
  status: Status;
  items: TimelineItem[];
  thinking: boolean;
  action: ChatAction;
  pendingBookingSlot?: string | null;
  onSendRaw: (text: string) => boolean;
  onPickSlot?: (slot: string) => void;
  onPickSearchResult?: (placeId: string) => void;
}

export default function ChatPanel({
  business,
  agent,
  status,
  items,
  thinking,
  action,
  pendingBookingSlot,
  onSendRaw,
  onPickSlot,
  onPickSearchResult,
}: Props) {
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [items, thinking]);

  useEffect(() => {
    if (status === "connected") inputRef.current?.focus();
  }, [status, business.place_id, agent.slug]);

  const turns = items.filter((it) => {
    if (it.kind === "user") return true;
    return it.reply.role === "say" || it.reply.role === "system";
  });

  // Perceived-latency aids: surface the latest system note as the live
  // thinking label so the user sees which step is running, plus a 1Hz
  // tick of seconds elapsed since their last message. Pure derivation
  // from `items`; the interval only nudges nowTick (no setState in
  // effect body).
  const [nowTick, setNowTick] = useState<number>(0);
  useEffect(() => {
    if (!thinking) return;
    const id = setInterval(() => {
      setNowTick(Date.now());
    }, 1000);
    return () => clearInterval(id);
  }, [thinking]);

  const { lastUserTs, latestSystemNote } = useMemo(() => {
    let ts: number | null = null;
    let note: string | null = null;
    for (let i = items.length - 1; i >= 0; i--) {
      const it = items[i];
      if (it.kind === "user") {
        ts = it.ts;
        break;
      }
      if (it.reply.role === "system" && !note) {
        const n = String((it.reply.content as { note?: unknown }).note || "");
        if (n) note = n;
      }
    }
    return { lastUserTs: ts, latestSystemNote: note };
  }, [items]);

  const elapsedSeconds =
    thinking && lastUserTs && nowTick > lastUserTs
      ? Math.floor((nowTick - lastUserTs) / 1000)
      : 0;

  const send = (text: string): boolean => {
    const envelope = `[biz:${business.place_id} agent:${agent.slug}] ${text}`;
    return onSendRaw(envelope);
  };

  const submit = (e?: React.FormEvent) => {
    e?.preventDefault();
    const text = draft.trim();
    if (!text) return;
    if (send(text)) setDraft("");
  };

  const accent = metaFor(business.vertical).color;

  return (
    <section className="flex flex-col flex-1 min-h-0 bg-white">
      <div
        ref={logRef}
        className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-3"
      >
        {turns.length === 0 && (
          <div className="px-1 space-y-2.5">
            <div className="text-sm text-ink-100">
              Asking{" "}
              <span className="font-medium" style={{ color: accent }}>
                {agent.label}
              </span>{" "}
              about <span className="text-ink-500 font-medium">{business.display_name}</span>.
              <div className="mt-1 text-[11px] text-ink-100">{agent.hint}</div>
            </div>
            {agent.prompts.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {agent.prompts.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => send(p)}
                    disabled={status !== "connected"}
                    className="
                      h-7 px-2.5 rounded-full text-[12px] font-medium
                      border border-paper-600 bg-white text-ink-700
                      hover:bg-paper-200 transition-colors
                      disabled:opacity-50 disabled:cursor-not-allowed
                      focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-iri-blue/40
                    "
                    title={status !== "connected" ? `cannot send — status: ${status}` : p}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {turns.map((it) => {
          if (it.kind === "user") {
            return (
              <div
                key={`u-${it.seq}`}
                className="ml-auto max-w-[80%] rounded-2xl rounded-br-md bg-ink-700 text-paper-100 px-3.5 py-2 text-sm leading-snug"
              >
                {stripEnvelope(it.text)}
              </div>
            );
          }
          const r = it.reply;
          if (r.role === "system") {
            const note = String((r.content as { note?: unknown }).note || "");
            if (!note) return null;
            return (
              <div
                key={`s-${r.seq}`}
                className="mx-auto text-[11px] text-ink-100 italic"
              >
                {note}
              </div>
            );
          }
          const say = String((r.content as { say?: unknown }).say || "");
          if (!say) return null;
          return (
            <div
              key={`a-${r.seq}`}
              className="mr-auto max-w-[88%] rounded-2xl rounded-bl-md bg-paper-200 text-ink-700 px-3.5 py-2 text-sm leading-snug border border-paper-500/50"
            >
              {say}
            </div>
          );
        })}

        {action?.kind === "offer_slots" && action.slots.length > 0 && (
          <div className="mr-auto max-w-full rounded-xl bg-paper-100 border border-paper-500 p-3 space-y-2">
            <div className="text-xs uppercase tracking-wide text-ink-100">
              Tap to confirm{action.business_name ? ` at ${action.business_name}` : ""}
            </div>
            <div className="flex flex-wrap gap-2">
              {action.slots.map((slot) => {
                const d = new Date(slot);
                const ok = !Number.isNaN(d.getTime());
                const when = ok ? d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : slot;
                const day = ok ? d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }) : "";
                const isPending = pendingBookingSlot === slot;
                return (
                  <Button
                    key={slot}
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-auto py-1.5 px-3 flex-col items-start"
                    onClick={() => onPickSlot?.(slot)}
                    disabled={!onPickSlot || status !== "connected" || isPending}
                  >
                    {isPending ? (
                      <span className="flex items-center gap-1.5 text-ink-700">
                        <ThinkingDots />
                        <span className="font-medium">Confirming…</span>
                      </span>
                    ) : (
                      <>
                        <span className="font-medium text-ink-700">{when}</span>
                        {day && <span className="text-[10px] text-ink-100">{day}</span>}
                      </>
                    )}
                  </Button>
                );
              })}
            </div>
          </div>
        )}

        {action?.kind === "search_results" && action.place_ids.length > 0 && (
          <div className="mr-auto max-w-full rounded-xl bg-paper-100 border border-paper-500 p-3 space-y-2">
            <div className="text-xs text-ink-100">
              Found {action.place_ids.length} {action.place_ids.length === 1 ? "place" : "places"}:
            </div>
            <div className="flex flex-wrap gap-1.5">
              {(action.matches && action.matches.length > 0
                ? action.matches
                : action.place_ids.map((pid) => ({ place_id: pid, display_name: pid, vertical: "" }))
              ).map((m) => (
                <button
                  key={m.place_id}
                  type="button"
                  onClick={() => onPickSearchResult?.(m.place_id)}
                  disabled={!onPickSearchResult}
                  className="h-7 px-2.5 rounded-full text-[12px] font-medium border border-paper-600 bg-white text-ink-700 hover:border-iri-blue hover:text-iri-blue transition-colors disabled:opacity-50"
                >
                  {m.display_name}
                </button>
              ))}
            </div>
          </div>
        )}

        {action?.kind === "booking_confirmed" && (
          <div className="mr-auto rounded-xl border border-sage/40 bg-sage/10 p-3 text-sm">
            <div className="text-xs uppercase tracking-wide text-sage font-medium">Confirmed</div>
            <div className="text-ink-700 font-medium">{action.business_name}</div>
            <div className="text-xs text-ink-100">{action.slot} · id {action.booking_id}</div>
          </div>
        )}

        {action?.kind === "booking_failed" && (
          <div className="mr-auto rounded-xl border border-rust/40 bg-rust/10 p-3 text-sm">
            <div className="text-xs uppercase tracking-wide text-rust font-medium">Didn't go through</div>
            <div className="text-ink-700">{action.reason}</div>
          </div>
        )}

        {thinking && (
          <div className="mr-auto flex items-center gap-2 px-1 text-ink-100 text-xs">
            <ThinkingDots />
            <span>{latestSystemNote || "thinking…"}</span>
            {elapsedSeconds > 1 && (
              <span className="text-[10.5px] text-ink-100/70 font-mono">
                {elapsedSeconds}s
              </span>
            )}
          </div>
        )}

        <DisconnectSkeleton status={status} />
      </div>

      <form
        onSubmit={submit}
        className="m-3 flex items-center gap-2 rounded-pill border border-paper-600 bg-paper-100 px-3 py-2 transition-colors focus-within:border-iri-blue focus-within:shadow-[0_0_0_3px_rgba(26,115,232,0.18)]"
      >
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={
            status === "connected" ? agent.placeholder
            : status === "connecting" ? "connecting to backend…"
            : status === "error" ? "agent offline — is uvicorn running on :8080?"
            : status === "closed" ? "reconnecting…"
            : "starting…"
          }
          autoComplete="off"
          spellCheck={false}
          className="flex-1 bg-transparent outline-none text-sm text-ink-700 placeholder:text-ink-100"
        />
        <Button
          type="submit"
          size="icon"
          variant="solid"
          disabled={!draft.trim() || status !== "connected"}
          aria-label="Send"
          className="rounded-full size-9"
          title={status !== "connected" ? `cannot send — status: ${status}` : "Send"}
        >
          <Icon name="arrow-right" className="size-4" />
        </Button>
      </form>
    </section>
  );
}

function ThinkingDots() {
  return (
    <span className="inline-flex gap-1" aria-hidden>
      <span className="size-1.5 rounded-full bg-ink-100 animate-pulse-soft" />
      <span className="size-1.5 rounded-full bg-ink-100 animate-pulse-soft [animation-delay:0.15s]" />
      <span className="size-1.5 rounded-full bg-ink-100 animate-pulse-soft [animation-delay:0.3s]" />
    </span>
  );
}

/** Strip the outgoing envelope prefix when displaying user turns back. */
function stripEnvelope(text: string): string {
  const m = text.match(/^\[biz:[^\s\]]+ agent:[^\s\]]+]\s*(.*)$/);
  return m ? (m[1] || "") : text;
}
