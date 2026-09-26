/**
 * Admin v2 query hooks — @tanstack/react-query around lib/api/admin-v2.ts.
 *
 * Source toggle: until the MA stream's task #8 ships its endpoints, hooks
 * point at the mocks in lib/api/admin-mocks.ts. Each hook has a single
 * `LIVE_MODE` constant at the top; flipping that (or setting
 * VITE_ADMIN_LIVE=1 at build) hits the real endpoints. No component-layer
 * edits needed.
 *
 * Cache keys are tuples [resource, tenantId, ...filters] so a tenant
 * switch invalidates cleanly and filter changes only refetch their
 * scoped variant.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import * as live from "../api/admin-v2";
import * as mock from "../api/admin-mocks";
import { mockOverviewKpis, type OverviewKpis } from "../api/admin-mocks";

// Live by default now that the MA-P6 admin v2 endpoints are shipped.
// Set VITE_ADMIN_LIVE=0 to fall back to the in-memory mocks (useful for
// storybook / offline UI work).
const LIVE_MODE =
  (import.meta.env.VITE_ADMIN_LIVE as string | undefined) !== "0";

/** Pick the right transport. Centralized so every hook benefits from
 *  one swap when the backend ships. */
const src = LIVE_MODE
  ? {
      bookings: live.listBookings,
      sessions: live.listSessions,
      transcript: live.getTranscript,
      users: live.listUsers,
      user: live.getUser,
      marketplace: live.listMarketplace,
      installed: live.listInstalledAgents,
      install: live.installAgent,
      patch: live.patchAgent,
      uninstall: live.uninstallAgent,
      notifications: live.listNotifications,
      markRead: live.markNotificationsRead,
      // No live overview KPI endpoint yet — when the backend ships it,
      // wire it here.
      overview: mockOverviewKpis,
    }
  : {
      bookings: mock.mockListBookings,
      sessions: mock.mockListSessions,
      transcript: mock.mockGetTranscript,
      users: mock.mockListUsers,
      user: mock.mockGetUser,
      marketplace: mock.mockListMarketplace,
      installed: mock.mockListInstalledAgents,
      install: mock.mockInstallAgent,
      patch: mock.mockPatchAgent,
      uninstall: mock.mockUninstallAgent,
      notifications: mock.mockListNotifications,
      markRead: mock.mockMarkNotificationsRead,
      overview: mockOverviewKpis,
    };

const STALE = {
  fast: 5_000,    // tables that should feel live
  med: 30_000,    // backgroundy
  slow: 5 * 60_000,
};

const POLL = {
  fast: 10_000,
  med: 30_000,
};

/* ─── Overview ──────────────────────────────────────────────────── */

export function useOverview(tenantId: string | null) {
  return useQuery<OverviewKpis>({
    queryKey: ["overview", tenantId],
    queryFn: () => src.overview(tenantId!),
    enabled: !!tenantId,
    staleTime: STALE.fast,
    refetchInterval: POLL.fast,
  });
}

/* ─── Bookings ──────────────────────────────────────────────────── */

interface BookingsFilters {
  status?: live.BookingStatus;
  user_id?: string;
  since?: number;
  limit?: number;
}

export function useBookings(tenantId: string | null, filters: BookingsFilters = {}) {
  return useQuery<live.BookingsResponse>({
    queryKey: ["bookings", tenantId, filters],
    queryFn: () => src.bookings(tenantId!, filters),
    enabled: !!tenantId,
    staleTime: STALE.fast,
    refetchInterval: POLL.fast,
  });
}

/* ─── Sessions ──────────────────────────────────────────────────── */

export function useSessions(
  tenantId: string | null,
  filters: { user_id?: string; limit?: number } = {},
) {
  return useQuery<live.SessionsResponse>({
    queryKey: ["sessions", tenantId, filters],
    queryFn: () => src.sessions(tenantId!, filters),
    enabled: !!tenantId,
    staleTime: STALE.fast,
    refetchInterval: POLL.fast,
  });
}

export function useTranscript(
  tenantId: string | null,
  sessionId: string | null,
  opts?: Partial<UseQueryOptions<live.TranscriptResponse>>,
) {
  return useQuery<live.TranscriptResponse>({
    queryKey: ["transcript", tenantId, sessionId],
    queryFn: () => src.transcript(tenantId!, sessionId!),
    enabled: !!tenantId && !!sessionId,
    staleTime: STALE.med,
    ...opts,
  });
}

/* ─── Notifications ─────────────────────────────────────────────── */

export function useNotifications(
  tenantId: string | null,
  filters: { limit?: number; unread?: boolean } = {},
) {
  return useQuery<live.NotificationsResponse>({
    queryKey: ["notifications", tenantId, filters],
    queryFn: () => src.notifications(tenantId!, filters),
    enabled: !!tenantId,
    staleTime: STALE.fast,
    refetchInterval: POLL.fast,
  });
}

export function useMarkNotificationsRead(tenantId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => src.markRead(tenantId!, ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications", tenantId] });
    },
  });
}

/* ─── Users ─────────────────────────────────────────────────────── */

export function useUsers(tenantId: string | null) {
  return useQuery<live.UsersResponse>({
    queryKey: ["users", tenantId],
    queryFn: () => src.users(tenantId!),
    enabled: !!tenantId,
    staleTime: STALE.med,
    refetchInterval: POLL.med,
  });
}

export function useUser(tenantId: string | null, userId: string | null) {
  return useQuery<live.UserDetail>({
    queryKey: ["user", tenantId, userId],
    queryFn: () => src.user(tenantId!, userId!),
    enabled: !!tenantId && !!userId,
    staleTime: STALE.med,
  });
}

/* ─── Agents (marketplace + installed) ──────────────────────────── */

export function useMarketplace(vertical?: string) {
  return useQuery<live.MarketplaceResponse>({
    queryKey: ["marketplace", vertical ?? "all"],
    queryFn: () => src.marketplace(vertical),
    staleTime: STALE.slow,
  });
}

export function useInstalledAgents(tenantId: string | null) {
  return useQuery<live.InstalledAgentsResponse>({
    queryKey: ["installed-agents", tenantId],
    queryFn: () => src.installed(tenantId!),
    enabled: !!tenantId,
    staleTime: STALE.med,
  });
}

export function useInstallAgent(tenantId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => src.install(tenantId!, slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["installed-agents", tenantId] });
    },
  });
}

export function usePatchAgent(tenantId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, body }: { slug: string; body: { enabled?: boolean; config?: Record<string, unknown> } }) =>
      src.patch(tenantId!, slug, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["installed-agents", tenantId] });
    },
  });
}

export function useUninstallAgent(tenantId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => src.uninstall(tenantId!, slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["installed-agents", tenantId] });
    },
  });
}
