/**
 * DisconnectSkeleton — renders a placeholder bubble row when the WS is not
 * connected, but waits 200ms before showing so it doesn't flash on transient
 * reconnects. Replaces the previous "frozen UI" state during outages.
 */
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";

import { Skeleton } from "@/components/ui/Skeleton";

import type { Status } from "./useWsChat";

const DOWN: Status[] = ["closed", "error", "connecting"];

export default function DisconnectSkeleton({ status }: { status: Status }) {
  const down = DOWN.includes(status);
  const [delayed, setDelayed] = useState(false);

  useEffect(() => {
    if (!down) return;
    const t = window.setTimeout(() => setDelayed(true), 200);
    return () => {
      window.clearTimeout(t);
      setDelayed(false);
    };
  }, [down]);

  const visible = down && delayed;

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18, ease: [0.2, 0.7, 0.3, 1] }}
          className="px-4 py-2 flex items-start gap-3"
          aria-live="polite"
        >
          <Skeleton className="h-4 w-4 rounded-full mt-1" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-32" />
            <Skeleton className="h-3 w-56" />
            <Skeleton className="h-3 w-44" />
            <p className="text-[11px] text-ink-100 pt-1">
              {status === "connecting"
                ? "reconnecting to backend…"
                : status === "error"
                ? "agent offline — is uvicorn running on :8080?"
                : "waiting for chat to come back…"}
            </p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
