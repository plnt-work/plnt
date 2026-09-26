import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, FieldHint, FieldInput, FieldLabel } from "@/components/ui/Field";
import { useCreateTenant } from "@/lib/queries/onboard";

import { SLUG_RE, SLUG_RULE_TEXT } from "./slug";
import { errText, type ClaimedBusiness } from "./types";

/**
 * Step 3 — pick the subdomain and create the tenant. Slug validity is
 * mirrored client-side; the backend re-validates (422/400/409 render
 * inline). On 201 the parent stores the one-time api_key and advances
 * the URL to ?step=install&tenant=<tid>.
 */
export function SlugStep({
  business,
  onCreated,
}: {
  business: ClaimedBusiness;
  onCreated: (tenantId: string, apiKey: string) => void;
}) {
  const [slug, setSlug] = useState(business.suggestedSlug);
  const create = useCreateTenant();

  const valid = SLUG_RE.test(slug);

  const submit = () => {
    create.mutate(
      {
        slug,
        place_id: business.place_id,
        name: business.name,
        address: business.address,
        lat: business.lat,
        lng: business.lng,
      },
      { onSuccess: (d) => onCreated(d.tenant_id, d.api_key) },
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink-700">Choose your link</h1>
      <p className="text-sm text-ink-200">
        This is the address your customers will chat at, for {business.name}.
      </p>
      <Field>
        <FieldLabel htmlFor="onboard-slug">Your address</FieldLabel>
        <div className="flex items-center gap-2">
          <FieldInput
            id="onboard-slug"
            className="flex-1 font-mono"
            value={slug}
            onChange={(e) => setSlug(e.target.value.toLowerCase())}
            spellCheck={false}
            autoFocus
          />
          <span className="whitespace-nowrap text-sm text-ink-200">.chat.plnt.work</span>
        </div>
        {slug && !valid ? (
          <p className="text-xs text-rust">{SLUG_RULE_TEXT}</p>
        ) : (
          <FieldHint>{SLUG_RULE_TEXT}</FieldHint>
        )}
      </Field>
      <div>
        <Button onClick={submit} disabled={!valid || create.isPending}>
          {create.isPending ? "Creating…" : "Continue"}
        </Button>
      </div>
      {create.isError && <p className="text-sm text-rust">{errText(create.error)}</p>}
    </div>
  );
}
