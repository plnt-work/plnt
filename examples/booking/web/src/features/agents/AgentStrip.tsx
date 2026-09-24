/**
 * AgentStrip — segmented control of installed agents for the currently-
 * selected business. The active agent is solid; the rest are outline chips.
 *
 * The default agent is derived from the business's vertical (see
 * features/places/verticals.ts → defaultAgent). The user can pivot mid-
 * conversation; the selection is held in Atlas state and threaded back into
 * the ChatPanel envelope.
 */
import { motion } from "motion/react";

import { cn } from "@/lib/cn";

import { agentsFor, type AgentDef, type AgentSlug } from "./registry";
import type { Vertical } from "../places/types";
import { metaFor } from "../places/verticals";

interface Props {
  vertical: Vertical;
  active: AgentSlug;
  onPick: (slug: AgentSlug) => void;
}

export default function AgentStrip({ vertical, active, onPick }: Props) {
  const options = agentsFor(vertical);
  const accent = metaFor(vertical).color;

  return (
    <div
      role="radiogroup"
      aria-label="Agent"
      className="px-4 pb-3 border-b border-paper-500/60"
    >
      <div className="text-[11px] uppercase tracking-wide text-ink-100 mb-2">Agent</div>
      <div className="flex flex-wrap gap-1.5">
        {options.map((a: AgentDef) => {
          const isActive = a.slug === active;
          return (
            <button
              key={a.slug}
              type="button"
              role="radio"
              aria-checked={isActive}
              onClick={() => onPick(a.slug)}
              title={a.hint}
              className={cn(
                "relative px-3 py-1.5 rounded-full text-[12.5px] font-medium transition-colors outline-none",
                "focus-visible:ring-2 focus-visible:ring-iri-blue/40 focus-visible:ring-offset-1 focus-visible:ring-offset-white",
                isActive
                  ? "text-white"
                  : "text-ink-200 hover:text-ink-700 bg-paper-200 hover:bg-paper-300",
              )}
            >
              {isActive && (
                <motion.span
                  layoutId="agent-strip-active"
                  transition={{ type: "spring", stiffness: 380, damping: 30 }}
                  className="absolute inset-0 rounded-full"
                  style={{ background: accent }}
                />
              )}
              <span className="relative z-10">{a.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
