// Pure venue-filter — kept side-effect-free so the test suite can pin
// behavior before any UI gets opinionated. Used by Home to drive both
// the marker set and the sheet's FlashList off the same `filtered`.
import type { Business, Vertical } from "@web/places/types";

export interface VenueFilter {
  vertical: Vertical | null;
  /** Substring (case-insensitive) match against display_name / address. */
  query: string | null;
  /** Inclusive lower bound on rating. */
  minRating?: number;
}

export function filterVenues(all: Business[], f: VenueFilter): Business[] {
  const q = f.query?.trim().toLowerCase() || null;
  return all.filter((b) => {
    if (f.vertical && b.vertical !== f.vertical) return false;
    if (q) {
      const hay = `${b.display_name} ${b.address}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (typeof f.minRating === "number" && b.rating < f.minRating) return false;
    return true;
  });
}
