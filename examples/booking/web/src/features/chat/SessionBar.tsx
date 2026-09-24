/**
 * SessionBar — the small bar at the bottom of the right rail that surfaces
 * the WS pill, geolocation pill, "+ new" session rotation, and the operator
 * console link. Kept tight and Google-product-like, not chatty.
 */
import { Link } from "react-router-dom";

import { cn } from "@/lib/cn";

import type { Status } from "./useWsChat";

export type LocStatus = "idle" | "asking" | "granted" | "denied";

interface Props {
  tenantId: string;
  status: Status;
  locStatus: LocStatus;
  userLoc: { lat: number; lng: number } | null;
  onNewSession: () => void;
  onRequestLocation: () => void;
}

export default function SessionBar({
  tenantId,
  status,
  locStatus,
  userLoc,
  onNewSession,
  onRequestLocation,
}: Props) {
  return (
    <div className="px-4 py-2.5 border-t border-paper-500/60 bg-paper-100 flex items-center gap-2 text-[11.5px]">
      <Pill kind={statusKind(status)} label={statusLabel(status)} />
      <button
        type="button"
        onClick={onRequestLocation}
        className="outline-none focus-visible:ring-2 focus-visible:ring-iri-blue/40 rounded-full"
        title={
          locStatus === "granted" && userLoc
            ? `lat ${userLoc.lat.toFixed(4)}, lng ${userLoc.lng.toFixed(4)}`
            : locStatus === "denied"
            ? "Location blocked — enable in browser settings, then click to retry"
            : locStatus === "asking"
            ? "Asking for location…"
            : "Click to share your location"
        }
      >
        <Pill kind={locKind(locStatus)} label={locLabel(locStatus)} />
      </button>
      <button
        type="button"
        onClick={onNewSession}
        className="ml-auto text-ink-200 hover:text-ink-700 transition-colors"
        title="Start a fresh conversation"
      >
        + new
      </button>
      <span className="text-ink-100">·</span>
      <span className="text-ink-100 truncate" title={tenantId}>
        {tenantId}
      </span>
      <span className="text-ink-100">·</span>
      <Link to="/console" className="text-ink-200 hover:text-ink-700 transition-colors">
        console →
      </Link>
    </div>
  );
}

type PillKind = "ok" | "warn" | "err" | "muted";

function Pill({ kind, label }: { kind: PillKind; label: string }) {
  const dot =
    kind === "ok" ? "bg-sage"
    : kind === "warn" ? "bg-amber animate-pulse-soft"
    : kind === "err" ? "bg-rust"
    : "bg-ink-50";
  const text =
    kind === "ok" ? "text-sage"
    : kind === "warn" ? "text-amber"
    : kind === "err" ? "text-rust"
    : "text-ink-100";
  return (
    <span className={cn("inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full", text)}>
      <span className={cn("size-1.5 rounded-full", dot)} />
      <span>{label}</span>
    </span>
  );
}

function statusKind(s: Status): PillKind {
  switch (s) {
    case "connected": return "ok";
    case "connecting": return "warn";
    case "error": return "err";
    case "closed": return "warn";
    default: return "muted";
  }
}
function statusLabel(s: Status): string { return s; }

function locKind(l: LocStatus): PillKind {
  switch (l) {
    case "granted": return "ok";
    case "asking": return "warn";
    case "denied": return "err";
    default: return "muted";
  }
}
function locLabel(l: LocStatus): string {
  switch (l) {
    case "granted": return "located";
    case "asking": return "locating…";
    case "denied": return "blocked";
    default: return "share location";
  }
}
