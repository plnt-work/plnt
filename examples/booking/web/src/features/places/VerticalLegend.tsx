/**
 * VerticalLegend — color/label legend used both inside the EmptyState
 * (when the right rail has nothing selected) and any future
 * map-legend overlay. Single source so colors don't drift.
 */
import { VERTICALS } from "./verticals";

export default function VerticalLegend() {
  return (
    <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[12px]">
      {VERTICALS.map((v) => (
        <li key={v.vertical} className="flex items-center gap-2 text-ink-200">
          <span
            className="size-2.5 rounded-full"
            style={{ background: v.color, boxShadow: `0 0 0 1px ${v.border}` }}
          />
          <span>{v.label}</span>
        </li>
      ))}
    </ul>
  );
}
