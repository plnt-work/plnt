/**
 * Onboard query hooks — @tanstack/react-query around lib/api/onboard.ts,
 * mirroring lib/queries/admin.ts. No mock layer: the onboard backend
 * shipped with slice-5a, so hooks always hit the live endpoints.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "../api/onboard";

/**
 * Signed-in merchant, or `null` when there is no valid onboard session.
 * 401 is the expected signed-out state, not an error.
 */
export function useOnboardMe() {
  return useQuery<api.Me | null>({
    queryKey: ["onboard-me"],
    queryFn: async () => {
      try {
        return await api.getMe();
      } catch (e) {
        if (e instanceof api.OnboardApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: 30_000,
    retry: false,
  });
}

export function useBusinessSearch(q: string) {
  return useQuery<api.SearchResponse>({
    queryKey: ["onboard-search", q],
    queryFn: () => api.searchBusiness(q),
    enabled: q.trim().length >= 2,
    staleTime: 60_000,
    retry: false,
  });
}

export function useClaimBusiness() {
  return useMutation({ mutationFn: api.claimBusiness });
}

export function useCreateTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createTenant,
    onSuccess: () => {
      // The new tenant now belongs to this merchant.
      qc.invalidateQueries({ queryKey: ["onboard-me"] });
    },
  });
}

export function useInstallFirstAgent() {
  return useMutation({ mutationFn: api.installFirstAgent });
}
