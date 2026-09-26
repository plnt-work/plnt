/**
 * EmptyState — shown in the right rail when no business is selected.
 * Spelled out as "what to do", not decorative AI-spark filler.
 */
import { MapPin } from "lucide-react";

import VerticalLegend from "./VerticalLegend";

export default function EmptyState() {
  return (
    <div className="flex flex-col items-stretch h-full p-6">
      <div className="flex-1 flex flex-col items-center justify-center text-center gap-3">
        <div className="size-10 rounded-full bg-paper-200 text-ink-200 grid place-items-center">
          <MapPin className="size-5" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-ink-700">
            Pick a business on the map
          </h3>
          <p className="mt-1 text-sm text-ink-100 max-w-[260px]">
            Click any pin to open its rail — agents for that vertical mount
            on the right, and you can chat with the one that fits.
          </p>
        </div>
      </div>

      <div className="border-t border-paper-500/60 pt-4">
        <div className="text-[11px] uppercase tracking-wide text-ink-100 mb-2">
          Pin colors
        </div>
        <VerticalLegend />
      </div>
    </div>
  );
}
