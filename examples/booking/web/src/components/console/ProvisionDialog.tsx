/**
 * ProvisionDialog — provisioning sheet for new tenants.
 *
 * Two-step:
 *   1. Form (tenant id + display name)
 *   2. API key reveal — shown once, copyable, then dismissed
 *
 * When the backend returns no api_key (existing tenant re-provisioned),
 * skips straight to onCreated.
 */
import { useState } from "react";

import { createTenant, type TenantSummary } from "../../api/admin";

interface Props {
  onCancel: () => void;
  onCreated: (t: TenantSummary) => void;
}

const TENANT_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;

export default function ProvisionDialog({ onCancel, onCreated }: Props) {
  const [tid, setTid] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [issued, setIssued] = useState<{ tenantId: string; key: string } | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!TENANT_RE.test(tid)) {
      setErr("tenant_id must match a-z0-9 with _ or − (max 64).");
      return;
    }
    try {
      const t = await createTenant(tid, name || tid);
      if (t.api_key) {
        setIssued({ tenantId: t.tenant_id, key: t.api_key });
      } else {
        onCreated(t);
      }
    } catch (e) {
      setErr(String((e as Error).message));
    }
  };

  if (issued) {
    return (
      <div className="dialog-backdrop">
        <div className="dialog" onClick={(e) => e.stopPropagation()}>
          <h3>API key for <em>{issued.tenantId}</em></h3>
          <p style={{ color: "var(--coal-mute)", fontSize: 12.5, margin: 0 }}>
            Shown once. Stashed in this browser for the debug chat. Rotate via
            <span style={{ fontFamily: "JetBrains Mono, monospace" }}> POST /v1/admin/tenants/{issued.tenantId}/rotate-key</span> later.
          </p>
          <div className="api-key">{issued.key}</div>
          <div className="warn">⚑ store securely — cannot be retrieved later</div>
          <div className="actions">
            <button
              type="button"
              className="copy-btn"
              onClick={() => navigator.clipboard?.writeText(issued.key)}
            >
              copy
            </button>
            <button
              type="button"
              className="primary"
              onClick={() => onCreated({
                tenant_id: issued.tenantId,
                display_name: name || issued.tenantId,
                created_at: 0,
                home: "",
              })}
            >
              done
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dialog-backdrop" onClick={onCancel}>
      <form className="dialog" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h3>Provision <em>tenant</em></h3>

        <div className="field">
          <label htmlFor="tid">tenant id</label>
          <div className="control">
            <span className="prefix">@</span>
            <input id="tid" autoFocus value={tid} onChange={(e) => setTid(e.target.value)} placeholder="acme" />
          </div>
          <div className="help" style={{ color: "var(--coal-mute)" }}>
            a-z 0-9 with _ or − (max 64). Becomes the URL slug.
          </div>
        </div>

        <div className="field">
          <label htmlFor="dn">display name</label>
          <div className="control">
            <input id="dn" value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Pizzeria" />
          </div>
        </div>

        {err && <div className="auth-error">{err}</div>}

        <div className="actions">
          <button type="button" className="ghost" onClick={onCancel}>cancel</button>
          <button type="submit" className="primary">create</button>
        </div>
      </form>
    </div>
  );
}
