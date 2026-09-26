import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { GOOGLE_START_URL, probeGoogleStart, type Me } from "@/lib/api/onboard";

/**
 * Step 1 — Google identity sign-in.
 *
 * The start endpoint is a full-page redirect, so the button navigates
 * (never fetches). A cheap `redirect: "manual"` probe first catches the
 * dev-mode 503 (`oauth_not_configured`) so we can render a panel instead
 * of dumping the user on a raw JSON page.
 */
export function SignInStep({ me, onAddAnother }: { me: Me | null; onAddAnother: () => void }) {
  const [oauthMissing, setOauthMissing] = useState(false);
  const [probing, setProbing] = useState(false);
  const [probeFailed, setProbeFailed] = useState(false);

  // Already signed in: no tenants → straight to claim; owns tenants →
  // offer the dashboard or another run through the wizard.
  if (me && me.tenants.length === 0) return <Navigate to="/onboard?step=claim" replace />;
  if (me) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold text-ink-700">You're already set up</h1>
        <p className="text-sm text-ink-200">
          Signed in as {me.email}, owner of{" "}
          {me.tenants.map((t) => t.business_name).join(", ")}.
        </p>
        <div className="flex items-center gap-3">
          <Button asChild>
            <Link to={`/console?tenant=${encodeURIComponent(me.tenants[0].tenant_id)}`}>
              Go to dashboard
            </Link>
          </Button>
          <Button variant="outline" onClick={onAddAnother}>
            Add another business
          </Button>
        </div>
      </div>
    );
  }

  const start = async () => {
    setProbing(true);
    setProbeFailed(false);
    try {
      const status = await probeGoogleStart();
      if (status === "unconfigured") {
        setOauthMissing(true);
        return;
      }
      window.location.href = GOOGLE_START_URL;
    } catch {
      setProbeFailed(true);
    } finally {
      setProbing(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink-700">
        Get your business a booking agent
      </h1>
      <p className="text-sm text-ink-200">
        Sign in, claim your business, and share a chat link your customers can
        book through — about five minutes end to end.
      </p>
      <div>
        <Button size="lg" onClick={() => void start()} disabled={probing}>
          Continue with Google
        </Button>
      </div>
      {oauthMissing && (
        <div className="rounded-md border border-paper-600 bg-paper-200 p-4 text-sm text-ink-500">
          <p className="font-medium text-ink-700">OAuth not configured on the server</p>
          <p className="mt-1">
            Set <code>GOOGLE_OAUTH_CLIENT_ID</code> and{" "}
            <code>GOOGLE_OAUTH_CLIENT_SECRET</code> in the API environment and
            restart it, then try again.
          </p>
        </div>
      )}
      {probeFailed && (
        <p className="text-sm text-rust">Couldn't reach the API — is it running?</p>
      )}
    </div>
  );
}
