/**
 * MapSearch — floating "search + filter" panel pinned top-left of the map.
 *
 * Composes with the parent's `filter` state:
 *   - Text input matches `display_name` (case-insensitive)
 *   - Vertical chips single-select; "All" resets to no vertical filter
 *
 * `resultCount` is the post-filter count — parent computes it from the
 * source list, we just render. This keeps the search agnostic to the
 * source (seed today, /v1/places/area tomorrow).
 */
import { Search, X } from "lucide-react";

import { cn } from "@/lib/cn";

import type { Vertical } from "./types";
import { VERTICALS } from "./verticals";

interface Props {
  query: string;
  onQueryChange: (v: string) => void;
  vertical: Vertical | null;
  onVerticalChange: (v: Vertical | null) => void;
  resultCount: number;
}

export default function MapSearch({
  query,
  onQueryChange,
  vertical,
  onVerticalChange,
  resultCount,
}: Props) {
  return (
    <div
      className="
        absolute top-4 left-4 z-10
        w-[340px] max-w-[calc(100%-32px)]
        rounded-xl bg-white/96 backdrop-blur-md
        shadow-lg ring-1 ring-paper-500/60
        p-3 space-y-2.5
      "
    >
      <div className="flex items-center gap-2 rounded-md border border-paper-500 bg-white px-2.5 py-1.5 transition-colors focus-within:border-iri-blue focus-within:ring-2 focus-within:ring-iri-blue/25">
        <Search className="size-4 text-ink-100 shrink-0" aria-hidden />
        <input
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Search businesses…"
          className="flex-1 bg-transparent outline-none text-sm text-ink-700 placeholder:text-ink-100"
          autoComplete="off"
          spellCheck={false}
        />
        {query && (
          <button
            type="button"
            onClick={() => onQueryChange("")}
            aria-label="Clear search"
            className="text-ink-100 hover:text-ink-700 transition-colors"
          >
            <X className="size-3.5" />
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Chip
          active={vertical === null}
          onClick={() => onVerticalChange(null)}
          label="All"
          accent="#0E1116"
          border="#0E1116"
        />
        {VERTICALS.map((v) => (
          <Chip
            key={v.vertical}
            active={vertical === v.vertical}
            onClick={() => onVerticalChange(vertical === v.vertical ? null : v.vertical)}
            label={v.label}
            accent={v.color}
            border={v.border}
          />
        ))}
      </div>

      <div className="text-[11px] text-ink-100 px-0.5">
        {resultCount} {resultCount === 1 ? "result" : "results"}
      </div>
    </div>
  );
}

function Chip({
  active,
  onClick,
  label,
  accent,
  border,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  accent: string;
  border: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "h-7 px-2.5 rounded-full text-[12px] font-medium border transition-colors outline-none",
        "focus-visible:ring-2 focus-visible:ring-iri-blue/40",
      )}
      style={
        active
          ? { background: accent, borderColor: border, color: "#FFFFFF" }
          : { background: "transparent", borderColor: "var(--color-paper-500)", color: "var(--color-ink-200)" }
      }
    >
      {label}
    </button>
  );
}
