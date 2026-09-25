import { useQuery } from "@tanstack/react-query";
import { api, type AuditEvent } from "@/lib/api";
import { Card, Empty, ErrorNote, Spinner } from "@/components/ui";
import { fmtTime } from "@/lib/format";

export function Audit({ tid }: { tid: string }) {
  const q = useQuery({
    queryKey: ["audit", tid],
    queryFn: () => api.get<{ events: AuditEvent[] }>(`/tenants/${tid}/audit?limit=500`),
    refetchInterval: 15_000,
  });
  if (q.isPending) return <Spinner />;
  if (q.error) return <ErrorNote error={q.error} />;
  const events = [...q.data.events].reverse();
  if (!events.length) return <Empty title="No audit events yet" />;
  return (
    <Card>
      <table className="w-full text-left text-[13px]">
        <thead className="text-[12px] text-muted">
          <tr>
            <th className="pb-2 font-medium">When</th>
            <th className="pb-2 font-medium">Action</th>
            <th className="pb-2 font-medium">Details</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e, i) => {
            const { ts, action, ...rest } = e;
            return (
              <tr key={i} className="border-t border-line align-top">
                <td className="whitespace-nowrap py-1.5 pr-4 text-muted">{fmtTime(ts)}</td>
                <td className="whitespace-nowrap py-1.5 pr-4 font-mono text-[12px]">{action}</td>
                <td className="py-1.5 font-mono text-[12px] text-muted">
                  {Object.entries(rest).map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join("  ")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
