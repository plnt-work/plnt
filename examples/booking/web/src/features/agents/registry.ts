/**
 * Agent registry — the small fixed set of micro-agents the right rail can
 * mount per business. Each business's vertical maps to a default agent in
 * features/places/verticals.ts; the AgentStrip surfaces the rest as a
 * segmented control so the user can pivot mid-conversation.
 *
 * The `slug` is what gets serialized into the outgoing message envelope
 *   `[biz:<place_id> agent:<slug>] <user text>`
 * so the backend MA stream can route to the right micro-agent worker. Keep
 * the slug stable across UI rewrites.
 */
import type { Vertical } from "../places/types";

export type AgentSlug =
  | "reservations"
  | "appointments"
  | "menu"
  | "inventory"
  | "membership"
  | "concierge";

export interface AgentDef {
  slug: AgentSlug;
  label: string;
  /** One-line description shown in the strip tooltip. */
  hint: string;
  /** Which verticals this agent applies to. */
  verticals: Vertical[];
  /** Composer placeholder text shown when this agent is active. */
  placeholder: string;
  /** Suggested-prompt chips shown in ChatPanel's empty state. Each chip
   *  is tappable and sends the literal text as a real chat turn. Keep
   *  4 short ones — the rail is 420px wide. */
  prompts: string[];
}

export const AGENTS: AgentDef[] = [
  {
    slug: "reservations",
    label: "Reservations",
    hint: "Check availability, hold tables, confirm bookings.",
    verticals: ["restaurant"],
    placeholder: "Table for two tonight at 8pm…",
    prompts: [
      "Table for 2 tonight at 8pm",
      "What's available tomorrow evening?",
      "Any patio seating this Friday?",
      "Earliest dinner slot today",
    ],
  },
  {
    slug: "menu",
    label: "Menu",
    hint: "Browse dishes, prices, dietary tags. No mutation.",
    verticals: ["restaurant"],
    placeholder: "What's good here?",
    prompts: [
      "Signature dishes",
      "Anything vegetarian?",
      "Under ₹500 mains",
      "What pairs with a Kingfisher?",
    ],
  },
  {
    slug: "appointments",
    label: "Appointments",
    hint: "Find slots and book with the practitioner / stylist.",
    verticals: ["doctor", "salon"],
    placeholder: "Earliest slot this week…",
    prompts: [
      "Earliest slot this week",
      "Saturday morning?",
      "Walk-in possible today?",
      "Book the next available 30-min",
    ],
  },
  {
    slug: "inventory",
    label: "Inventory",
    hint: "Stock check, refill requests, prescription handoff.",
    verticals: ["pharmacy"],
    placeholder: "Do you have ibuprofen 400mg?",
    prompts: [
      "Do you have ibuprofen 400mg?",
      "Refill my prescription",
      "Home delivery to Cuffe Parade?",
      "Generic substitute for Crocin",
    ],
  },
  {
    slug: "membership",
    label: "Membership",
    hint: "Plans, day-passes, class sign-ups.",
    verticals: ["gym"],
    placeholder: "Day pass for today…",
    prompts: [
      "Day pass for today",
      "Monthly plans",
      "Trial class — what's available?",
      "First-timer offer?",
    ],
  },
  {
    slug: "concierge",
    label: "Concierge",
    hint: "Open-ended questions: hours, location, recommendations.",
    verticals: ["restaurant", "doctor", "salon", "pharmacy", "gym"],
    placeholder: "Ask anything about this place…",
    prompts: [
      "What time do they close today?",
      "Is parking available?",
      "How busy is it right now?",
      "Best time to visit?",
    ],
  },
];

const BY_SLUG: Record<AgentSlug, AgentDef> = Object.fromEntries(
  AGENTS.map((a) => [a.slug, a]),
) as Record<AgentSlug, AgentDef>;

export function agentsFor(vertical: Vertical): AgentDef[] {
  return AGENTS.filter((a) => a.verticals.includes(vertical));
}

export function agentBySlug(slug: AgentSlug): AgentDef {
  return BY_SLUG[slug];
}
