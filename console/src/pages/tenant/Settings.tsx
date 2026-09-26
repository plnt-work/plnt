import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Check, Copy, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, type ModelConfig, type ModelHealth, type TenantDetail } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge, Button, Card, ErrorNote, Field } from "@/components/ui";
import { inputClass } from "@/lib/format";

export function Settings({ tenant }: { tenant: TenantDetail }) {
  const { isOperator } = useAuth();
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <ModelCard tenant={tenant} />
      <SecretsCard tenant={tenant} />
      {isOperator && <KeyCard tid={tenant.id} />}
    </div>
  );
}

function useRefresh(tid: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["tenant", tid] });
}

const BLANK: ModelConfig = { provider: "ollama", base_url: "http://127.0.0.1:11434", model: "" };

function ModelCard({ tenant }: { tenant: TenantDetail }) {
  const refresh = useRefresh(tenant.id);
  const [own, setOwn] = useState(Boolean(tenant.model));
  const [cfg, setCfg] = useState<ModelConfig>(tenant.model ?? BLANK);
  const health = useQuery({
    queryKey: ["model-health", tenant.id, tenant.model],
    queryFn: () => api.get<ModelHealth>(`/tenants/${tenant.id}/model/health`),
    enabled: false,
  });
  const save = useMutation({
    mutationFn: () => (own ? api.put(`/tenants/${tenant.id}/model`, clean(cfg)) : api.del(`/tenants/${tenant.id}/model`)),
    onSuccess: refresh,
  });
  const set = (k: keyof ModelConfig, v: string) =>
    setCfg({ ...cfg, [k]: ["num_ctx", "cost_in_per_m", "cost_out_per_m"].includes(k) ? (v === "" ? undefined : Number(v)) : v });

  return (
    <Card title="Model" className="md:row-span-2">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        <div className="flex gap-4 text-[13px]">
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={!own} onChange={() => setOwn(false)} /> Server default
          </label>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={own} onChange={() => setOwn(true)} /> Tenant’s own model
          </label>
        </div>
        {own && (
          <>
            <Field label="Provider" required>
              <select className={inputClass} value={cfg.provider} onChange={(e) => set("provider", e.target.value)}>
                <option value="ollama">Ollama (native)</option>
                <option value="openai">OpenAI-compatible (OpenAI, Gemini, vLLM, llama.cpp, LM Studio)</option>
              </select>
            </Field>
            <Field label="Base URL" required hint={cfg.provider === "openai" ? "Usually ends in /v1" : undefined}>
              <input className={inputClass} value={cfg.base_url} onChange={(e) => set("base_url", e.target.value)} />
            </Field>
            <Field label="Model" required>
              <input className={inputClass} value={cfg.model} placeholder="qwen2.5:7b"
                     onChange={(e) => set("model", e.target.value)} />
            </Field>
            <Field label="API key secret" hint="Name of a secret below that holds the key (hosted APIs only).">
              <select className={inputClass} value={cfg.api_key_secret ?? ""}
                      onChange={(e) => set("api_key_secret", e.target.value)}>
                <option value="">None</option>
                {tenant.secrets.map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
            <div className="grid grid-cols-3 gap-2">
              <Field label="Context (num_ctx)">
                <input type="number" className={inputClass} value={cfg.num_ctx ?? ""} onChange={(e) => set("num_ctx", e.target.value)} />
              </Field>
              <Field label="$ / 1M in">
                <input type="number" step="any" className={inputClass} value={cfg.cost_in_per_m ?? ""} onChange={(e) => set("cost_in_per_m", e.target.value)} />
              </Field>
              <Field label="$ / 1M out">
                <input type="number" step="any" className={inputClass} value={cfg.cost_out_per_m ?? ""} onChange={(e) => set("cost_out_per_m", e.target.value)} />
              </Field>
            </div>
          </>
        )}
        <ErrorNote error={save.error} />
        <div className="flex gap-2">
          <Button type="submit" variant="primary" busy={save.isPending}>Save</Button>
          <Button type="button" busy={health.isFetching} onClick={() => void health.refetch()}>
            <Activity className="size-3.5" /> Check model
          </Button>
        </div>
        {health.data && (
          <div className="rounded-md bg-sunken px-3 py-2 text-[12px]">
            <Badge tone={health.data.ok ? "good" : "bad"}>{health.data.ok ? "healthy" : "not usable"}</Badge>
            <span className="ml-2 font-mono">{health.data.model} @ {health.data.base_url}</span>
            {health.data.detail && <p className="mt-1 text-muted">{health.data.detail}</p>}
            {health.data.hint && <p className="mt-1">Fix: {health.data.hint}</p>}
          </div>
        )}
        <ErrorNote error={health.error} />
      </form>
    </Card>
  );
}

function clean(cfg: ModelConfig): Partial<ModelConfig> {
  return Object.fromEntries(Object.entries(cfg).filter(([, v]) => v !== undefined && v !== ""));
}

function SecretsCard({ tenant }: { tenant: TenantDetail }) {
  const refresh = useRefresh(tenant.id);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const put = useMutation({
    mutationFn: () => api.put(`/tenants/${tenant.id}/secrets/${name}`, { value }),
    onSuccess: () => { setName(""); setValue(""); void refresh(); },
  });
  const del = useMutation({ mutationFn: (n: string) => api.del(`/tenants/${tenant.id}/secrets/${n}`), onSuccess: refresh });
  return (
    <Card title="Secrets">
      <p className="mb-3 text-[12px] text-muted">
        Values are write-only: agents’ tools can read them, nobody can read them back here.
      </p>
      <ul className="mb-3 space-y-1">
        {tenant.secrets.length === 0 && <li className="text-[13px] text-muted">No secrets set.</li>}
        {tenant.secrets.map((s) => (
          <li key={s} className="flex items-center justify-between text-[13px]">
            <span className="font-mono">{s}</span>
            <Button variant="ghost" aria-label={`Delete ${s}`} onClick={() => del.mutate(s)}>
              <Trash2 className="size-3.5" />
            </Button>
          </li>
        ))}
      </ul>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); put.mutate(); }}>
        <input className={inputClass} placeholder="NAME" value={name} aria-label="Secret name"
               onChange={(e) => setName(e.target.value.toUpperCase())} />
        <input className={inputClass} type="password" placeholder="value" value={value} aria-label="Secret value"
               onChange={(e) => setValue(e.target.value)} autoComplete="off" />
        <Button type="submit" busy={put.isPending} disabled={!name || !value}>Set</Button>
      </form>
      <div className="mt-2"><ErrorNote error={put.error ?? del.error} /></div>
    </Card>
  );
}

function KeyCard({ tid }: { tid: string }) {
  const [key, setKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const rotate = useMutation({
    mutationFn: () => api.post<{ api_key: string }>(`/tenants/${tid}/keys`),
    onSuccess: (r) => { setKey(r.api_key); setCopied(false); },
  });
  return (
    <Card title="API key">
      <p className="text-[12px] text-muted">
        Rotating issues a new key immediately; the old one stops working.
      </p>
      {key && (
        <div className="mt-3 flex gap-2">
          <code className="flex-1 overflow-x-auto rounded-md bg-sunken px-2.5 py-1.5 text-[12px]">{key}</code>
          <Button onClick={() => { void navigator.clipboard.writeText(key); setCopied(true); }}>
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          </Button>
        </div>
      )}
      <div className="mt-3 flex gap-2">
        <Button variant="danger" busy={rotate.isPending}
                onClick={() => confirm("Rotate this tenant's API key? The current key stops working.") && rotate.mutate()}>
          Rotate key
        </Button>
      </div>
      <ErrorNote error={rotate.error} />
    </Card>
  );
}
