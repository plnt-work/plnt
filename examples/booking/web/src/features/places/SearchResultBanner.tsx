/**
 * SearchResultBanner — sticky top-of-map banner for the no-selection state.
 *
 * Rendered when the MA stream emits a `search_results` action and no
 * business is selected. Sits absolute-positioned at the top of the map
 * area (above MapSearch). Tapping a chip switches the rail to that
 * business; X dismisses the banner and clears the parent's search query.
 *
 * If `matches` is missing, falls back to rendering place_ids verbatim —
 * the MA stream may ship richer metadata later but a bare list is still
 * useful.
 */
import { Sparkles, X } from "lucide-react";

import type { SearchMatch } from "../chat/ChatPanel";

interface Props {
  note?: string;
  matches: SearchMatch[];
  onPick: (placeId: string) => void;
  onDismiss: () => void;
}

export default function SearchResultBanner({ note, matches, onPick, onDismiss }: Props) {
  if (matches.length === 0) return null;
  const heading = note || `Found ${matches.length} ${matches.length === 1 ? "place" : "places"}`;

  return (
    <div
      className="
        absolute top-4 left-4 right-4 z-20
        rounded-xl bg-white/96 backdrop-blur-md
        shadow-lg ring-1 ring-paper-500/60
        p-3 space-y-2
      "
    >
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-iri-blue shrink-0" aria-hidden />
        <div className="flex-1 text-sm font-medium text-ink-700 truncate">{heading}</div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Clear search results"
          className="text-ink-100 hover:text-ink-700 transition-colors"
        >
          <X className="size-3.5" />
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {matches.map((m) => (
          <button
            key={m.place_id}
            type="button"
            onClick={() => onPick(m.place_id)}
            className="h-7 px-2.5 rounded-full text-[12px] font-medium border border-paper-600 bg-white text-ink-700 hover:border-iri-blue hover:text-iri-blue transition-colors"
          >
            {m.display_name}
          </button>
        ))}
      </div>
    </div>
  );
}
