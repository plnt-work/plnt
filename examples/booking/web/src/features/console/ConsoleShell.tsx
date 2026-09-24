/**
 * ConsoleShell — Vertex AI-shaped admin chrome.
 *
 *   ┌────────────────────────────────────────────────────────────┐
 *   │ Atlas  ▾ tenant            console / overview        → /atlas │  topbar
 *   ├────────┬─────────────────────────────────────────────────┤
 *   │ Nav    │ Tabbed content                                  │
 *   │ rail   │                                                 │
 *   │ ─ ovv  │   (each tab is a feature module)                │
 *   │ ─ rsv  │                                                 │
 *   │ ─ cnv  │                                                 │
 *   │ ─ usr  │                                                 │
 *   │ ─ agt  │                                                 │
 *   │ ─ set  │                                                 │
 *   └────────┴─────────────────────────────────────────────────┘
 *
 * Tabs are URL-scoped via ?tab=… so reload + share links work.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  BookOpenCheck,
  Bot,
  Cog,
  LayoutGrid,
  MessageSquareText,
  TicketCheck,
  Users,
} from "lucide-react";

import { cn } from "@/lib/cn";
import { Combobox, type ComboboxItem } from "@/components/ui/Combobox";

import NotificationsBell from "./NotificationsBell";
import OverviewTab from "./tabs/OverviewTab";
import ReservationsTab from "./tabs/ReservationsTab";
import ConversationsTab from "./tabs/ConversationsTab";
import UsersTab from "./tabs/UsersTab";
import AgentsTab from "./tabs/AgentsTab";
import SettingsTab from "./tabs/SettingsTab";

import type { TenantSummary } from "@/api/admin";

export type ConsoleTab =
  | "overview"
  | "reservations"
  | "conversations"
  | "users"
  | "agents"
  | "settings";

interface NavItem {
  id: ConsoleTab;
  label: string;
  Icon: typeof LayoutGrid;
  hint: string;
}

const NAV: NavItem[] = [
  { id: "overview", label: "Overview", Icon: LayoutGrid, hint: "Tenant health at a glance" },
  { id: "reservations", label: "Reservations", Icon: TicketCheck, hint: "Bookings ledger" },
  { id: "conversations", label: "Conversations", Icon: MessageSquareText, hint: "Sessions + transcripts" },
  { id: "users", label: "Users", Icon: Users, hint: "End-user activity" },
  { id: "agents", label: "Agents", Icon: Bot, hint: "Installed micro-agents + marketplace" },
  { id: "settings", label: "Settings", Icon: Cog, hint: "API keys, retention, tenant ops" },
];

interface Props {
  tenants: TenantSummary[];
  selected: string | null;
  onSelectTenant: (id: string) => void;
  onProvision: () => void;
  onDeleteTenant: (id: string) => void;
  /** Merchant-scoped console: no tenant picker, no provisioning chrome. */
  merchantMode?: boolean;
}

export default function ConsoleShell({
  tenants, selected, onSelectTenant, onProvision, onDeleteTenant,
  merchantMode = false,
}: Props) {
  const [params, setParams] = useSearchParams();
  const tabFromUrl = params.get("tab") as ConsoleTab | null;
  const [tab, setTab] = useState<ConsoleTab>(
    tabFromUrl && NAV.some((n) => n.id === tabFromUrl) ? tabFromUrl : "overview",
  );

  // Mirror local tab state back into URL.
  useEffect(() => {
    if (params.get("tab") !== tab) {
      params.set("tab", tab);
      setParams(params, { replace: true });
    }
  }, [tab, params, setParams]);

  const tenantItems: ComboboxItem[] = useMemo(
    () => tenants.map((t) => ({
      value: t.tenant_id,
      label: (
        <span className="flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-iri-blue" />
          <span className="truncate">{t.display_name || t.tenant_id}</span>
        </span>
      ),
      keywords: [t.display_name, t.tenant_id],
      trailing: t.tenant_id,
    })),
    [tenants],
  );

  const active = NAV.find((n) => n.id === tab) ?? NAV[0]!;

  return (
    <div className="theme-console h-full grid grid-rows-[56px_1fr] bg-coal-700 text-coal-50">
      {/* ─── Topbar ─── */}
      <header className="grid grid-cols-[auto_auto_1fr_auto] items-center gap-3 px-4 border-b border-coal-500 bg-coal-700/95 backdrop-blur-sm">
        <Link to="/atlas" className="inline-flex items-center gap-2 text-coal-50 hover:text-iri-blue transition-colors">
          <span className="size-5 rounded-md bg-iri-blue/90 grid place-items-center text-[10px] font-semibold text-paper-100">
            A
          </span>
          <span className="text-[14px] font-semibold tracking-tight">Atlas</span>
          <span className="text-coal-200">Console</span>
        </Link>

        {merchantMode ? (
          <span className="inline-flex items-center gap-2 text-[13px] text-coal-50">
            <span className="size-1.5 rounded-full bg-iri-blue" />
            <span className="truncate">
              {tenants.find((t) => t.tenant_id === selected)?.display_name ?? selected}
            </span>
          </span>
        ) : (
          <Combobox
            value={selected}
            onChange={(v) => v && onSelectTenant(v)}
            items={tenantItems}
            placeholder="Select tenant…"
            searchPlaceholder="Search tenants"
            emptyText="No tenants. Provision one →"
            ariaLabel="Tenant"
          />
        )}

        <div className="text-[12.5px] text-coal-200 flex items-center gap-2 min-w-0">
          <span>console</span>
          <span>/</span>
          <span className="text-coal-50 font-medium truncate">{selected ?? "—"}</span>
          <span>/</span>
          <span className="text-coal-50">{active.label}</span>
        </div>

        <div className="flex items-center gap-3 text-[12.5px]">
          <NotificationsBell tenantId={selected} />
          {!merchantMode && (
            <button
              type="button"
              onClick={onProvision}
              className="h-8 px-3 rounded-md bg-iri-blue text-white hover:bg-iri-blue/90 transition-colors text-[12.5px] font-medium outline-none focus-visible:ring-2 focus-visible:ring-iri-blue/40"
            >
              + Tenant
            </button>
          )}
          <Link to="/atlas" className="text-coal-200 hover:text-coal-50 transition-colors">
            map surface →
          </Link>
        </div>
      </header>

      {/* ─── Body: nav rail + content ─── */}
      <div className="grid grid-cols-[224px_1fr] min-h-0">
        <nav className="border-r border-coal-500 bg-coal-700/60 py-3 overflow-y-auto">
          <ul className="space-y-0.5 px-2">
            {NAV.map((n) => {
              const Icon = n.Icon;
              const isActive = n.id === tab;
              return (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => setTab(n.id)}
                    aria-current={isActive ? "page" : undefined}
                    className={cn(
                      "w-full inline-flex items-center gap-2.5 px-2.5 h-9 rounded-md text-[13px] transition-colors text-left outline-none",
                      "focus-visible:ring-2 focus-visible:ring-iri-blue/40",
                      isActive
                        ? "bg-iri-blue/15 text-iri-blue font-medium"
                        : "text-coal-100 hover:bg-coal-500/40 hover:text-coal-50",
                    )}
                    title={n.hint}
                  >
                    <Icon className={cn("size-4 shrink-0", isActive ? "text-iri-blue" : "text-coal-200")} />
                    <span>{n.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>

          <div className="mt-6 px-3 text-[10.5px] text-coal-200 uppercase tracking-wide">
            Quick links
          </div>
          <ul className="mt-1 space-y-0.5 px-2">
            <li>
              <Link
                to="/atlas"
                className="w-full inline-flex items-center gap-2.5 px-2.5 h-8 rounded-md text-[12.5px] text-coal-200 hover:text-coal-50 hover:bg-coal-500/40 transition-colors"
              >
                <BookOpenCheck className="size-3.5" />
                Consumer surface
              </Link>
            </li>
          </ul>
        </nav>

        <main className="min-w-0 min-h-0 overflow-y-auto p-6">
          {!selected ? (
            <div className="grid h-full place-items-center text-coal-200 text-[13px]">
              Pick a tenant on the top bar, or provision a new one.
            </div>
          ) : tab === "overview" ? (
            <OverviewTab tenantId={selected} onNavigate={setTab} />
          ) : tab === "reservations" ? (
            <ReservationsTab tenantId={selected} />
          ) : tab === "conversations" ? (
            <ConversationsTab tenantId={selected} />
          ) : tab === "users" ? (
            <UsersTab tenantId={selected} onJumpToConversations={() => setTab("conversations")} />
          ) : tab === "agents" ? (
            <AgentsTab tenantId={selected} />
          ) : (
            <SettingsTab
              tenantId={selected}
              tenant={tenants.find((t) => t.tenant_id === selected) ?? null}
              onDelete={() => onDeleteTenant(selected)}
            />
          )}
        </main>
      </div>
    </div>
  );
}
