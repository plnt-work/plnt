import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api, ApiError, getToken, type Whoami } from "@/lib/api";
import { Button, ErrorNote, Spinner } from "@/components/ui";
import { AuthCtx } from "@/lib/auth";

/** Resolves what the stored token can do; renders `fallback` when there is none. */
export function AuthProvider({ children, fallback }: { children: ReactNode; fallback: ReactNode }) {
  const q = useQuery({
    queryKey: ["whoami", getToken()],
    queryFn: () => api.get<Whoami>("/whoami"),
    retry: false,
  });
  if (q.isPending) {
    return (
      <div className="grid min-h-full place-items-center">
        <Spinner />
      </div>
    );
  }
  if (q.isError) {
    // Only "who are you?" answers send you to sign in. Anything else (server
    // down, 500) is said out loud instead of looking like a logout.
    const status = q.error instanceof ApiError ? q.error.status : 0;
    if (status === 401 || status === 403) return <>{fallback}</>;
    return (
      <div className="mx-auto max-w-md space-y-3 p-6">
        <h1 className="text-lg font-semibold">Cannot reach the plnt server</h1>
        <ErrorNote error={q.error} />
        <Button onClick={() => void q.refetch()} busy={q.isFetching}>Try again</Button>
      </div>
    );
  }
  const who = q.data;
  return (
    <AuthCtx.Provider value={{ who, isOperator: who.role === "admin" || who.role === "dev" }}>
      {children}
    </AuthCtx.Provider>
  );
}
