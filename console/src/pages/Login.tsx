import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, setToken, type Whoami } from "@/lib/api";
import { Button, ErrorNote, Field } from "@/components/ui";
import { inputClass } from "@/lib/format";

export function Login() {
  const qc = useQueryClient();
  const [token, setTok] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setToken(token.trim());
    try {
      await api.get<Whoami>("/whoami");
      await qc.invalidateQueries();
    } catch (err) {
      setToken("");
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-full place-items-center p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-lg border border-line bg-panel p-6">
        <div>
          <div className="text-lg font-semibold">plnt console</div>
          <p className="mt-1 text-[13px] text-muted">
            Sign in with the operator token (<code>PLNT_ADMIN_TOKEN</code>) to manage every
            tenant, or a tenant API key (<code>pk_…</code>) to manage one.
          </p>
        </div>
        <Field label="Token">
          <input className={inputClass} type="password" autoFocus value={token}
                 onChange={(e) => setTok(e.target.value)} autoComplete="current-password" />
        </Field>
        <ErrorNote error={error} />
        <Button type="submit" variant="primary" className="w-full" busy={busy} disabled={!token.trim()}>
          Sign in
        </Button>
      </form>
    </main>
  );
}
