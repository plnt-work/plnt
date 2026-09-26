/**
 * Reservations — bookings ledger.
 *
 * Top: status filter (pill row) + user filter (Combobox) + count.
 * Body: DataTable on Bookings; row click → Drawer with full row +
 * "see conversation" link to Conversations tab.
 */
import { useMemo, useState } from "react";

import { DataTable } from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Combobox, type ComboboxItem } from "@/components/ui/Combobox";
import {
  Drawer, DrawerBody, DrawerContent, DrawerFooter, DrawerHeader,
} from "@/components/ui/Drawer";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { TicketCheck } from "lucide-react";

import { useBookings, useUsers } from "@/lib/queries/admin";
import { BookingStatusBadge } from "../badges";
import PageHeader from "../PageHeader";
import {
  absoluteFromSeconds, businessNameOf, relativeFromSeconds, slotFromIso,
} from "@/lib/format";

import type { ColumnDef } from "@tanstack/react-table";
import type { Booking, BookingStatus } from "@/lib/api/admin-v2";
import { cn } from "@/lib/cn";

interface Props {
  tenantId: string;
}

const STATUSES: Array<{ id: BookingStatus | "all"; label: string }> = [
  { id: "all", label: "All" },
  { id: "confirmed", label: "Confirmed" },
  { id: "pending", label: "Pending" },
  { id: "failed", label: "Failed" },
  { id: "cancelled", label: "Cancelled" },
];

export default function ReservationsTab({ tenantId }: Props) {
  const [statusFilter, setStatusFilter] = useState<BookingStatus | "all">("all");
  const [userFilter, setUserFilter] = useState<string | null>(null);
  const [selected, setSelected] = useState<Booking | null>(null);

  const { data, isLoading } = useBookings(tenantId, {
    status: statusFilter === "all" ? undefined : statusFilter,
    user_id: userFilter ?? undefined,
    limit: 200,
  });

  const usersQ = useUsers(tenantId);
  const userItems: ComboboxItem[] = useMemo(
    () => (usersQ.data?.users ?? []).map((u) => ({
      value: u.user_id,
      label: u.user_id,
      keywords: [u.user_id],
      trailing: `${u.bookings} bookings`,
    })),
    [usersQ.data],
  );

  const columns: ColumnDef<Booking>[] = useMemo(
    () => [
      {
        accessorKey: "booking_id",
        header: "Booking",
        cell: (info) => <span className="font-mono text-coal-50">{String(info.getValue())}</span>,
        size: 110,
      },
      {
        accessorKey: "user_id",
        header: "User",
        cell: (info) => <span>{String(info.getValue())}</span>,
        size: 140,
      },
      {
        accessorKey: "business_id",
        header: "Business",
        cell: (info) => (
          <div className="flex flex-col">
            <span className="text-coal-50 truncate">{businessNameOf(info.getValue() as string)}</span>
            <span className="font-mono text-[10.5px] text-coal-200">{String(info.getValue())}</span>
          </div>
        ),
      },
      {
        accessorKey: "slot",
        header: "Slot",
        cell: (info) => <span className="text-coal-100">{slotFromIso(info.getValue() as string)}</span>,
        size: 200,
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: (info) => <BookingStatusBadge status={info.getValue() as BookingStatus} />,
        size: 110,
      },
      {
        accessorKey: "created_at",
        header: "Created",
        cell: (info) => <span className="text-coal-200">{relativeFromSeconds(Number(info.getValue()))}</span>,
        size: 140,
      },
    ],
    [],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Reservations"
        description="Bookings ledger across every micro-agent for this tenant."
      />

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1">
          {STATUSES.map((s) => {
            const active = statusFilter === s.id;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => setStatusFilter(s.id)}
                className={cn(
                  "h-8 px-3 rounded-full text-[12.5px] font-medium border transition-colors outline-none",
                  "focus-visible:ring-2 focus-visible:ring-iri-blue/40",
                  active
                    ? "bg-iri-blue/20 border-iri-blue/60 text-iri-blue"
                    : "bg-transparent border-coal-500 text-coal-200 hover:text-coal-50",
                )}
              >
                {s.label}
              </button>
            );
          })}
        </div>

        <Combobox
          value={userFilter}
          onChange={setUserFilter}
          items={userItems}
          placeholder="All users"
          searchPlaceholder="Search users"
          clearLabel="All users"
          ariaLabel="Filter by user"
        />

        <div className="ml-auto text-[12px] text-coal-200">
          {isLoading ? "loading…" : `${data?.bookings.length ?? 0} of ${data?.total ?? 0}`}
        </div>
      </div>

      <DataTable
        data={data?.bookings ?? []}
        columns={columns}
        loading={isLoading}
        getRowId={(b) => b.booking_id}
        activeRowId={selected?.booking_id ?? null}
        onRowClick={(b) => setSelected(b)}
        emptyState={
          <EmptyState
            icon={TicketCheck}
            title="No bookings yet"
            description="When users confirm a slot, it lands here."
          />
        }
      />

      <Drawer open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        {selected && (
          <DrawerContent size="md">
            <DrawerHeader
              title={selected.booking_id}
              subtitle={businessNameOf(selected.business_id)}
              badge={<BookingStatusBadge status={selected.status} />}
            />
            <DrawerBody>
              <dl className="grid grid-cols-[110px_1fr] gap-y-2.5 text-[12.5px]">
                <Row label="User" value={selected.user_id} />
                <Row label="Business id" value={<span className="font-mono">{selected.business_id}</span>} />
                <Row label="Slot" value={slotFromIso(selected.slot)} />
                <Row label="Slot (raw)" value={<span className="font-mono text-[11px]">{selected.slot}</span>} />
                <Row label="Idempotency" value={<span className="font-mono text-[11px]">{selected.idempotency_key}</span>} />
                <Row label="Created" value={`${absoluteFromSeconds(selected.created_at)} · ${relativeFromSeconds(selected.created_at)}`} />
              </dl>

              <div className="mt-6 rounded-md border border-coal-500 bg-coal-700/60 p-3 text-[12px] text-coal-200">
                <div className="text-coal-50 font-medium mb-1.5">Raw JSON</div>
                <pre className="font-mono text-[11px] whitespace-pre-wrap break-all">
                  {JSON.stringify(selected, null, 2)}
                </pre>
              </div>
            </DrawerBody>
            <DrawerFooter>
              <Badge tone="info">read-only · cancel via the user's chat session</Badge>
              <Button variant="outline" size="sm" onClick={() => setSelected(null)}>
                Close
              </Button>
            </DrawerFooter>
          </DrawerContent>
        )}
      </Drawer>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="text-coal-200 uppercase tracking-wide text-[10.5px] pt-0.5">{label}</dt>
      <dd className="text-coal-50">{value}</dd>
    </>
  );
}
