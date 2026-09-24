import { canAdvanceFrom } from "@/features/booking/cart";
import type { ServiceRef } from "@/features/booking/cart";

const haircut: ServiceRef = { id: "s1", name: "Haircut", duration_min: 30, price_cents: 5000 };

describe("booking flow state machine", () => {
  it("services step blocks advance when cart is empty", () => {
    expect(canAdvanceFrom("services", { services: [], proId: null, slot: null })).toBe(false);
  });

  it("services step allows advance once a service is picked", () => {
    expect(
      canAdvanceFrom("services", { services: [haircut], proId: null, slot: null }),
    ).toBe(true);
  });

  it("professional step blocks advance until a pro is picked", () => {
    expect(
      canAdvanceFrom("professional", { services: [haircut], proId: null, slot: null }),
    ).toBe(false);
    expect(
      canAdvanceFrom("professional", {
        services: [haircut],
        proId: "no-preference",
        slot: null,
      }),
    ).toBe(true);
  });

  it("time step blocks advance until a slot is picked", () => {
    expect(
      canAdvanceFrom("time", {
        services: [haircut],
        proId: "t1",
        slot: null,
      }),
    ).toBe(false);
    expect(
      canAdvanceFrom("time", {
        services: [haircut],
        proId: "t1",
        slot: "10:00",
      }),
    ).toBe(true);
  });

  it("confirm step requires everything", () => {
    expect(
      canAdvanceFrom("confirm", { services: [], proId: null, slot: null }),
    ).toBe(false);
    expect(
      canAdvanceFrom("confirm", { services: [haircut], proId: null, slot: null }),
    ).toBe(false);
    expect(
      canAdvanceFrom("confirm", {
        services: [haircut],
        proId: "t1",
        slot: "10:00",
      }),
    ).toBe(true);
  });

  it("backwards nav doesn't invalidate state — picking a pro still leaves services intact", () => {
    // Simulates: services → professional → back → services.
    // The store itself doesn't mutate on nav; we just assert can-advance
    // stays true for services as long as the array is non-empty.
    const state = { services: [haircut], proId: "t1" as const, slot: null };
    expect(canAdvanceFrom("services", state)).toBe(true);
    expect(canAdvanceFrom("professional", state)).toBe(true);
  });
});
