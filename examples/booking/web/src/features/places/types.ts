export type Vertical =
  | "restaurant"
  | "doctor"
  | "salon"
  | "pharmacy"
  | "gym";

export interface Business {
  place_id: string;
  display_name: string;
  vertical: Vertical;
  lat: number;
  lng: number;
  address: string;
  rating: number;
  user_ratings: number;
  photo_uri?: string;
  /** Hero/carousel images. Sourced from Wikimedia Commons (preferred)
   *  or the venue's official site. Mobile renders these in VenueHero;
   *  web BusinessHeader still consumes `photo_uri` for now. */
  photos?: string[];
  hours?: string;
  phone?: string;
  web?: string;

  // ─── Vertical-specific details ────────────────────────────────────
  // Optional; when present the right-rail BusinessDetails surface
  // renders a section per applicable field. All entries are tappable
  // and dispatch a real chat message via ChatPanel — there is no
  // decorative-only data here. Seed today, MA-stream-driven later.

  /** Restaurant: signature dishes the agent should know about. */
  menu_highlights?: MenuItem[];
  /** Doctor: practitioner specialties / focus areas. */
  specialties?: string[];
  /** Salon: bookable services with optional price + duration. */
  services?: ServiceItem[];
  /** Pharmacy: categories the chemist commonly stocks / delivers. */
  categories?: string[];
  /** Gym: classes or amenities the membership unlocks. */
  classes?: string[];
}

export interface MenuItem {
  name: string;
  price?: string;
  note?: string;
}

export interface ServiceItem {
  name: string;
  price?: string;
  duration?: string;
}
