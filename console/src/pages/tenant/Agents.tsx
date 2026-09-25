import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Settings2, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, type CatalogBundle, type Install, type JsonSchema, type TenantDetail } from "@/lib/api";
import { SchemaForm } from "@/components/SchemaForm";
import { pruneBlankRows, withDefaults } from "@/lib/schema";
import { Badge, Button, Card, Empty, ErrorNote, Modal, Spinner } from "@/components/ui";
import { fmtTime } from "@/lib/format";

export function Agents({ tenant }: { tenant: TenantDetail }) {
  const catalog = useQuery({
    queryKey: ["catalog"],
    queryFn: () => api.get<{ bundles: CatalogBundle[]; errors: Record<string, string> }>("/bundles"),
  });
  const [installing, setInstalling] = useState<CatalogBundle | null>(null);
  const [editing, setEditing] = useState<Install | null>(null);
  const installed = new Set(tenant.installs.map((i) => i.slug));

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h2 className="text-[13px] font-semibold">Installed</h2>
        {tenant.installs.length === 0 ? (
          <Empty title="No agents installed">Pick one from the catalog below.</Empty>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {tenant.installs.map((i) => (
              <InstalledCard key={`${i.slug}@${i.version}`} tid={tenant.id} inst={i}
                             secrets={tenant.secrets} onEdit={() => setEditing(i)} />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-[13px] font-semibold">Catalog</h2>
        {catalog.isPending && <Spinner />}
        <ErrorNote error={catalog.error} />
        <div className="grid gap-3 md:grid-cols-2">
          {catalog.data?.bundles.map((b) => (
            <Card key={b.slug}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">{b.slug} <span className="font-normal text-muted">v{b.version}</span></div>
                  <p className="mt-1 text-[13px] text-muted">{b.description}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {b.tools.map((t) => <Badge key={t}>{t}</Badge>)}
                    {b.secrets.map((s) => <Badge key={s} tone="warn">needs {s}</Badge>)}
                  </div>
                </div>
                <Button variant={installed.has(b.slug) ? "secondary" : "primary"} onClick={() => setInstalling(b)}>
                  {installed.has(b.slug) ? "Reinstall" : "Install"}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {installing && (
        <ConfigDialog
          title={`Install ${installing.slug}`}
          schema={installing.config_schema}
          initial={withDefaults(installing.config_schema,
                                tenant.installs.find((i) => i.slug === installing.slug)?.config)}
          missingSecrets={installing.secrets.filter((s) => !tenant.secrets.includes(s))}
          onClose={() => setInstalling(null)}
          save={(config) => api.post(`/tenants/${tenant.id}/installs`, { bundle: installing.slug, config })}
          tid={tenant.id}
        />
      )}
      {editing && (
        <ConfigDialog
          title={`${editing.slug} settings`}
          schema={editing.config_schema ?? null}
          initial={editing.config}
          missingSecrets={(editing.secrets_required ?? []).filter((s) => !tenant.secrets.includes(s))}
          onClose={() => setEditing(null)}
          save={(config) => api.patch(`/tenants/${tenant.id}/installs/${editing.slug}`, { config })}
          tid={tenant.id}
        />
      )}
    </div>
  );
}

function InstalledCard({ tid, inst, secrets, onEdit }: {
  tid: string;
  inst: Install;
  secrets: string[];
  onEdit: () => void;
}) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["tenant", tid] });
  const toggle = useMutation({
    mutationFn: () => api.patch(`/tenants/${tid}/installs/${inst.slug}`, { enabled: !inst.enabled }),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: () => api.del(`/tenants/${tid}/installs/${inst.slug}`), onSuccess: refresh });
  const missing = (inst.secrets_required ?? []).filter((s) => !secrets.includes(s));

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium">{inst.slug}</span>
            <span className="text-muted">v{inst.version}</span>
            <Badge tone={inst.enabled ? "good" : "neutral"}>{inst.enabled ? "enabled" : "disabled"}</Badge>
          </div>
          {inst.description && <p className="mt-1 text-[13px] text-muted">{inst.description}</p>}
          <p className="mt-1 text-[12px] text-muted">
            installed {fmtTime(inst.installed_at)} · <span className="font-mono">{inst.digest.slice(0, 12)}</span>
          </p>
          {missing.length > 0 && (
            <p className="mt-2 flex items-center gap-1 text-[12px] text-warn">
              <KeyRound className="size-3.5" /> Set secret {missing.join(", ")} in Settings before use.
            </p>
          )}
          {inst.load_error && <p className="mt-2 text-[12px] text-danger">{inst.load_error}</p>}
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <Button onClick={onEdit}><Settings2 className="size-3.5" /> Settings</Button>
        <Button busy={toggle.isPending} onClick={() => toggle.mutate()}>
          {inst.enabled ? "Disable" : "Enable"}
        </Button>
        <Button variant="danger" busy={remove.isPending}
                onClick={() => confirm(`Uninstall ${inst.slug}? Its settings are removed.`) && remove.mutate()}>
          <Trash2 className="size-3.5" /> Uninstall
        </Button>
      </div>
      <ErrorNote error={toggle.error ?? remove.error} />
    </Card>
  );
}

function ConfigDialog({ title, schema, initial, missingSecrets, onClose, save, tid }: {
  title: string;
  schema: JsonSchema | null;
  initial: Record<string, unknown>;
  missingSecrets: string[];
  onClose: () => void;
  save: (config: Record<string, unknown>) => Promise<unknown>;
  tid: string;
}) {
  const qc = useQueryClient();
  const [value, setValue] = useState(initial);
  const m = useMutation({
    mutationFn: () => save(pruneBlankRows(schema, value)),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenant", tid] });
      onClose();
    },
  });
  return (
    <Modal open onClose={onClose} title={title} wide>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); m.mutate(); }}>
        {missingSecrets.length > 0 && (
          <p className="rounded-md bg-warn-soft px-3 py-2 text-[12px] text-warn">
            This agent needs the secret{missingSecrets.length > 1 ? "s" : ""} {missingSecrets.join(", ")}.
            Set {missingSecrets.length > 1 ? "them" : "it"} in Settings → Secrets.
          </p>
        )}
        <SchemaForm schema={schema} value={value} onChange={setValue} />
        <ErrorNote error={m.error} />
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" busy={m.isPending}>Save</Button>
        </div>
      </form>
    </Modal>
  );
}
