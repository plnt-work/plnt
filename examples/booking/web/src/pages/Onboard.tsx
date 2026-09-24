/**
 * Onboard — merchant onboarding wizard (Journey A frontend, slice 5b).
 *
 * URL contract: /onboard?step=signin|claim|slug|install|menu|done drives
 * the wizard so refresh and back/forward work; install/menu/done also
 * carry ?tenant=<tid> once the tenant exists. In-memory only: the claimed
 * business (refresh at ?step=slug falls back to claim) and the one-time
 * api_key (shown once by design — a refresh loses it, the backend never
 * re-issues it).
 */
import { useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { ClaimStep } from "../features/onboard/ClaimStep";
import { DoneStep } from "../features/onboard/DoneStep";
import { InstallStep } from "../features/onboard/InstallStep";
import { MenuStep } from "../features/onboard/MenuStep";
import { SignInStep } from "../features/onboard/SignInStep";
import { SlugStep } from "../features/onboard/SlugStep";
import { StepIndicator } from "../features/onboard/StepIndicator";
import {
  STEP_KEYS,
  type ClaimedBusiness,
  type StepKey,
} from "../features/onboard/types";
import { Skeleton } from "../components/ui/Skeleton";
import { useOnboardMe } from "../lib/queries/onboard";

export default function Onboard() {
  const [params, setParams] = useSearchParams();
  const rawStep = params.get("step") ?? "signin";
  const step: StepKey = (STEP_KEYS as readonly string[]).includes(rawStep)
    ? (rawStep as StepKey)
    : "signin";
  const tenantId = params.get("tenant");

  const meQ = useOnboardMe();

  const [business, setBusiness] = useState<ClaimedBusiness | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);

  const go = (next: StepKey, tenant?: string) => {
    const p = new URLSearchParams({ step: next });
    const tid = tenant ?? tenantId;
    if (tid && (next === "install" || next === "menu" || next === "done")) p.set("tenant", tid);
    setParams(p);
  };

  // ─── guards — URL is the source of truth, so refreshes land sanely ──
  if (meQ.isLoading) {
    return (
      <Shell step={step}>
        <div className="flex flex-col gap-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-10 w-48" />
        </div>
      </Shell>
    );
  }
  const me = meQ.data ?? null;
  if (step !== "signin" && !me) return <Navigate to="/onboard?step=signin" replace />;
  if (step === "slug" && !business) return <Navigate to="/onboard?step=claim" replace />;
  if ((step === "install" || step === "menu" || step === "done") && !tenantId)
    return <Navigate to="/onboard?step=claim" replace />;

  return (
    <Shell step={step}>
      {step === "signin" && <SignInStep me={me} onAddAnother={() => go("claim")} />}
      {step === "claim" && (
        <ClaimStep
          onClaimed={(b) => {
            setBusiness(b);
            go("slug");
          }}
        />
      )}
      {step === "slug" && business && (
        <SlugStep
          business={business}
          onCreated={(tid, key) => {
            setApiKey(key);
            go("install", tid);
          }}
        />
      )}
      {step === "install" && tenantId && (
        <InstallStep tenantId={tenantId} apiKey={apiKey} onInstalled={() => go("menu")} />
      )}
      {step === "menu" && tenantId && (
        <MenuStep tenantId={tenantId} onDone={() => go("done")} />
      )}
      {step === "done" && tenantId && <DoneStep tenantId={tenantId} />}
    </Shell>
  );
}

function Shell({ step, children }: { step: StepKey; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-paper-100">
      <div className="mx-auto flex w-full max-w-xl flex-col gap-8 px-6 py-16">
        <StepIndicator current={step} />
        {children}
      </div>
    </div>
  );
}
