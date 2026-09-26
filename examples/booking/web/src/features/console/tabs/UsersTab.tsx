/**
 * Users — end-user activity.
 *
 * One row per user_id: first/last seen, session count, booking count.
 * Row click → Drawer with the user's bookings and sessions, plus
 * a "jump to conversations filtered to them" shortcut.
 */
import { useMemo, useState } from "react";

import { DataTable } from "@/components/ui/DataTable";
import {
  Drawer, DrawerBody, DrawerContent, DrawerFooter, DrawerHeader,
} from "@/components/ui/Drawer";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Users } from "lucide-react";

import { useUsers, useUser } from "@/lib/queries/admin";
import { BookingStatusBadge, SessionStatusBadge } from "../badges";
import PageHeader from "../PageHeader";
import {
  absoluteFromSeconds, businessNameOf, relativeFromSeconds, slotFromIso,
} from "@/lib/format";

import type { ColumnDef } from "@tanstack/react-table";
import type { UserSummary } from "@/lib/api/admin-v2";

interface Props {
  tenantId: string;
  onJumpToConversations: () => void;
}

export default function UsersTab({ tenantId, onJumpToConversations }: Props) {
  const { data, isLoading } = useUsers(tenantId);
  const [openUserId, setOpenUserId] = useState<string | null>(null);

  const columns: ColumnDef<UserSummary>[] = useMemo(
    () => [
      {
        accessorKey: "user_id",
        header: "User",
        cell: (info) => <span className="font-mono text-coal-50">{String(info.getValue())}</span>,
      },
      {
        accessorKey: "sessions",
        header: "Sessions",
        cell: (info) => <span className="font-mono text-coal-50">{Number(info.getValue())}</span>,
        size: 90,
      },
      {
        accessorKey: "bookings",
        header: "Bookings",
        cell: (info) => <span className="font-mono text-coal-50">{Number(info.getValue())}</span>,
        size: 90,
      },
      {
        accessorKey: "first_seen",
        header: "First seen",
        cell: (info) => <span className="text-coal-200">{relativeFromSeconds(Number(info.getValue()))}</span>,
      },
      {
        accessorKey: "last_seen",
        header: "Last seen",
        cell: (info) => <span className="text-coal-200">{relativeFromSeconds(Number(info.getValue()))}</span>,
      },
    ],
    [],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Users"
        description="One row per stable user_id (web tab + later WhatsApp identity). Click to see their bookings + sessions."
      />

      <DataTable
        data={data?.users ?? []}
        columns={columns}
        loading={isLoading}
        getRowId={(u) => u.user_id}
        activeRowId={openUserId}
        onRowClick={(u) => setOpenUserId(u.user_id)}
        emptyState={
          <EmptyState
            icon={Users}
            title="No users yet"
            description="The first WebSocket connection registers a user_id here."
          />
        }
      />

      <Drawer open={!!openUserId} onOpenChange={(o) => !o && setOpenUserId(null)}>
        {openUserId && (
          <UserDrawer
            tenantId={tenantId}
            userId={openUserId}
            onJumpToConversations={() => { setOpenUserId(null); onJumpToConversations(); }}
          />
        )}
      </Drawer>
    </div>
  );
}

function UserDrawer({
  tenantId,
  userId,
  onJumpToConversations,
}: {
  tenantId: string;
  userId: string;
  onJumpToConversations: () => void;
}) {
  const { data, isLoading } = useUser(tenantId, userId);

  return (
    <DrawerContent size="lg">
      <DrawerHeader
        title={userId}
        subtitle={isLoading
          ? "Loading…"
          : `${data?.bookings.length ?? 0} bookings · ${data?.sessions.length ?? 0} sessions`}
        badge={<Badge tone="info">end-user</Badge>}
      />
      <DrawerBody className="space-y-5">
        <section>
          <h3 className="text-[12px] uppercase tracking-wide text-coal-200 mb-2">Bookings</h3>
          {!isLoading && data && data.bookings.length === 0 ? (
            <div className="text-[12px] text-coal-200">No bookings yet.</div>
          ) : (
            <ul className="space-y-2">
              {(data?.bookings ?? []).map((b) => (
                <li key={b.booking_id} className="rounded-md border border-coal-500 bg-coal-700/60 p-3 text-[12.5px]">
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <span className="font-mono text-coal-50">{b.booking_id}</span>
                    <BookingStatusBadge status={b.status} />
                  </div>
                  <div className="text-coal-50">{businessNameOf(b.business_id)}</div>
                  <div className="text-coal-200">{slotFromIso(b.slot)} · {relativeFromSeconds(b.created_at)}</div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h3 className="text-[12px] uppercase tracking-wide text-coal-200 mb-2">Sessions</h3>
          {!isLoading && data && data.sessions.length === 0 ? (
            <div className="text-[12px] text-coal-200">No sessions yet.</div>
          ) : (
            <ul className="space-y-2">
              {(data?.sessions ?? []).map((s) => (
                <li key={s.session_id} className="rounded-md border border-coal-500 bg-coal-700/60 p-3 text-[12.5px]">
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <span className="font-mono text-coal-50">{s.session_id}</span>
                    <SessionStatusBadge status={s.status} />
                  </div>
                  <div className="text-coal-50">{businessNameOf(s.business_id)}</div>
                  <div className="text-coal-200">
                    {s.message_count} msgs · last {relativeFromSeconds(s.last_message_at)} · started {absoluteFromSeconds(s.started_at)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </DrawerBody>
      <DrawerFooter>
        <Button variant="outline" size="sm" onClick={onJumpToConversations}>
          View all conversations →
        </Button>
      </DrawerFooter>
    </DrawerContent>
  );
}
