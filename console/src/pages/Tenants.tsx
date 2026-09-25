import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type TenantSummary } from "@/lib/api";
import { Button, Card, Empty, ErrorNote, Field, Modal, Spinner } from "@/components/ui";
import { fmtTime, inputClass } from "@/lib/format";

export function Tenants() {
  const q = useQuery({
    queryKey: ["tenants"],
    queryFn: () => api.get<{ tenants: TenantSummary[] }>("/tenants"),
  });
  const [creating, setCreating] = useState(false);

  return (
    <div className="mx-auto max-w-5xl space-y-4 px-4 py-6 md:p-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-lg font-semibold">Tenants</h1>
          <p className="text-[13px] text-muted">Each tenant is one customer with its own agents, data and keys.</p>
        </div>
        <Button variant="primary" onClick={() => setCreating(true)}>
          <Plus className="size-3.5" /> New tenant
        </Button>
      </div>

      {q.isPending && <Spinner />}
      <ErrorNote error={q.error} />
      {q.data && q.data.tenants.length === 0 && (
        <Empty title="No tenants yet">Create one to install an agent for a customer.</Empty>
      )}
      {q.data && q.data.tenants.length > 0 && (
        <Card>
          <table className="w-full text-left text-[13px]">
            <thead className="text-[12px] text-muted">
              <tr><th className="pb-2 font-medium">Tenant</th><th className="pb-2 font-medium">Created</th></tr>
            </thead>
            <tbody>
              {q.data.tenants.map((t) => (
                <tr key={t.id} className="border-t border-line">
                  <td className="py-2">
                    <Link to={`/t/${t.id}`} className="font-medium hover:underline">{t.name}</Link>
                    {t.name !== t.id && <span className="ml-2 font-mono text-[12px] text-muted">{t.id}</span>}
                  </td>
                  <td className="py-2 text-muted">{fmtTime(t.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      <CreateTenant open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function CreateTenant({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [copied, setCopied] = useState(false);
  const m = useMutation({
    mutationFn: () => api.post<{ tenant: TenantSummary; api_key: string }>("/tenants", { id, name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenants"] }),
  });
  const close = () => {
    setId("");
    setName("");
    setCopied(false);
    m.reset();
    onClose();
  };

  return (
    <Modal open={open} onClose={close} title={m.data ? "Tenant created" : "New tenant"}>
      {m.data ? (
        <div className="space-y-3">
          <p className="text-[13px]">
            This is <b>{m.data.tenant.name}</b>’s API key. It is shown once — store it now. The
            tenant uses it to call the API and to sign in here.
          </p>
          <div className="flex gap-2">
            <code className="flex-1 overflow-x-auto rounded-md bg-sunken px-2.5 py-1.5 text-[12px]">
              {m.data.api_key}
            </code>
            <Button onClick={() => {
              void navigator.clipboard.writeText(m.data.api_key);
              setCopied(true);
            }}>
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <div className="flex justify-end"><Button variant="primary" onClick={close}>Done</Button></div>
        </div>
      ) : (
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
          <Field label="ID" hint="Lowercase letters, digits and dashes. Used in URLs." required>
            <input className={inputClass} value={id} placeholder="luigis-bistro"
                   onChange={(e) => setId(e.target.value.toLowerCase())} />
          </Field>
          <Field label="Name">
            <input className={inputClass} value={name} placeholder="Luigi's Bistro"
                   onChange={(e) => setName(e.target.value)} />
          </Field>
          <ErrorNote error={m.error} />
          <div className="flex justify-end gap-2">
            <Button type="button" onClick={close}>Cancel</Button>
            <Button type="submit" variant="primary" busy={m.isPending} disabled={!id}>Create</Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
