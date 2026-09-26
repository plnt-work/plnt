/**
 * Console — operator dashboard, FE-Console-v2 shell.
 *
 * Two modes (slice 6):
 *   - merchant: a signed-in onboard session owning tenants clamps the
 *     console to those tenants and hides the picker/provisioning chrome.
 *   - internal: ?internal=true, or an admin token baked into the build —
 *     today's multi-tenant picker behavior, unchanged.
 * Signed out with neither → a plain panel linking to /onboard.
 */
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import ConsoleShell from "../features/console/ConsoleShell";
import ProvisionDialog from "../components/console/ProvisionDialog";
import { deleteTenant, listTenants, type TenantSummary } from "../api/admin";
import { useOnboardMe } from "../lib/queries/onboard";

const ADMIN_TOKEN_SET = Boolean(import.meta.env.VITE_ADMIN_TOKEN);

export default function Console() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();

  const internal = params.get("internal") === "true" || ADMIN_TOKEN_SET;
  const meQ = useOnboardMe();
  const merchantTenants = useMemo(
    () => (!internal ? (meQ.data?.tenants ?? []) : []),
    [internal, meQ.data],
  );
  const merchantMode = merchantTenants.length > 0;

  // Cross-tenant listing is admin-bearer-only — merchants use /me instead.
  const tenantsQ = useQuery({
    queryKey: ["tenants"],
    queryFn: listTenants,
    staleTime: 30_000,
    refetchInterval: 60_000,
    enabled: internal,
  });

  const tenants: TenantSummary[] = useMemo(() => {
    if (!merchantMode) return tenantsQ.data ?? [];
    return merchantTenants.map((t) => ({
      tenant_id: t.tenant_id,
      display_name: t.business_name,
      created_at: 0,
      home: "",
    }));
  }, [merchantMode, merchantTenants, tenantsQ.data]);

  // The user's intended selection. URL is the source of truth; this state
  // only holds an override when no URL param has been set yet.
  const [override, setOverride] = useState<string | null>(null);

  // Effective selection: URL → override → first tenant, clamped to the
  // visible tenant list (which in merchant mode is only owned tenants).
  const selected: string | null = useMemo(() => {
    const raw = override ?? params.get("tenant");
    if (raw && tenants.some((t) => t.tenant_id === raw)) return raw;
    return tenants[0]?.tenant_id ?? null;
  }, [override, params, tenants]);

  const onSelectTenant = (id: string) => {
    setOverride(id);
    params.set("tenant", id);
    setParams(params, { replace: true });
  };

  const [provisioning, setProvisioning] = useState(false);

  const deleteMut = useMutation({
    mutationFn: deleteTenant,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenants"] });
    },
  });

  if (!internal && !merchantMode) {
    if (meQ.isLoading) return <ConsolePanel>Loading…</ConsolePanel>;
    return (
      <ConsolePanel>
        <p>This console is scoped to your business.</p>
        <Link
          to="/onboard"
          className="text-iri-blue underline underline-offset-2 hover:text-iri-blue/80"
        >
          Sign in and claim your business →
        </Link>
      </ConsolePanel>
    );
  }

  return (
    <>
      <ConsoleShell
        tenants={tenants}
        selected={selected}
        onSelectTenant={onSelectTenant}
        onProvision={() => setProvisioning(true)}
        onDeleteTenant={(id) => deleteMut.mutate(id)}
        merchantMode={merchantMode}
      />

      {provisioning && (
        <ProvisionDialog
          onCancel={() => setProvisioning(false)}
          onCreated={(t) => {
            setProvisioning(false);
            qc.invalidateQueries({ queryKey: ["tenants"] });
            onSelectTenant(t.tenant_id);
          }}
        />
      )}
    </>
  );
}

function ConsolePanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="theme-console grid h-full place-items-center bg-coal-700 text-coal-100">
      <div className="flex flex-col items-center gap-2 text-[13px]">{children}</div>
    </div>
  );
}
