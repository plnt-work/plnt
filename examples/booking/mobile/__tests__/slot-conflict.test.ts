import { hasConflict, overlaps, filterAvailable } from "@/features/booking/slot-conflict";

const at = (start: string, duration_min = 30) => ({ start, duration_min });

describe("slot-conflict", () => {
  describe("overlaps", () => {
    it("returns true for slots that start during another", () => {
      expect(overlaps(at("2026-07-04T19:00"), at("2026-07-04T19:15"))).toBe(true);
    });

    it("returns false for back-to-back slots (touching but not overlapping)", () => {
      expect(overlaps(at("2026-07-04T19:00"), at("2026-07-04T19:30"))).toBe(false);
    });

    it("returns false for slots on different days", () => {
      expect(overlaps(at("2026-07-04T19:00"), at("2026-07-05T19:00"))).toBe(false);
    });

    it("respects duration on the longer slot", () => {
      const long = at("2026-07-04T18:00", 120);
      const inside = at("2026-07-04T19:30", 30);
      expect(overlaps(long, inside)).toBe(true);
    });
  });

  describe("hasConflict", () => {
    it("flags a candidate that collides with any existing", () => {
      const existing = [at("2026-07-04T10:00"), at("2026-07-04T14:00")];
      expect(hasConflict(at("2026-07-04T14:15"), existing)).toBe(true);
    });

    it("is false when no existing overlaps", () => {
      const existing = [at("2026-07-04T10:00"), at("2026-07-04T14:00")];
      expect(hasConflict(at("2026-07-04T12:00"), existing)).toBe(false);
    });
  });

  describe("filterAvailable", () => {
    it("drops candidates that conflict with existing", () => {
      const candidates = [
        at("2026-07-04T09:00"),
        at("2026-07-04T10:15"),
        at("2026-07-04T12:00"),
      ];
      const existing = [at("2026-07-04T10:00")];
      const out = filterAvailable(candidates, existing);
      expect(out.map((s) => s.start)).toEqual([
        "2026-07-04T09:00",
        "2026-07-04T12:00",
      ]);
    });
  });
});
