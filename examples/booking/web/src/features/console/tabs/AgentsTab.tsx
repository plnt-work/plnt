/**
 * Agents — installed agents + marketplace.
 *
 * Two-column layout:
 *   Left: Installed agents (DataTable). Row toggle = enabled flag,
 *         "Uninstall" via Drawer.
 *   Right: Marketplace cards — filter by vertical. Installed agents
 *         show a "Installed" badge; uninstalled ones a "+ Install"
 *         button that calls the install mutation.
 *
 * "from where they can enable agents they want to put" — that's this tab.
 */
import { useMemo, useState } from "react";
import { Bot, Check, Loader2, Plus, Power, Trash2 } from "lucide-react";

import { DataTable } from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  Drawer, DrawerBody, DrawerContent, DrawerFooter, DrawerHeader,
} from "@/components/ui/Drawer";

import {
  useInstallAgent,
  useInstalledAgents,
  useMarketplace,
  usePatchAgent,
  useUninstallAgent,
} from "@/lib/queries/admin";
import PageHeader from "../PageHeader";
import { absoluteFromSeconds, relativeFromSeconds } from "@/lib/format";

import { VERTICALS } from "@/features/places/verticals";
import { cn } from "@/lib/cn";

import type { ColumnDef } from "@tanstack/react-table";
import type { InstalledAgent, MarketplaceAgent } from "@/lib/api/admin-v2";

interface Props {
  tenantId: string;
}

export default function AgentsTab({ tenantId }: Props) {
  const installedQ = useInstalledAgents(tenantId);
  const [verticalFilter, setVerticalFilter] = useState<string | null>(null);
  const marketQ = useMarketplace(verticalFilter ?? undefined);

  const install = useInstallAgent(tenantId);
  const patch = usePatchAgent(tenantId);
  const uninstall = useUninstallAgent(tenantId);

  const [drawerSlug, setDrawerSlug] = useState<string | null>(null);

  const installedBySlug: Map<string, InstalledAgent> = useMemo(
    () => new Map((installedQ.data?.agents ?? []).map((a) => [a.slug, a])),
    [installedQ.data],
  );

  const columns: ColumnDef<InstalledAgent>[] = useMemo(
    () => [
      {
        accessorKey: "slug",
        header: "Agent",
        cell: (info) => {
          const a = info.row.original;
          const market = marketQ.data?.agents.find((m) => m.slug === a.slug);
          return (
            <div className="flex items-center gap-2">
              <span className="size-6 rounded-md bg-iri-blue/20 text-iri-blue grid place-items-center">
                <Bot className="size-3.5" />
              </span>
              <div className="min-w-0">
                <div className="text-coal-50 font-medium leading-tight">
                  {market?.display_name ?? a.slug}
                </div>
                <div className="font-mono text-[10.5px] text-coal-200 leading-tight">{a.slug}</div>
              </div>
            </div>
          );
        },
      },
      {
        accessorKey: "enabled",
        header: "State",
        cell: (info) => {
          const a = info.row.original;
          return (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                patch.mutate({ slug: a.slug, body: { enabled: !a.enabled } });
              }}
              className={cn(
                "inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full text-[11px] font-medium border transition-colors outline-none",
                "focus-visible:ring-2 focus-visible:ring-iri-blue/40",
                a.enabled
                  ? "bg-sage/15 border-sage/30 text-sage hover:bg-sage/20"
                  : "bg-coal-500/40 border-coal-400 text-coal-200 hover:text-coal-50",
              )}
              title={a.enabled ? "Disable agent" : "Enable agent"}
            >
              <Power className="size-3" />
              {a.enabled ? "Enabled" : "Disabled"}
            </button>
          );
        },
        size: 130,
      },
      {
        accessorKey: "conversation_count",
        header: "Conversations",
        cell: (info) => <span className="font-mono text-coal-50">{Number(info.getValue())}</span>,
        size: 130,
      },
      {
        accessorKey: "last_used_at",
        header: "Last used",
        cell: (info) => {
          const v = info.getValue() as number | null;
          return <span className="text-coal-200">{v ? relativeFromSeconds(v) : "—"}</span>;
        },
        size: 140,
      },
      {
        accessorKey: "installed_at",
        header: "Installed",
        cell: (info) => <span className="text-coal-200">{absoluteFromSeconds(Number(info.getValue()))}</span>,
        size: 160,
      },
    ],
    [marketQ.data, patch],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Agents"
        description="Installed micro-agents on this tenant + marketplace catalog. Toggle, configure, or install."
      />

      <div className="grid grid-cols-[3fr_2fr] gap-5">
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[13px] font-semibold text-coal-50">Installed</h2>
            <span className="text-[11.5px] text-coal-200">
              {installedQ.isLoading ? "loading…" : `${installedQ.data?.agents.length ?? 0} installed`}
            </span>
          </div>
          <DataTable
            data={installedQ.data?.agents ?? []}
            columns={columns}
            loading={installedQ.isLoading}
            getRowId={(a) => a.slug}
            activeRowId={drawerSlug}
            onRowClick={(a) => setDrawerSlug(a.slug)}
            emptyState={
              <EmptyState
                icon={Bot}
                title="No agents installed"
                description="Browse the marketplace on the right to put one to work."
              />
            }
          />
        </section>

        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[13px] font-semibold text-coal-50">Marketplace</h2>
            <select
              value={verticalFilter ?? ""}
              onChange={(e) => setVerticalFilter(e.target.value || null)}
              className="h-8 px-2 rounded-md border border-coal-500 bg-coal-600/60 text-[12.5px] text-coal-50 outline-none focus-visible:ring-2 focus-visible:ring-iri-blue/40"
              aria-label="Filter by vertical"
            >
              <option value="">All verticals</option>
              {VERTICALS.map((v) => (
                <option key={v.vertical} value={v.vertical}>{v.label}</option>
              ))}
            </select>
          </div>
          <ul className="space-y-2">
            {marketQ.isLoading && (
              <li className="h-20 rounded bg-coal-500 animate-pulse-soft" />
            )}
            {!marketQ.isLoading && marketQ.data?.agents.length === 0 && (
              <EmptyState
                icon={Bot}
                title="Nothing in this vertical"
                description="Try a different vertical or 'All'."
              />
            )}
            {(marketQ.data?.agents ?? []).map((m) => (
              <MarketplaceCard
                key={m.slug}
                m={m}
                installed={installedBySlug.has(m.slug)}
                installing={install.isPending && install.variables === m.slug}
                onInstall={() => install.mutate(m.slug)}
              />
            ))}
          </ul>
        </section>
      </div>

      <Drawer open={!!drawerSlug} onOpenChange={(o) => !o && setDrawerSlug(null)}>
        {drawerSlug && (() => {
          const a = installedBySlug.get(drawerSlug);
          if (!a) return null;
          const market = marketQ.data?.agents.find((m) => m.slug === a.slug);
          return (
            <DrawerContent size="md">
              <DrawerHeader
                title={market?.display_name ?? a.slug}
                subtitle={a.slug}
                badge={
                  <Badge tone={a.enabled ? "ok" : "neutral"}>
                    {a.enabled ? "enabled" : "disabled"}
                  </Badge>
                }
              />
              <DrawerBody className="space-y-4">
                {market && (
                  <p className="text-[13px] text-coal-100">{market.description}</p>
                )}
                <section>
                  <h3 className="text-[11px] uppercase tracking-wide text-coal-200 mb-1.5">Tools</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {(market?.tools ?? []).map((t) => (
                      <code
                        key={t}
                        className="text-[11px] font-mono px-2 py-0.5 rounded bg-coal-500/40 text-coal-50 border border-coal-500"
                      >
                        {t}
                      </code>
                    ))}
                    {(!market || market.tools.length === 0) && (
                      <span className="text-[12px] text-coal-200">(none — one-shot skill)</span>
                    )}
                  </div>
                </section>
                <section>
                  <h3 className="text-[11px] uppercase tracking-wide text-coal-200 mb-1.5">Config</h3>
                  <pre className="rounded border border-coal-500 bg-coal-700/60 p-2.5 font-mono text-[11.5px] text-coal-50 whitespace-pre-wrap break-all">
                    {JSON.stringify(a.config, null, 2) || "{}"}
                  </pre>
                </section>
                <section className="text-[12.5px] text-coal-200">
                  Installed {absoluteFromSeconds(a.installed_at)} · {a.conversation_count} conversations · last used {a.last_used_at ? relativeFromSeconds(a.last_used_at) : "never"}.
                </section>
              </DrawerBody>
              <DrawerFooter>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => patch.mutate({ slug: a.slug, body: { enabled: !a.enabled } })}
                  disabled={patch.isPending}
                >
                  <Power className="size-3.5" />
                  {a.enabled ? "Disable" : "Enable"}
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => {
                    uninstall.mutate(a.slug);
                    setDrawerSlug(null);
                  }}
                  disabled={uninstall.isPending}
                >
                  <Trash2 className="size-3.5" />
                  Uninstall
                </Button>
              </DrawerFooter>
            </DrawerContent>
          );
        })()}
      </Drawer>
    </div>
  );
}

function MarketplaceCard({
  m,
  installed,
  installing,
  onInstall,
}: {
  m: MarketplaceAgent;
  installed: boolean;
  installing: boolean;
  onInstall: () => void;
}) {
  return (
    <li className="rounded-md border border-coal-500 bg-coal-600/60 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="size-5 rounded bg-iri-blue/20 text-iri-blue grid place-items-center">
              <Bot className="size-3" />
            </span>
            <span className="text-[13px] font-semibold text-coal-50">{m.display_name}</span>
            <code className="font-mono text-[10.5px] text-coal-200">{m.slug}</code>
          </div>
          <p className="mt-1 text-[12px] text-coal-100 leading-snug">{m.description}</p>
          {m.tools.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {m.tools.map((t) => (
                <code
                  key={t}
                  className="text-[10.5px] font-mono px-1.5 py-0.5 rounded bg-coal-500/40 text-coal-200"
                >
                  {t}
                </code>
              ))}
            </div>
          )}
        </div>
        <div className="shrink-0">
          {installed ? (
            <Badge tone="ok">
              <Check className="size-3" />
              Installed
            </Badge>
          ) : (
            <Button size="sm" variant="solid" onClick={onInstall} disabled={installing}>
              {installing ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
              {installing ? "Installing…" : "Install"}
            </Button>
          )}
        </div>
      </div>
    </li>
  );
}
