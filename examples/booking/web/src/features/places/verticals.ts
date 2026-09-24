/**
 * Vertical metadata — label, accent color, default agent.
 * Single source of truth for the floating MapSearch chips, the Pin colors,
 * the legend, and the AgentStrip's "what is the default" question.
 *
 * Replaced upstream when MA-P3's /v1/places/area returns a vertical taxonomy.
 */
import type { Vertical } from "./types";
import type { AgentSlug } from "../agents/registry";

export interface VerticalMeta {
  vertical: Vertical;
  label: string;
  plural: string;
  /** Solid pin color — HSL background of <Pin>. */
  color: string;
  /** Border color — slightly darker for contrast on the soft Map style. */
  border: string;
  /** Glyph color on the pin. */
  glyph: string;
  /** Default agent the right-rail mounts to when this vertical's pin is picked. */
  defaultAgent: AgentSlug;
}

export const VERTICALS: VerticalMeta[] = [
  {
    vertical: "restaurant",
    label: "Restaurants",
    plural: "restaurants",
    color: "#E26478",
    border: "#B23E54",
    glyph: "#FFFFFF",
    defaultAgent: "reservations",
  },
  {
    vertical: "doctor",
    label: "Doctors",
    plural: "doctors",
    color: "#3B6EA8",
    border: "#234F82",
    glyph: "#FFFFFF",
    defaultAgent: "appointments",
  },
  {
    vertical: "salon",
    label: "Salons",
    plural: "salons",
    color: "#A672E0",
    border: "#7A4FB6",
    glyph: "#FFFFFF",
    defaultAgent: "appointments",
  },
  {
    vertical: "pharmacy",
    label: "Pharmacies",
    plural: "pharmacies",
    color: "#5E8B5E",
    border: "#3F6A3F",
    glyph: "#FFFFFF",
    defaultAgent: "inventory",
  },
  {
    vertical: "gym",
    label: "Gyms",
    plural: "gyms",
    color: "#C97B2A",
    border: "#9A5C1C",
    glyph: "#FFFFFF",
    defaultAgent: "membership",
  },
];

export const VERTICAL_BY_KEY: Record<Vertical, VerticalMeta> = Object.fromEntries(
  VERTICALS.map((v) => [v.vertical, v]),
) as Record<Vertical, VerticalMeta>;

export function metaFor(v: Vertical): VerticalMeta {
  return VERTICAL_BY_KEY[v];
}
