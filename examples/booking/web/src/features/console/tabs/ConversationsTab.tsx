/**
 * Conversations — sessions + transcripts.
 *
 * Left: searchable session list (DataTable, dense, click-to-open).
 * Right (Drawer xl): full transcript with role-tinted bubbles and
 * action-card preview where present.
 *
 * URL param ?session=<sid> opens the drawer on mount so Overview's
 * "see this session" link works.
 */
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { DataTable } from "@/components/ui/DataTable";
import {
  Drawer, DrawerBody, DrawerContent, DrawerHeader,
} from "@/components/ui/Drawer";
import { EmptyState } from "@/components/ui/EmptyState";
import { Badge } from "@/components/ui/Badge";
import { Combobox, type ComboboxItem } from "@/components/ui/Combobox";
import { MessageSquareText } from "lucide-react";

import { useSessions, useTranscript, useUsers } from "@/lib/queries/admin";
import { SessionStatusBadge } from "../badges";
import PageHeader from "../PageHeader";
import {
  absoluteFromSeconds, businessNameOf, relativeFromSeconds, truncate,
} from "@/lib/format";

import type { ColumnDef } from "@tanstack/react-table";
import type { SessionRow, TranscriptEntry } from "@/lib/api/admin-v2";

interface Props {
  tenantId: string;
}

export default function ConversationsTab({ tenantId }: Props) {
  const [userFilter, setUserFilter] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  // URL is the source of truth for "which session drawer is open",
  // so Overview's ?session=<sid> deep-link works and back-button closes
  // the drawer naturally.
  const openSessionId = params.get("session");
  const setOpenSessionId = (sid: string | null) => {
    if (sid) params.set("session", sid); else params.delete("session");
    setParams(params, { replace: true });
  };

  const { data, isLoading } = useSessions(tenantId, {
    user_id: userFilter ?? undefined,
    limit: 200,
  });

  const usersQ = useUsers(tenantId);
  const userItems: ComboboxItem[] = useMemo(
    () => (usersQ.data?.users ?? []).map((u) => ({
      value: u.user_id,
      label: u.user_id,
      trailing: `${u.sessions} sessions`,
    })),
    [usersQ.data],
  );

  const columns: ColumnDef<SessionRow>[] = useMemo(
    () => [
      {
        accessorKey: "session_id",
        header: "Session",
        cell: (info) => <span className="font-mono text-coal-50">{String(info.getValue())}</span>,
        size: 130,
      },
      {
        accessorKey: "user_id",
        header: "User",
        cell: (info) => <span>{String(info.getValue())}</span>,
        size: 130,
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
    ],
    [],
  );

  const closeDrawer = () => setOpenSessionId(null);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Conversations"
        description="Every WebSocket session with full trace — including the hidden classify/resolve/availability steps."
      />

      <div className="flex flex-wrap items-center gap-3">
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
          {isLoading ? "loading…" : `${data?.sessions.length ?? 0} of ${data?.total ?? 0}`}
        </div>
      </div>

      <DataTable
        data={data?.sessions ?? []}
        columns={columns}
        loading={isLoading}
        getRowId={(r) => r.session_id}
        activeRowId={openSessionId}
        onRowClick={(r) => setOpenSessionId(r.session_id)}
        emptyState={
          <EmptyState
            icon={MessageSquareText}
            title="No sessions"
            description="Sessions appear here as soon as a user pings the WebSocket."
          />
        }
      />

      <Drawer open={!!openSessionId} onOpenChange={(open) => !open && closeDrawer()}>
        {openSessionId && (
          <TranscriptDrawer tenantId={tenantId} sessionId={openSessionId} />
        )}
      </Drawer>
    </div>
  );
}

function TranscriptDrawer({
  tenantId,
  sessionId,
}: {
  tenantId: string;
  sessionId: string;
}) {
  const { data, isLoading } = useTranscript(tenantId, sessionId);
  const entries = data?.transcript ?? [];
  const first = entries[0];

  return (
    <DrawerContent size="xl">
      <DrawerHeader
        title={sessionId}
        subtitle={first ? `${entries.length} events · started ${absoluteFromSeconds(first.at)}` : "Loading transcript…"}
      />
      <DrawerBody>
        {isLoading ? (
          <div className="space-y-2">
            <div className="h-3 w-32 rounded bg-coal-500 animate-pulse-soft" />
            <div className="h-3 w-3/4 rounded bg-coal-500 animate-pulse-soft" />
            <div className="h-3 w-1/2 rounded bg-coal-500 animate-pulse-soft" />
          </div>
        ) : entries.length === 0 ? (
          <EmptyState
            icon={MessageSquareText}
            title="No transcript"
            description="This session has no recorded turns yet."
          />
        ) : (
          <ol className="space-y-3 text-[12.5px]">
            {entries.map((e) => (
              <TranscriptRow key={e.seq} entry={e} />
            ))}
          </ol>
        )}
      </DrawerBody>
    </DrawerContent>
  );
}

function TranscriptRow({ entry }: { entry: TranscriptEntry }) {
  const tone =
    entry.role === "user" ? "neutral"
    : entry.role === "say" ? "info"
    : entry.role === "system" ? "warn"
    : "coal";

  let body: string;
  if (entry.role === "user") {
    body = String((entry.content as { text?: unknown }).text ?? "");
  } else if (entry.role === "say") {
    body = String((entry.content as { say?: unknown }).say ?? "");
  } else if (entry.role === "system") {
    body = String((entry.content as { note?: unknown }).note ?? "");
  } else {
    body = truncate(JSON.stringify(entry.content), 240);
  }

  const action = (entry.content as { action?: Record<string, unknown> | null }).action ?? entry.action ?? null;

  return (
    <li className="rounded-md border border-coal-500 bg-coal-700/60 p-3">
      <div className="flex items-center justify-between gap-3 mb-1">
        <div className="flex items-center gap-2">
          <Badge tone={tone}>{entry.role}</Badge>
          <span className="font-mono text-[10.5px] text-coal-200">seq {entry.seq}</span>
        </div>
        <span className="text-[11px] text-coal-200">{absoluteFromSeconds(entry.at)}</span>
      </div>
      <div className="text-coal-50 whitespace-pre-wrap break-words">{body}</div>
      {action && (
        <div className="mt-2 rounded border border-iri-blue/30 bg-iri-blue/10 p-2 text-[11px] text-coal-100">
          <div className="text-[10.5px] uppercase tracking-wide text-iri-blue font-medium mb-0.5">
            action · {String((action as { kind?: unknown }).kind ?? "?")}
          </div>
          <pre className="font-mono whitespace-pre-wrap break-all">{JSON.stringify(action, null, 2)}</pre>
        </div>
      )}
    </li>
  );
}
