import { createContext, useContext } from "react";
import type { Whoami } from "./api";

export type Auth = { who: Whoami; isOperator: boolean };

export const AuthCtx = createContext<Auth | null>(null);

export function useAuth(): Auth {
  const a = useContext(AuthCtx);
  if (!a) throw new Error("useAuth outside AuthProvider");
  return a;
}
