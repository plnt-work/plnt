import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Session, type TenantDetail, type Usage } from "@/lib/api";
import { Badge, Card, Empty, ErrorNote, Stat } from "@/components/ui";
import { fmtNum, fmtTime, fmtUsd } from "@/lib/format";

const DAY = 86_400;

export function Overview({ tenant }: { tenant: TenantDetail }) {
  // Fixed when the tab opens; the queries refetch on an interval.
  const [since] = useState(() => Math.floor(Date.now() / 1000) - 30 * DAY);
  const usage = useQuery({
    queryKey: ["usage", tenant.id, "30d"],
    queryFn: () => api.get<Usage>(`/tenants/${tenant.id}/usage?since=${since}`),
    refetchInterval: 10_000,
  });
  const sessions = useQuery({
    queryKey: ["sessions", tenant.id],
    queryFn: () => api.get<{ sessions: Session[] }>(`/tenants/${tenant.id}/sessions?limit=200`),
    refetchInterval: 10_000,
  });
  const u = usage.data;
  const recent = sessions.data?.sessions ?? [];
  const active = recent.filter((s) => s.created_at >= since).length;
  const enabled = tenant.installs.filter((i) => i.enabled);

  return (
    <div className="space-y-4">
      <ErrorNote error={usage.error ?? sessions.error} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Conversations · 30 days" value={fmtNum(active)} />
        <Stat label="Model calls · 30 days" value={u ? fmtNum(u.model_calls) : "—"} />
        <Stat
          label="Tokens · 30 days"
          value={u ? fmtNum(u.prompt_tokens + u.completion_tokens) : "—"}
          sub={u && `${fmtNum(u.prompt_tokens)} in · ${fmtNum(u.completion_tokens)} out`}
        />
        <Stat
          label="Model cost · 30 days"
          value={u ? fmtUsd(u.cost_usd) : "—"}
          sub={tenant.model ? `${tenant.model.model} (own model)` : "server default model"}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Usage by agent and model">
          {!u || u.by_bundle_model.length === 0 ? (
            <p className="text-[13px] text-muted">No model calls in the last 30 days.</p>
          ) : (
            <table className="w-full text-left text-[13px]">
              <thead className="text-[12px] text-muted">
                <tr>
                  <th className="pb-2 font-medium">Agent</th>
                  <th className="pb-2 font-medium">Model</th>
                  <th className="pb-2 text-right font-medium">Calls</th>
                  <th className="pb-2 text-right font-medium">Tokens</th>
                  <th className="pb-2 text-right font-medium">Cost</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {u.by_bundle_model.map((r) => (
                  <tr key={`${r.bundle}/${r.model}`} className="border-t border-line">
                    <td className="py-1.5">{r.bundle}</td>
                    <td className="py-1.5 font-mono text-[12px]">{r.model}</td>
                    <td className="py-1.5 text-right">{fmtNum(r.model_calls)}</td>
                    <td className="py-1.5 text-right">{fmtNum(r.prompt_tokens + r.completion_tokens)}</td>
                    <td className="py-1.5 text-right">{fmtUsd(r.cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card title="Installed agents">
          {tenant.installs.length === 0 ? (
            <Empty title="No agents installed">Install one from the Agents tab.</Empty>
          ) : (
            <ul className="space-y-2 text-[13px]">
              {tenant.installs.map((i) => (
                <li key={`${i.slug}@${i.version}`} className="flex items-center justify-between">
                  <span>
                    <span className="font-medium">{i.slug}</span>
                    <span className="ml-1.5 text-muted">v{i.version}</span>
                  </span>
                  <Badge tone={i.enabled ? "good" : "neutral"}>{i.enabled ? "enabled" : "disabled"}</Badge>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-[12px] text-muted">
            {enabled.length} of {tenant.installs.length} enabled · last conversation{" "}
            {fmtTime(recent[0]?.created_at)}
          </p>
        </Card>
      </div>
    </div>
  );
}
