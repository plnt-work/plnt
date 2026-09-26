import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { Field, FieldInput, FieldLabel } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { OnboardApiError, type Candidate } from "@/lib/api/onboard";
import { useBusinessSearch, useClaimBusiness } from "@/lib/queries/onboard";

import { manualPlaceId } from "./slug";
import { errText, type ClaimedBusiness } from "./types";
import { useDebouncedValue } from "./useDebouncedValue";

/**
 * Step 2 — find and claim the business. Debounced Places search; each
 * candidate is a tappable card. Selecting one calls /claim to get the
 * suggested slug, then hands the combined selection up. When Places
 * returns nothing (or is disabled server-side), a manual name+address
 * form feeds the same path with a `manual:<slug>` sentinel place_id.
 */
export function ClaimStep({ onClaimed }: { onClaimed: (b: ClaimedBusiness) => void }) {
  const [q, setQ] = useState("");
  const debouncedQ = useDebouncedValue(q);
  const searchQ = useBusinessSearch(debouncedQ);
  const claim = useClaimBusiness();

  const [manual, setManual] = useState(false);
  const [manualName, setManualName] = useState("");
  const [manualAddress, setManualAddress] = useState("");

  const claimCandidate = (c: Candidate) => {
    claim.mutate(
      { place_id: c.place_id, name: c.name, address: c.address },
      {
        onSuccess: (d) =>
          onClaimed({
            place_id: c.place_id,
            name: c.name,
            address: c.address,
            lat: c.lat,
            lng: c.lng,
            suggestedSlug: d.slug,
          }),
      },
    );
  };

  const claimManual = (e: FormEvent) => {
    e.preventDefault();
    const name = manualName.trim();
    if (!name) return;
    const address = manualAddress.trim();
    const place_id = manualPlaceId(name);
    claim.mutate(
      { place_id, name, address },
      {
        onSuccess: (d) => onClaimed({ place_id, name, address, suggestedSlug: d.slug }),
      },
    );
  };

  const searching = searchQ.isFetching;
  const candidates = searchQ.data?.candidates ?? [];
  const searchedEmpty =
    searchQ.isSuccess && !searching && debouncedQ.trim().length >= 2 && candidates.length === 0;
  const searchUnavailable = searchQ.isError && !(searchQ.error instanceof OnboardApiError && searchQ.error.status === 401);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink-700">Find your business</h1>
      <Field>
        <FieldLabel htmlFor="onboard-q">Business name and city</FieldLabel>
        <FieldInput
          id="onboard-q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Bakasur Pizza Kitchen, Pune"
          autoFocus
        />
      </Field>

      {searching && (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-14" />
          <Skeleton className="h-14" />
          <Skeleton className="h-14" />
        </div>
      )}

      {!searching && candidates.length > 0 && (
        <ul className="flex flex-col gap-2">
          {candidates.map((c) => (
            <li key={c.place_id}>
              <button
                type="button"
                onClick={() => claimCandidate(c)}
                disabled={claim.isPending}
                className="w-full rounded-md border border-paper-600 bg-white px-4 py-3 text-left transition-colors hover:bg-paper-200 disabled:opacity-50"
              >
                <span className="block text-sm font-medium text-ink-700">{c.name}</span>
                <span className="block text-xs text-ink-100">
                  {c.address}
                  {c.category ? ` · ${c.category.replace(/_/g, " ")}` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {searchQ.error instanceof OnboardApiError && searchQ.error.status === 401 && (
        <p className="text-sm text-rust">{errText(searchQ.error)}</p>
      )}
      {searchUnavailable && (
        <p className="text-sm text-ink-200">Search isn't available right now.</p>
      )}

      {(searchedEmpty || searchUnavailable) && !manual && (
        <p className="text-sm text-ink-200">
          Can't find it?{" "}
          <button
            type="button"
            className="text-iri-blue underline-offset-2 hover:underline"
            onClick={() => setManual(true)}
          >
            Enter your business name manually
          </button>
        </p>
      )}

      {manual && (
        <form onSubmit={claimManual} className="flex flex-col gap-3">
          <Field>
            <FieldLabel htmlFor="onboard-manual-name">Business name</FieldLabel>
            <FieldInput
              id="onboard-manual-name"
              value={manualName}
              onChange={(e) => setManualName(e.target.value)}
              required
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="onboard-manual-address">Address (optional)</FieldLabel>
            <FieldInput
              id="onboard-manual-address"
              value={manualAddress}
              onChange={(e) => setManualAddress(e.target.value)}
            />
          </Field>
          <div>
            <Button type="submit" disabled={claim.isPending || !manualName.trim()}>
              Continue
            </Button>
          </div>
        </form>
      )}

      {claim.isError && <p className="text-sm text-rust">{errText(claim.error)}</p>}
    </div>
  );
}
