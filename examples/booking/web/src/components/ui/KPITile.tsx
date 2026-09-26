/**
 * KPITile — single dense metric card for the Overview strip.
 *
 * Vertex-shape: label up top in muted small caps, big numeric value,
 * optional delta (positive = sage, negative = rust) under it. Click is
 * optional; when present the whole tile becomes a button → navigate to
 * the related tab.
 */
import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { cn } from "@/lib/cn";

interface Props {
  label: string;
  value: ReactNode;
  hint?: string;
  delta?: number;
  /** Comparison window label, e.g. "vs 24h ago". */
  deltaWindow?: string;
  onClick?: () => void;
  loading?: boolean;
  className?: string;
}

export function KPITile({
  label, value, hint, delta, deltaWindow, onClick, loading, className,
}: Props) {
  const isButton = !!onClick;
  const Cmp: "button" | "div" = isButton ? "button" : "div";

  return (
    <Cmp
      type={isButton ? "button" : undefined}
      onClick={onClick}
      className={cn(
        "rounded-lg border border-coal-500 bg-coal-600/60 p-4 text-left",
        "transition-colors",
        isButton && "hover:bg-coal-500/60 hover:border-coal-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-iri-blue/40",
        className,
      )}
    >
      <div className="text-[10.5px] uppercase tracking-wide text-coal-200 font-medium">
        {label}
      </div>
      <div className="mt-1.5 text-[26px] leading-none font-semibold text-coal-50 font-mono">
        {loading ? <span className="inline-block h-6 w-16 rounded bg-coal-500 animate-pulse-soft" /> : value}
      </div>
      {(hint || delta !== undefined) && (
        <div className="mt-2 flex items-center gap-2 text-[11px] text-coal-200">
          {delta !== undefined && <DeltaPill delta={delta} window={deltaWindow} />}
          {hint && <span className="truncate">{hint}</span>}
        </div>
      )}
    </Cmp>
  );
}

function DeltaPill({ delta, window }: { delta: number; window?: string }) {
  const Icon = delta > 0 ? ArrowUpRight : delta < 0 ? ArrowDownRight : Minus;
  const tone =
    delta > 0 ? "text-sage" : delta < 0 ? "text-rust" : "text-coal-200";
  const pct = Math.abs(delta).toFixed(0);
  return (
    <span className={cn("inline-flex items-center gap-0.5 font-medium", tone)}>
      <Icon className="size-3" />
      {pct}%{window ? ` ${window}` : ""}
    </span>
  );
}
