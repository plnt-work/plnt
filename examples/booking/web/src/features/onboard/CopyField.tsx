import { useState } from "react";

import { Button } from "@/components/ui/Button";

/** Read-only value with a copy-to-clipboard button. */
export function CopyField({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <div className="flex items-center gap-2">
      <code className="min-w-0 flex-1 truncate rounded-md border border-paper-600 bg-paper-200 px-3 py-2 text-sm text-ink-700">
        {value}
      </code>
      <Button
        variant="outline"
        size="sm"
        aria-label={`Copy ${label}`}
        onClick={() => {
          void navigator.clipboard?.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
      >
        {copied ? "Copied" : "Copy"}
      </Button>
    </div>
  );
}
