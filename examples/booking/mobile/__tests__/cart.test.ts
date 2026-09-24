import AsyncStorage from "@react-native-async-storage/async-storage";
import { useCart, totalCents, totalMinutes, type ServiceRef } from "@/features/booking/cart";

const haircut: ServiceRef = { id: "s1", name: "Haircut", duration_min: 30, price_cents: 5000 };
const color: ServiceRef = { id: "s2", name: "Color", duration_min: 90, price_cents: 12000 };

describe("cart", () => {
  beforeEach(async () => {
    useCart.getState().reset();
    await AsyncStorage.clear();
  });

  it("addService is idempotent (no dupes)", () => {
    useCart.getState().setPlace("biz-1");
    useCart.getState().addService(haircut);
    useCart.getState().addService(haircut);
    expect(useCart.getState().services).toHaveLength(1);
  });

  it("toggleService adds then removes", () => {
    useCart.getState().setPlace("biz-1");
    useCart.getState().toggleService(haircut);
    expect(useCart.getState().services).toHaveLength(1);
    useCart.getState().toggleService(haircut);
    expect(useCart.getState().services).toHaveLength(0);
  });

  it("totalCents and totalMinutes sum the cart", () => {
    useCart.getState().setPlace("biz-1");
    useCart.getState().addService(haircut);
    useCart.getState().addService(color);
    const s = useCart.getState();
    expect(totalCents(s)).toBe(17000);
    expect(totalMinutes(s)).toBe(120);
  });

  it("setPlace to a different venue wipes services/pro/slot", () => {
    useCart.getState().setPlace("biz-1");
    useCart.getState().addService(haircut);
    useCart.getState().setPro("t1");
    useCart.getState().setSlot("2026-07-04", "10:00");

    useCart.getState().setPlace("biz-2");
    const s = useCart.getState();
    expect(s.placeId).toBe("biz-2");
    expect(s.services).toEqual([]);
    expect(s.proId).toBeNull();
    expect(s.slot).toBeNull();
  });

  it("setPlace to the same venue preserves state", () => {
    useCart.getState().setPlace("biz-1");
    useCart.getState().addService(haircut);
    useCart.getState().setPlace("biz-1");
    expect(useCart.getState().services).toHaveLength(1);
  });

  it("reset wipes everything", () => {
    useCart.getState().setPlace("biz-1");
    useCart.getState().addService(haircut);
    useCart.getState().setPro("t1");
    useCart.getState().reset();
    const s = useCart.getState();
    expect(s.placeId).toBeNull();
    expect(s.services).toEqual([]);
    expect(s.proId).toBeNull();
    expect(s.slot).toBeNull();
  });

  it("persistence round-trip: state writes to AsyncStorage", async () => {
    useCart.getState().setPlace("biz-1");
    useCart.getState().addService(haircut);
    // The manual subscribe writes synchronously to the AsyncStorage
    // mock; still give it a microtask to drain in case the impl swaps.
    await new Promise((r) => setTimeout(r, 0));
    const raw = await AsyncStorage.getItem("plnt.cart");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.placeId).toBe("biz-1");
    expect(parsed.services).toHaveLength(1);
    expect(parsed.services[0].id).toBe("s1");
  });
});
