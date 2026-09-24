import { filterVenues } from "@/features/places/filter";
import type { Business } from "@web/places/types";

const venues: Business[] = [
  { place_id: "a", display_name: "Anna's Salon", vertical: "salon", lat: 0, lng: 0, address: "Main St", rating: 4.6, user_ratings: 100 },
  { place_id: "b", display_name: "Beta Clinic", vertical: "doctor", lat: 0, lng: 0, address: "Park Ave", rating: 4.2, user_ratings: 50 },
  { place_id: "c", display_name: "City Cuts", vertical: "salon", lat: 0, lng: 0, address: "Oak Rd", rating: 3.9, user_ratings: 20 },
];

describe("filterVenues", () => {
  it("returns all when filter is empty", () => {
    expect(filterVenues(venues, { vertical: null, query: null }).length).toBe(3);
  });

  it("narrows to a single vertical", () => {
    const out = filterVenues(venues, { vertical: "salon", query: null });
    expect(out.map((v) => v.place_id)).toEqual(["a", "c"]);
  });

  it("matches query against display_name", () => {
    const out = filterVenues(venues, { vertical: null, query: "anna" });
    expect(out.map((v) => v.place_id)).toEqual(["a"]);
  });

  it("matches query against address", () => {
    const out = filterVenues(venues, { vertical: null, query: "park" });
    expect(out.map((v) => v.place_id)).toEqual(["b"]);
  });

  it("query is case-insensitive", () => {
    const out = filterVenues(venues, { vertical: null, query: "ANNA" });
    expect(out.map((v) => v.place_id)).toEqual(["a"]);
  });

  it("combines vertical + query", () => {
    const out = filterVenues(venues, { vertical: "salon", query: "cuts" });
    expect(out.map((v) => v.place_id)).toEqual(["c"]);
  });

  it("respects minRating", () => {
    const out = filterVenues(venues, { vertical: null, query: null, minRating: 4.5 });
    expect(out.map((v) => v.place_id)).toEqual(["a"]);
  });

  it("returns empty when no venue matches", () => {
    const out = filterVenues(venues, { vertical: "gym", query: null });
    expect(out).toEqual([]);
  });
});
