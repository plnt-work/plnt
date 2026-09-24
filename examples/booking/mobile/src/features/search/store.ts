// Tiny shared search state — used by Home (display) and the
// modal /search screen (mutation). Two surfaces, one truth, without
// pulling in zustand (reserved for cart per the stack rules) or
// React context (overkill for a 3-field store).
//
// Backed by useSyncExternalStore so consumers re-render on patch.
import { useSyncExternalStore } from "react";
import type { Vertical } from "@web/places/types";

export interface SearchState {
  /** Active treatment / freeform query. null = "All treatments". */
  query: string | null;
  /** Vertical filter from the sheet chip row. null = All. */
  vertical: Vertical | null;
  /** Resolved label for the secondary line of the search pill. */
  locationLabel: string;
  userLoc: { lat: number; lng: number } | null;
}

let state: SearchState = {
  query: null,
  vertical: null,
  locationLabel: "Current location",
  userLoc: null,
};
const listeners = new Set<() => void>();

export function setSearch(patch: Partial<SearchState>): void {
  state = { ...state, ...patch };
  listeners.forEach((cb) => cb());
}

export function getSearch(): SearchState {
  return state;
}

export function useSearch(): SearchState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
    () => state,
  );
}
