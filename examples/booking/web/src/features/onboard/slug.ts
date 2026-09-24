/** Client-side mirror of the slug rules in surface/onboard.py. */
export const SLUG_RE = /^[a-z0-9][a-z0-9-]{2,40}$/;

export const SLUG_RULE_TEXT =
  "3–41 characters: lowercase letters, numbers and hyphens, starting with a letter or number.";

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 41)
    .replace(/-+$/, "");
}

/**
 * Sentinel place_id for the manual-entry path. The backend's CreateRequest
 * accepts any string for place_id (no Places validation), so a stable,
 * recognizable prefix keeps manual claims distinguishable in tenant.json.
 */
export function manualPlaceId(name: string): string {
  return `manual:${slugify(name) || "unnamed"}`;
}
