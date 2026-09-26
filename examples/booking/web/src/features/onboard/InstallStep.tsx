import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, FieldInput, FieldLabel } from "@/components/ui/Field";
import { OnboardApiError } from "@/lib/api/onboard";
import { useInstallFirstAgent } from "@/lib/queries/onboard";

import { CopyField } from "./CopyField";
import { errText } from "./types";

const AGENT_SLUG = "booking-restaurant";

/**
 * Step 4 — install the pre-selected Table Booking agent with the three
 * Journey-A config fields. The api_key panel renders only when the key
 * is still in memory from the create call — it is shown exactly once.
 * The optional menu upload follows as its own step (MenuStep).
 */
export function InstallStep({
  tenantId,
  apiKey,
  onInstalled,
}: {
  tenantId: string;
  apiKey: string | null;
  onInstalled: () => void;
}) {
  const [partyMin, setPartyMin] = useState("1");
  const [partyMax, setPartyMax] = useState("8");
  const [horizonDays, setHorizonDays] = useState("60");
  const [turnMinutes, setTurnMinutes] = useState("90");
  const install = useInstallFirstAgent();

  const submit = () => {
    install.mutate(
      {
        tenant_id: tenantId,
        slug: AGENT_SLUG,
        config: {
          party_size_min: Number(partyMin) || 1,
          party_size_max: Number(partyMax) || 8,
          booking_horizon_days: Number(horizonDays) || 60,
          turn_minutes: Number(turnMinutes) || 90,
        },
      },
      {
        onSuccess: onInstalled,
        onError: (e) => {
          // 409 = already installed (e.g. retry after a refresh) — done.
          if (e instanceof OnboardApiError && e.status === 409) onInstalled();
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-5">
      {apiKey && (
        <div className="flex flex-col gap-2 rounded-md border border-paper-600 bg-paper-200 p-4">
          <p className="text-sm font-medium text-ink-700">Your API key</p>
          <CopyField value={apiKey} label="API key" />
          <p className="text-xs text-ink-200">
            Save it now — it won't be shown again.
          </p>
        </div>
      )}

      <h1 className="text-2xl font-semibold text-ink-700">Install your first agent</h1>

      <div className="rounded-md border border-ink-700 bg-white px-4 py-3">
        <p className="text-sm font-medium text-ink-700">Table Booking (Restaurant)</p>
        <p className="mt-0.5 text-xs text-ink-100">
          Conversational table booking: checks availability and confirms a slot
          after an explicit customer yes.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <Field>
          <FieldLabel htmlFor="onboard-party-min">Party size</FieldLabel>
          <div className="flex items-center gap-2">
            <FieldInput
              id="onboard-party-min"
              type="number"
              min={1}
              className="w-24"
              value={partyMin}
              onChange={(e) => setPartyMin(e.target.value)}
            />
            <span className="text-sm text-ink-200">to</span>
            <FieldInput
              id="onboard-party-max"
              type="number"
              min={1}
              className="w-24"
              aria-label="Party size maximum"
              value={partyMax}
              onChange={(e) => setPartyMax(e.target.value)}
            />
          </div>
        </Field>
        <Field>
          <FieldLabel htmlFor="onboard-horizon">Booking horizon (days)</FieldLabel>
          <FieldInput
            id="onboard-horizon"
            type="number"
            min={1}
            className="w-24"
            value={horizonDays}
            onChange={(e) => setHorizonDays(e.target.value)}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="onboard-turn">Table turn time (minutes)</FieldLabel>
          <FieldInput
            id="onboard-turn"
            type="number"
            min={15}
            className="w-24"
            value={turnMinutes}
            onChange={(e) => setTurnMinutes(e.target.value)}
          />
        </Field>
      </div>

      <div>
        <Button onClick={submit} disabled={install.isPending}>
          {install.isPending ? "Installing…" : "Install"}
        </Button>
      </div>
      {install.isError && !(install.error instanceof OnboardApiError && install.error.status === 409) && (
        <p className="text-sm text-rust">{errText(install.error)}</p>
      )}
    </div>
  );
}
