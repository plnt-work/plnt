// Booking cart — single global cart (one venue at a time). Persisted
// to AsyncStorage so a navigation away mid-flow recovers selections.
//
// We DON'T use zustand's `persist` middleware: its barrel pulls in the
// devtools middleware which contains `import.meta.env` (Vite syntax)
// that breaks the web bundle parse. A 15-line subscribe-then-write
// pattern gives us the same recovery behavior without that import chain.
//
// Switching to a different venue (setPlace with a different placeId)
// hard-resets services / pro / slot — the cart is per-venue.
import { create } from "zustand";
import AsyncStorage from "@react-native-async-storage/async-storage";

export interface ServiceRef {
  id: string;
  name: string;
  duration_min: number;
  price_cents: number;
}

export type ProSelection = string | "no-preference";

interface CartState {
  placeId: string | null;
  services: ServiceRef[];
  proId: ProSelection | null;
  /** ISO "HH:mm" slot on the picked date. */
  slot: string | null;
  /** ISO "YYYY-MM-DD" date for the slot. */
  date: string | null;

  setPlace(placeId: string): void;
  addService(s: ServiceRef): void;
  removeService(id: string): void;
  toggleService(s: ServiceRef): void;
  setPro(id: ProSelection): void;
  setSlot(date: string, slot: string): void;
  reset(): void;
  /** Internal — used by hydration. Avoids triggering the per-venue wipe
   *  guard in setPlace when restoring from disk. */
  _hydrate(snapshot: Partial<CartSnapshot>): void;
}

interface CartSnapshot {
  placeId: string | null;
  services: ServiceRef[];
  proId: ProSelection | null;
  slot: string | null;
  date: string | null;
}

const initial: CartSnapshot = {
  placeId: null,
  services: [],
  proId: null,
  slot: null,
  date: null,
};

const STORAGE_KEY = "plnt.cart";

export const useCart = create<CartState>()((set, get) => ({
  ...initial,
  setPlace(placeId) {
    const cur = get();
    if (cur.placeId === placeId) return;
    // Different venue → wipe everything else so a stale slot can't
    // bleed across venues.
    set({ ...initial, placeId });
  },
  addService(s) {
    const services = get().services;
    if (services.some((x) => x.id === s.id)) return;
    set({ services: [...services, s] });
  },
  removeService(id) {
    set({ services: get().services.filter((s) => s.id !== id) });
  },
  toggleService(s) {
    const services = get().services;
    if (services.some((x) => x.id === s.id)) {
      set({ services: services.filter((x) => x.id !== s.id) });
    } else {
      set({ services: [...services, s] });
    }
  },
  setPro(id) {
    set({ proId: id });
  },
  setSlot(date, slot) {
    set({ date, slot });
  },
  reset() {
    set({ ...initial });
  },
  _hydrate(snapshot) {
    set({ ...initial, ...snapshot });
  },
}));

// ─── persistence — manual subscribe + AsyncStorage ───────────────────
// Read once at module-load (async); subsequent writes happen on every
// state change. The persisted shape mirrors `partialize` from before.

function snapshot(s: CartState): CartSnapshot {
  return {
    placeId: s.placeId,
    services: s.services,
    proId: s.proId,
    slot: s.slot,
    date: s.date,
  };
}

let hydrated = false;

void (async () => {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<CartSnapshot>;
      useCart.getState()._hydrate(parsed);
    }
  } catch {
    // corrupted snapshot — drop it
  } finally {
    hydrated = true;
  }
})();

useCart.subscribe((state) => {
  if (!hydrated) return; // skip pre-hydration writes
  void AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot(state))).catch(() => {});
});

/** Derived total in cents — kept as a selector so the persisted snapshot
 *  isn't bloated with a redundant field. */
export function totalCents(s: { services: ServiceRef[] }): number {
  return s.services.reduce((acc, x) => acc + x.price_cents, 0);
}

/** Derived total duration in minutes. */
export function totalMinutes(s: { services: ServiceRef[] }): number {
  return s.services.reduce((acc, x) => acc + x.duration_min, 0);
}

/** State machine: which step can we advance to from `current`? */
export type BookingStep = "services" | "professional" | "time" | "confirm";

export function canAdvanceFrom(
  step: BookingStep,
  s: { services: ServiceRef[]; proId: ProSelection | null; slot: string | null },
): boolean {
  switch (step) {
    case "services":
      return s.services.length > 0;
    case "professional":
      return s.proId !== null;
    case "time":
      return s.slot !== null;
    case "confirm":
      return s.services.length > 0 && s.proId !== null && s.slot !== null;
  }
}
