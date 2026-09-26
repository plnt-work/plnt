import { Link } from "react-router-dom";

import { Button } from "@/components/ui/Button";

import { CopyField } from "./CopyField";

/**
 * Final step — the share card. tenant_id === slug (create returns the
 * slug as tenant_id), so the URL param is all this step needs. Atlas
 * honors ?tenant= as of slice 6, so "Open your chat" scopes correctly.
 */
export function DoneStep({ tenantId }: { tenantId: string }) {
  const shareUrl = `https://${tenantId}.chat.plnt.work`;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink-700">Your agent is live</h1>
      <p className="text-sm text-ink-200">
        Share this link — customers who open it can chat and book directly.
      </p>
      <CopyField value={shareUrl} label="share link" />
      <div className="flex items-center gap-3">
        <Button asChild>
          <Link to={`/atlas?tenant=${encodeURIComponent(tenantId)}`}>Open your chat</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to={`/console?tenant=${encodeURIComponent(tenantId)}`}>
            Open your dashboard
          </Link>
        </Button>
      </div>
    </div>
  );
}
