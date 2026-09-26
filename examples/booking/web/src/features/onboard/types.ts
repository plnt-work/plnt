export const STEP_KEYS = ["signin", "claim", "slug", "install", "menu", "done"] as const;
export type StepKey = (typeof STEP_KEYS)[number];

/** Business selected (or manually entered) in the claim step, plus the
 *  slug the backend suggested for it. In-memory only — a refresh at the
 *  slug step sends the user back to claim (URL carries the step, not the
 *  selection). */
export interface ClaimedBusiness {
  place_id: string;
  name: string;
  address: string;
  lat?: number;
  lng?: number;
  suggestedSlug: string;
}

export function errText(e: unknown): string {
  if (e && typeof e === "object" && "status" in e && "detail" in e) {
    const err = e as { status: number; detail: string };
    if (err.status === 401) return "Your session expired — go back to sign-in.";
    return err.detail;
  }
  return "Request failed — is the API running?";
}
