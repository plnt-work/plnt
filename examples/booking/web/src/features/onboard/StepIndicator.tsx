import { cn } from "@/lib/cn";

import { STEP_KEYS, type StepKey } from "./types";

const LABELS: Record<StepKey, string> = {
  signin: "Sign in",
  claim: "Your business",
  slug: "Your link",
  install: "First agent",
  menu: "Menu",
  done: "Share",
};

export function StepIndicator({ current }: { current: StepKey }) {
  const idx = STEP_KEYS.indexOf(current);
  return (
    <ol className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-100">
      {STEP_KEYS.map((key, i) => (
        <li
          key={key}
          className={cn("flex items-center gap-1.5", i === idx && "font-medium text-ink-700")}
          aria-current={i === idx ? "step" : undefined}
        >
          <span
            className={cn(
              "grid size-5 place-items-center rounded-full border text-[11px]",
              i < idx
                ? "border-ink-700 bg-ink-700 text-paper-100"
                : i === idx
                  ? "border-ink-700"
                  : "border-paper-600",
            )}
          >
            {i + 1}
          </span>
          {LABELS[key]}
        </li>
      ))}
    </ol>
  );
}
