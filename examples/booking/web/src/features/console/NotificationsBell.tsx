/**
 * NotificationsBell — topbar bell with unread badge + feed dialog.
 * Data: useNotifications (poll) + useMarkNotificationsRead.
 */
import { useState } from "react";
import { Bell } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/Dialog";
import { cn } from "@/lib/cn";
import { relativeFromSeconds } from "@/lib/format";
import { useMarkNotificationsRead, useNotifications } from "@/lib/queries/admin";

export default function NotificationsBell({ tenantId }: { tenantId: string | null }) {
  const [open, setOpen] = useState(false);
  const { data } = useNotifications(tenantId, { limit: 50 });
  const markRead = useMarkNotificationsRead(tenantId);

  const notifications = data?.notifications ?? [];
  const unread = data?.unread_count ?? 0;
  const unreadIds = notifications.filter((n) => !n.read).map((n) => n.id);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          aria-label={unread > 0 ? `Notifications (${unread} unread)` : "Notifications"}
          className="relative grid size-8 place-items-center rounded-md text-coal-200 hover:text-coal-50 hover:bg-coal-500/40 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-iri-blue/40"
        >
          <Bell className="size-4" />
          {unread > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-iri-blue text-white text-[10px] font-semibold grid place-items-center">
              {unread > 99 ? "99+" : unread}
            </span>
          )}
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Notifications</DialogTitle>
          <DialogDescription>
            {unread > 0 ? `${unread} unread` : "All caught up"}
          </DialogDescription>
        </DialogHeader>

        {unreadIds.length > 0 && (
          <button
            type="button"
            onClick={() => markRead.mutate(unreadIds)}
            disabled={markRead.isPending}
            className="self-start text-[12.5px] font-medium text-iri-blue hover:underline disabled:opacity-50"
          >
            Mark all read
          </button>
        )}

        <ul className="max-h-96 overflow-y-auto -mx-2 divide-y divide-paper-500">
          {notifications.length === 0 && (
            <li className="px-2 py-6 text-center text-sm text-ink-200">
              No notifications yet.
            </li>
          )}
          {notifications.map((n) => (
            <li key={n.id} className={cn("px-2 py-2.5", !n.read && "bg-paper-100")}>
              <div className="flex items-baseline justify-between gap-3">
                <span className={cn("text-[13px] text-ink-700", !n.read && "font-semibold")}>
                  {n.title}
                </span>
                <span className="shrink-0 text-[11.5px] text-ink-200">
                  {relativeFromSeconds(n.ts)}
                </span>
              </div>
              <p className="mt-0.5 text-[12.5px] text-ink-200">{n.body}</p>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
