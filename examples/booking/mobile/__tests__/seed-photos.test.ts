// Guards the curated-photo invariant on the shared seed. Each business
// must carry at least one photo URL, and every URL must parse as a
// valid `https://` URL. The reachability check is deliberately offline-
// only — CI shouldn't depend on Wikimedia uptime.
import { SAMPLE_BUSINESSES } from "@web/places/sample-businesses";

describe("SAMPLE_BUSINESSES.photos[]", () => {
  it("every business has at least one photo", () => {
    const missing = SAMPLE_BUSINESSES.filter(
      (b) => !Array.isArray(b.photos) || b.photos.length === 0,
    ).map((b) => b.place_id);
    expect(missing).toEqual([]);
  });

  it("every photo URL parses and uses https", () => {
    const bad: string[] = [];
    for (const b of SAMPLE_BUSINESSES) {
      for (const url of b.photos ?? []) {
        try {
          const parsed = new URL(url);
          if (parsed.protocol !== "https:") bad.push(`${b.place_id}: ${url}`);
        } catch {
          bad.push(`${b.place_id}: ${url}`);
        }
      }
    }
    expect(bad).toEqual([]);
  });
});
