import { useQuery } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type TenantDetail } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ErrorNote, Spinner, Tabs } from "@/components/ui";
import { Agents } from "./tenant/Agents";
import { Audit } from "./tenant/Audit";
import { Conversations } from "./tenant/Conversations";
import { Overview } from "./tenant/Overview";
import { Settings } from "./tenant/Settings";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "conversations", label: "Conversations" },
  { id: "agents", label: "Agents" },
  { id: "settings", label: "Settings" },
  { id: "audit", label: "Audit log" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export function Tenant({ tid }: { tid: string }) {
  const { isOperator } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find((t) => t.id === params.get("tab"))?.id ?? "overview") as TabId;
  const q = useQuery({
    queryKey: ["tenant", tid],
    queryFn: () => api.get<TenantDetail>(`/tenants/${tid}`),
  });

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-4 py-6 md:p-6">
      {isOperator && (
        <Link to="/" className="inline-flex items-center gap-1 text-[12px] text-muted hover:text-ink">
          <ChevronLeft className="size-3.5" /> All tenants
        </Link>
      )}
      <div>
        <h1 className="text-lg font-semibold">{q.data?.name ?? tid}</h1>
        <p className="font-mono text-[12px] text-muted">{tid}</p>
      </div>
      <Tabs tabs={[...TABS]} value={tab} onChange={(t) => setParams({ tab: t })} />
      {q.isPending && <Spinner />}
      <ErrorNote error={q.error} />
      {q.data && (
        <div className="pt-2">
          {tab === "overview" && <Overview tenant={q.data} />}
          {tab === "conversations" && <Conversations tenant={q.data} />}
          {tab === "agents" && <Agents tenant={q.data} />}
          {tab === "settings" && <Settings tenant={q.data} />}
          {tab === "audit" && <Audit tid={tid} />}
        </div>
      )}
    </div>
  );
}
