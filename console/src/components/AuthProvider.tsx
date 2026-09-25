import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api, getToken, type Whoami } from "@/lib/api";
import { AuthCtx } from "@/lib/auth";

/** Resolves what the stored token can do; renders `fallback` when there is none. */
export function AuthProvider({ children, fallback }: { children: ReactNode; fallback: ReactNode }) {
  const q = useQuery({
    queryKey: ["whoami", getToken()],
    queryFn: () => api.get<Whoami>("/whoami"),
    retry: false,
  });
  if (q.isPending) return null;
  if (q.isError) return <>{fallback}</>;
  const who = q.data;
  return (
    <AuthCtx.Provider value={{ who, isOperator: who.role === "admin" || who.role === "dev" }}>
      {children}
    </AuthCtx.Provider>
  );
}
