/**
 * Overview — tenant health at a glance.
 *
 *   ┌──────────────────────────────────────────────────────────┐
 *   │ Conversations  Bookings  Active users  Avg messages      │  KPI strip
 *   ├──────────────────────────┬───────────────────────────────┤
 *   │ Bookings by status       │ Recent activity               │
 *   │ (mini bar)               │ (last 8 sessions)             │
 *   └──────────────────────────┴───────────────────────────────┘
 */
import { ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { KPITile } from "@/components/ui/KPITile";
import { DataTable } from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { useOverview } from "@/lib/queries/admin";
import { SessionStatusBadge } from "../badges";
import PageHeader from "../PageHeader";
import { businessNameOf, relativeFromSeconds } from "@/lib/format";

import type { ColumnDef } from "@tanstack/react-table";
import type { SessionRow } from "@/lib/api/admin-v2";
import type { ConsoleTab } from "../ConsoleShell";

interface Props {
  tenantId: string;
  onNavigate: (t: ConsoleTab) => void;
}

const RECENT_COLS: ColumnDef<SessionRow>[] = [
  {
    accessorKey: "session_id",
    header: "Session",
    cell: (info) => <span className="font-mono text-[12px] text-coal-100">{String(info.getValue())}</span>,
    size: 140,
  },
  {
    accessorKey: "user_id",
    header: "User",
    cell: (info) => <span className="text-coal-50">{String(info.getValue())}</span>,
    size: 140,
  },
  {
    accessorKey: "business_id",
    header: "Business",
    cell: (info) => <span className="text-coal-100">{businessNameOf(info.getValue() as string | null)}</span>,
  },
  {
    accessorKey: "message_count",
    header: "Msgs",
    cell: (info) => <span className="font-mono text-coal-50">{Number(info.getValue())}</span>,
    size: 70,
  },
  {
    accessorKey: "last_message_at",
    header: "Last activity",
    cell: (info) => <span className="text-coal-200">{relativeFromSeconds(Number(info.getValue()))}</span>,
    size: 160,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: (info) => <SessionStatusBadge status={info.getValue() as SessionRow["status"]} />,
    size: 90,
  },
];

export default function OverviewTab({ tenantId, onNavigate }: Props) {
  const { data, isLoading } = useOverview(tenantId);
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description={`Live activity for ${tenantId}. Refreshes every 10s.`}
      />

      <section className="grid grid-cols-4 gap-3">
        <KPITile
          label="Conversations · 24h"
          value={data?.conversations_24h ?? 0}
          hint="open + idle + closed today"
          loading={isLoading}
          onClick={() => onNavigate("conversations")}
        />
        <KPITile
          label="Bookings · 24h"
          value={data?.bookings_24h ?? 0}
          hint="all statuses"
          loading={isLoading}
          onClick={() => onNavigate("reservations")}
        />
        <KPITile
          label="Active users · 24h"
          value={data?.active_users_24h ?? 0}
          hint="distinct user_ids"
          loading={isLoading}
          onClick={() => onNavigate("users")}
        />
        <KPITile
          label="Avg msgs / session"
          value={data?.avg_messages ?? 0}
          hint="across active sessions"
          loading={isLoading}
        />
      </section>

      <section className="grid grid-cols-[1fr_1.5fr] gap-3">
        <div className="rounded-lg border border-coal-500 bg-coal-600/60 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[13px] font-semibold text-coal-50">Bookings by status</h3>
            <button
              type="button"
              onClick={() => onNavigate("reservations")}
              className="text-[11.5px] text-iri-blue hover:underline inline-flex items-center gap-0.5"
            >
              View all <ArrowRight className="size-3" />
            </button>
          </div>
          <BookingsBar data={data?.bookings_by_status} loading={isLoading} />
        </div>

        <div className="rounded-lg border border-coal-500 bg-coal-600/60 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[13px] font-semibold text-coal-50">Recent activity</h3>
            <button
              type="button"
              onClick={() => onNavigate("conversations")}
              className="text-[11.5px] text-iri-blue hover:underline inline-flex items-center gap-0.5"
            >
              View all <ArrowRight className="size-3" />
            </button>
          </div>
          <DataTable
            data={data?.recent_sessions ?? []}
            columns={RECENT_COLS}
            loading={isLoading}
            loadingRows={4}
            getRowId={(r) => r.session_id}
            onRowClick={(r) => {
              navigate(`?tab=conversations&session=${encodeURIComponent(r.session_id)}`, { replace: true });
              onNavigate("conversations");
            }}
          />
        </div>
      </section>
    </div>
  );
}

function BookingsBar({
  data,
  loading,
}: {
  data?: Record<string, number>;
  loading?: boolean;
}) {
  if (loading || !data) {
    return <div className="h-24 rounded bg-coal-500 animate-pulse-soft" />;
  }
  const STATUSES: Array<{ key: string; tone: "ok" | "warn" | "danger" | "neutral"; label: string }> = [
    { key: "confirmed", tone: "ok", label: "Confirmed" },
    { key: "pending", tone: "warn", label: "Pending" },
    { key: "failed", tone: "danger", label: "Failed" },
    { key: "cancelled", tone: "neutral", label: "Cancelled" },
  ];
  const max = Math.max(1, ...STATUSES.map((s) => data[s.key] ?? 0));
  return (
    <ul className="space-y-2">
      {STATUSES.map((s) => {
        const v = data[s.key] ?? 0;
        const pct = (v / max) * 100;
        const barColor =
          s.tone === "ok" ? "bg-sage"
          : s.tone === "warn" ? "bg-amber"
          : s.tone === "danger" ? "bg-rust"
          : "bg-coal-400";
        return (
          <li key={s.key} className="flex items-center gap-3">
            <div className="w-24 text-[12px] text-coal-200">{s.label}</div>
            <div className="flex-1 h-2 rounded-full bg-coal-500 overflow-hidden">
              <div className={`${barColor} h-full`} style={{ width: `${pct}%` }} />
            </div>
            <div className="w-10 text-right">
              <Badge tone={s.tone} size="sm">{v}</Badge>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
