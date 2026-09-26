/**
 * Seed data — 13 businesses around Colaba, Mumbai (18.9217, 72.8332),
 * spread across all 5 verticals. Replaced by MA-P3's /v1/places/area
 * endpoint when seeding ships. Names are illustrative; coords are tightly
 * clustered so the demo map opens at a reasonable zoom.
 *
 * Photo URLs are sourced from Wikimedia Commons (documentary, freely
 * licensed). Where the exact venue has a photo on Commons we use it;
 * otherwise we use a category-matching documentary shot (e.g. an Indian
 * pharmacy interior for a Mumbai pharmacy). NO stock photos.
 */
import type { Business } from "./types";

export const SAMPLE_BUSINESSES: Business[] = [
  // ─── Restaurants ────────────────────────────────────────────────────
  {
    place_id: "biz-leopold",
    display_name: "Leopold Cafe",
    vertical: "restaurant",
    lat: 18.9221,
    lng: 72.8313,
    address: "SB Singh Rd, Colaba Causeway",
    rating: 4.2,
    user_ratings: 18420,
    hours: "8am – 12am",
    phone: "+91 22 2282 8185",
    web: "https://leopoldcafe.com",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/8/8b/LeopoldCafe_gobeirne.jpg",
      "https://upload.wikimedia.org/wikipedia/commons/1/1c/LeopoldCafe2_gobeirne.jpg",
    ],
    menu_highlights: [
      { name: "Chicken stroganoff", price: "₹520", note: "house classic" },
      { name: "Beef chilli fry", price: "₹560" },
      { name: "Kingfisher pitcher", price: "₹480" },
      { name: "Chocolate sizzler", price: "₹390" },
    ],
  },
  {
    place_id: "biz-bademiya",
    display_name: "Bademiya",
    vertical: "restaurant",
    lat: 18.9246,
    lng: 72.8331,
    address: "Tulloch Rd, behind Taj Hotel",
    rating: 4.3,
    user_ratings: 9820,
    hours: "7pm – 2am",
    phone: "+91 22 2284 8038",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/1/11/Bademiya_restaurant%2C_Mumbai.jpg",
      "https://upload.wikimedia.org/wikipedia/commons/a/aa/Bagdadi_Restaurant%2C_Colaba%2C_Mumbai.jpg",
    ],
    menu_highlights: [
      { name: "Seekh kebab roll", price: "₹220", note: "the reason people queue" },
      { name: "Chicken tikka roll", price: "₹240" },
      { name: "Mutton bhuna roll", price: "₹280" },
      { name: "Bademiya special baida roti", price: "₹260" },
    ],
  },
  {
    place_id: "biz-cafemondegar",
    display_name: "Cafe Mondegar",
    vertical: "restaurant",
    lat: 18.9226,
    lng: 72.8319,
    address: "Metro House, Colaba Causeway",
    rating: 4.1,
    user_ratings: 14110,
    hours: "8am – 12am",
    phone: "+91 22 2202 0591",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/4/4b/Cafe_Mondegar.JPG",
      "https://upload.wikimedia.org/wikipedia/commons/e/e8/Cafe_Mondegar_bar_with_mural.JPG",
    ],
    menu_highlights: [
      { name: "Mondy's all-day breakfast", price: "₹420" },
      { name: "Chicken sizzler", price: "₹540" },
      { name: "Mutton biryani", price: "₹480" },
      { name: "Jukebox beer pitcher", price: "₹450" },
    ],
  },
  {
    place_id: "biz-thaihouse",
    display_name: "Thai House",
    vertical: "restaurant",
    lat: 18.9197,
    lng: 72.8351,
    address: "Strand Rd, Colaba",
    rating: 4.4,
    user_ratings: 1240,
    hours: "12pm – 11pm",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/f/f5/Pad_Thai_%2824904587663%29.jpg",
      "https://upload.wikimedia.org/wikipedia/commons/1/1b/Panang_Curry_%283250505131%29.jpg",
    ],
    menu_highlights: [
      { name: "Pad thai (prawn)", price: "₹580" },
      { name: "Panang curry", price: "₹620" },
      { name: "Tom kha gai", price: "₹460" },
      { name: "Mango sticky rice", price: "₹320" },
    ],
  },

  // ─── Doctors ────────────────────────────────────────────────────────
  {
    place_id: "biz-saifeehealth",
    display_name: "Saifee Health Clinic",
    vertical: "doctor",
    lat: 18.9237,
    lng: 72.8298,
    address: "1st floor, Maker Chambers, Colaba",
    rating: 4.6,
    user_ratings: 412,
    hours: "Mon–Sat 9am – 7pm",
    phone: "+91 22 2202 7088",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/3/3e/Saifi_Hospital.jpg",
      "https://upload.wikimedia.org/wikipedia/commons/3/3c/Hinduja_Healthcare_Surgical%2C_Khar%2C_Mumbai.jpg",
    ],
    specialties: ["General medicine", "Diabetology", "Cardiology consult", "Diagnostics"],
  },
  {
    place_id: "biz-bombayhospital-annex",
    display_name: "Bombay Hospital Annex",
    vertical: "doctor",
    lat: 18.9182,
    lng: 72.8294,
    address: "Cuffe Parade, Colaba",
    rating: 4.4,
    user_ratings: 1502,
    hours: "24 hours",
    phone: "+91 22 2206 7676",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/d/d4/Gokuldas_Tejpal_Hospital.jpg",
      "https://upload.wikimedia.org/wikipedia/commons/c/c1/Homi_Bhabha_Block_at_Tata_Memorial_Hospital_Mumbai.jpg",
    ],
    specialties: ["Emergency", "Orthopaedics", "Paediatrics", "ENT"],
  },

  // ─── Salons ─────────────────────────────────────────────────────────
  {
    place_id: "biz-truefitt",
    display_name: "Truefitt & Hill",
    vertical: "salon",
    lat: 18.9211,
    lng: 72.8321,
    address: "The Taj Mahal Palace, lobby level",
    rating: 4.7,
    user_ratings: 318,
    hours: "10am – 8pm",
    phone: "+91 22 6665 3366",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/2/2b/The_Taj_Mahal_Palace_Hotel.jpg",
      "https://upload.wikimedia.org/wikipedia/commons/b/b3/Taj_Mahal_Palace_Hotel_photo.jpg",
    ],
    services: [
      { name: "Classic gentleman's cut", price: "₹2,800", duration: "45m" },
      { name: "Royal hot-towel shave", price: "₹3,400", duration: "30m" },
      { name: "Beard sculpt", price: "₹1,800", duration: "25m" },
      { name: "Scalp massage", price: "₹2,200", duration: "30m" },
    ],
  },
  {
    place_id: "biz-juiceandscissors",
    display_name: "Juice & Scissors",
    vertical: "salon",
    lat: 18.9258,
    lng: 72.8312,
    address: "Wodehouse Rd, Colaba",
    rating: 4.3,
    user_ratings: 612,
    hours: "10am – 9pm",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/a/ac/BarberShopKolhapur.JPG",
      "https://upload.wikimedia.org/wikipedia/commons/7/72/Pune_WadarWadi_Area_-_Shaving_Saloon.jpg",
    ],
    services: [
      { name: "Haircut", price: "₹650", duration: "30m" },
      { name: "Beard trim", price: "₹250", duration: "15m" },
      { name: "Hair colour", price: "₹1,400", duration: "60m" },
      { name: "Head massage", price: "₹450", duration: "20m" },
    ],
  },

  // ─── Pharmacies ─────────────────────────────────────────────────────
  {
    place_id: "biz-wellness-pharmacy",
    display_name: "Wellness Pharmacy",
    vertical: "pharmacy",
    lat: 18.9203,
    lng: 72.8337,
    address: "Apollo Bunder, Colaba",
    rating: 4.5,
    user_ratings: 224,
    hours: "8am – 11pm",
    phone: "+91 22 2284 4001",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/7/73/Small_pharmacy_in_Kerala.jpg",
      "https://upload.wikimedia.org/wikipedia/commons/0/0a/India_-_Varanasi_pharmacy_-_0822.jpg",
    ],
    categories: ["Prescription refill", "OTC pain relief", "Cold + cough", "Home delivery"],
  },
  {
    place_id: "biz-noble-chemist",
    display_name: "Noble Chemist",
    vertical: "pharmacy",
    lat: 18.9189,
    lng: 72.8319,
    address: "SP Mukherjee Chowk, Colaba",
    rating: 4.2,
    user_ratings: 87,
    hours: "9am – 10:30pm",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/4/48/Pharmacy%2C_Gangtok%2C_India_%288083933798%29.jpg",
      "https://upload.wikimedia.org/wikipedia/commons/2/20/Medical_store_in_Paliem%2C_North_Goa%2C_March%2C_2018.jpg",
    ],
    categories: ["Prescription refill", "Diabetes care", "Generic substitutes", "Walk-in only"],
  },
  {
    place_id: "biz-medplus-cuffe",
    display_name: "MedPlus — Cuffe Parade",
    vertical: "pharmacy",
    lat: 18.9162,
    lng: 72.8273,
    address: "Cuffe Parade Rd",
    rating: 4.1,
    user_ratings: 312,
    hours: "8am – 11pm",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/8/89/Medplus_pharmacy.jpg",
      "https://upload.wikimedia.org/wikipedia/commons/8/83/Medplus_store.JPG",
    ],
    categories: ["Prescription refill", "Vitamins + supplements", "Home delivery", "Express pickup"],
  },

  // ─── Gyms ───────────────────────────────────────────────────────────
  {
    place_id: "biz-talwalkars-colaba",
    display_name: "Talwalkars Better Value Fitness",
    vertical: "gym",
    lat: 18.9168,
    lng: 72.8308,
    address: "Cuffe Parade, Colaba",
    rating: 4.0,
    user_ratings: 540,
    hours: "5am – 11pm",
    phone: "+91 22 6655 1234",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/e/e0/Gym_at_Universal_Ai_University.jpg",
    ],
    classes: ["Strength + conditioning", "Cardio floor", "Group HIIT", "Day pass"],
  },
  {
    place_id: "biz-cult-colaba",
    display_name: "Cult Fit — Colaba",
    vertical: "gym",
    lat: 18.9244,
    lng: 72.8290,
    address: "Best Marg, Colaba",
    rating: 4.4,
    user_ratings: 1130,
    hours: "6am – 10pm",
    photos: [
      "https://upload.wikimedia.org/wikipedia/commons/1/10/Indian_Gym%2C_Sec.7_Roop_Ngr._-_panoramio.jpg",
    ],
    classes: ["Boxing", "Yoga", "S+C", "Dance fitness", "Trial class"],
  },
];

export const COLABA_CENTER = { lat: 18.9217, lng: 72.8332 };
