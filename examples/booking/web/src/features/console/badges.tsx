import { Badge } from "@/components/ui/Badge";
import type { BookingStatus, SessionStatus } from "@/lib/api/admin-v2";

export function BookingStatusBadge({ status }: { status: BookingStatus }) {
  const tone =
    status === "confirmed" ? "ok"
    : status === "pending" ? "warn"
    : status === "failed" ? "danger"
    : "neutral";
  return <Badge tone={tone}>{status}</Badge>;
}

export function SessionStatusBadge({ status }: { status: SessionStatus }) {
  const tone =
    status === "active" ? "ok"
    : status === "idle" ? "warn"
    : "neutral";
  return <Badge tone={tone}>{status}</Badge>;
}
