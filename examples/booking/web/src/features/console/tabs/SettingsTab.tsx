/**
 * Settings — tenant ops & metadata.
 *
 * - Tenant id / display name / home path (read-only)
 * - API key reveal (placeholder — backend doesn't expose post-creation)
 * - Danger zone: Delete tenant (re-uses the AlertDialog from the old Console)
 *
 * Most fields here are placeholders for backend work; the layout is the
 * shape so MA-stream can fill them in without UI churn.
 */
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/AlertDialog";
import { absoluteFromSeconds } from "@/lib/format";
import PageHeader from "../PageHeader";

import type { TenantSummary } from "@/api/admin";

interface Props {
  tenantId: string;
  tenant: TenantSummary | null;
  onDelete: () => void;
}

export default function SettingsTab({ tenantId, tenant, onDelete }: Props) {
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <div className="space-y-6 max-w-3xl">
      <PageHeader title="Settings" description="Tenant ops and metadata." />

      <Card title="Tenant">
        <Row label="Tenant id" value={<span className="font-mono">{tenantId}</span>} />
        <Row label="Display name" value={tenant?.display_name ?? "—"} />
        <Row label="Home" value={<span className="font-mono text-[12px] break-all">{tenant?.home ?? "—"}</span>} />
        <Row label="Created" value={tenant ? absoluteFromSeconds(tenant.created_at) : "—"} />
      </Card>

      <Card title="API key">
        <p className="text-[12.5px] text-coal-200">
          The tenant's API key is only returned at provisioning time. Rotate by re-provisioning;
          the secret is not stored client-side.
        </p>
        <div className="flex items-center gap-2">
          <code className="font-mono text-[12px] px-2 py-1 rounded bg-coal-700/60 border border-coal-500 text-coal-200">
            ••••••••
          </code>
          <Badge tone="info">read-only</Badge>
        </div>
      </Card>

      <Card title="Retention" subtitle="Soon: per-resource TTLs (memori turns, audit jsonl, booking ledger).">
        <Row label="Memori turns" value={<Badge tone="neutral">90 days (default)</Badge>} />
        <Row label="Audit log" value={<Badge tone="neutral">indefinite (default)</Badge>} />
        <Row label="Booking ledger" value={<Badge tone="neutral">indefinite (default)</Badge>} />
      </Card>

      <Card title="Danger zone" tone="danger">
        <p className="text-[12.5px] text-coal-200">
          Permanently wipes all conversations, memory, bookings, and audit data for this tenant.
        </p>
        <div>
          <Button variant="danger" size="sm" onClick={() => setConfirmOpen(true)}>
            Delete tenant
          </Button>
        </div>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete tenant '{tenantId}'?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently wipes all conversations, memory, bookings, and audit
              data for this tenant. The action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => { e.preventDefault(); setConfirmOpen(false); onDelete(); }}
            >
              Delete tenant
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function Card({
  title,
  subtitle,
  tone,
  children,
}: {
  title: string;
  subtitle?: string;
  tone?: "danger";
  children: React.ReactNode;
}) {
  return (
    <section
      className={[
        "rounded-lg border bg-coal-600/60 p-4 space-y-3",
        tone === "danger" ? "border-rust/40" : "border-coal-500",
      ].join(" ")}
    >
      <div>
        <h2 className="text-[13px] font-semibold text-coal-50">{title}</h2>
        {subtitle && <p className="text-[12px] text-coal-200 mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-3 text-[12.5px] items-center">
      <span className="text-coal-200 uppercase tracking-wide text-[10.5px]">{label}</span>
      <span className="text-coal-50">{value}</span>
    </div>
  );
}
