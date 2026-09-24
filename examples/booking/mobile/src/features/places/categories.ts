// Mobile category chips — six tiles surfacing in the Home sheet's
// filter row. The vertical mapping is intentionally narrow: Hair /
// Nails / Brows / Makeup all bucket to salon, Medical to doctor, All
// drops the vertical filter entirely.
//
// `iconForVertical` is the reverse lookup used by map MarkerPill so
// the marker icon stays consistent with the chip the user just tapped.
import type { Vertical } from "@web/places/types";
import {
  Sparkles,
  Scissors,
  Hand,
  Eye,
  Palette,
  Stethoscope,
  type LucideIcon,
} from "lucide-react-native";

export interface CategoryDef {
  key: string;
  label: string;
  icon: LucideIcon;
  vertical: Vertical | null;
}

export const CATEGORIES: CategoryDef[] = [
  { key: "all", label: "All", icon: Sparkles, vertical: null },
  { key: "hair", label: "Hair", icon: Scissors, vertical: "salon" },
  { key: "nails", label: "Nails", icon: Hand, vertical: "salon" },
  { key: "brows", label: "Brows", icon: Eye, vertical: "salon" },
  { key: "makeup", label: "Makeup", icon: Palette, vertical: "salon" },
  { key: "medical", label: "Medical", icon: Stethoscope, vertical: "doctor" },
];

const VERTICAL_ICON: Record<Vertical, LucideIcon> = {
  salon: Scissors,
  doctor: Stethoscope,
  restaurant: Sparkles,
  pharmacy: Sparkles,
  gym: Sparkles,
};

export function iconForVertical(v: Vertical | null): LucideIcon {
  if (!v) return Sparkles;
  return VERTICAL_ICON[v] ?? Sparkles;
}
