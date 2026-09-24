import { mockAvailability } from "@/lib/api/venues";

describe("mockAvailability", () => {
  it("is deterministic for identical inputs", () => {
    const a = mockAvailability("biz-leopold", "2026-07-04", ["s1", "s2"], "t1");
    const b = mockAvailability("biz-leopold", "2026-07-04", ["s1", "s2"], "t1");
    expect(a).toEqual(b);
  });

  it("is invariant to serviceIds order", () => {
    const a = mockAvailability("biz-leopold", "2026-07-04", ["s1", "s2"], "t1");
    const b = mockAvailability("biz-leopold", "2026-07-04", ["s2", "s1"], "t1");
    expect(a).toEqual(b);
  });

  it("changes when the date changes", () => {
    const a = mockAvailability("biz-leopold", "2026-07-04", ["s1"], "t1");
    const b = mockAvailability("biz-leopold", "2026-07-05", ["s1"], "t1");
    expect(a).not.toEqual(b);
  });

  it("changes when the place changes", () => {
    const a = mockAvailability("biz-leopold", "2026-07-04", ["s1"], "t1");
    const b = mockAvailability("biz-bademiya", "2026-07-04", ["s1"], "t1");
    expect(a).not.toEqual(b);
  });

  it("changes when the pro changes", () => {
    const a = mockAvailability("biz-leopold", "2026-07-04", ["s1"], "t1");
    const b = mockAvailability("biz-leopold", "2026-07-04", ["s1"], "t2");
    expect(a).not.toEqual(b);
  });

  it("returns valid HH:mm slots only", () => {
    const a = mockAvailability("biz-leopold", "2026-07-04", ["s1"], "t1");
    for (const slot of a.slots) {
      expect(slot).toMatch(/^\d{2}:\d{2}$/);
    }
  });

  it("returns the requested date in the response", () => {
    const a = mockAvailability("biz-leopold", "2026-07-04", ["s1"], "t1");
    expect(a.date).toBe("2026-07-04");
  });
});
