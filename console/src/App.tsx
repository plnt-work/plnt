import { useQueryClient } from "@tanstack/react-query";
import { LogOut, Sprout } from "lucide-react";
import { Link, Navigate, Route, Routes, useParams } from "react-router-dom";
import { setToken } from "@/lib/api";
import { AuthProvider } from "@/components/AuthProvider";
import { useAuth } from "@/lib/auth";
import { Login } from "@/pages/Login";
import { Tenant } from "@/pages/Tenant";
import { Tenants } from "@/pages/Tenants";

export function App() {
  return (
    <AuthProvider fallback={<Login />}>
      <Shell />
    </AuthProvider>
  );
}

function Shell() {
  const { who, isOperator } = useAuth();
  const qc = useQueryClient();
  const home = who.role === "tenant" ? `/t/${who.tenant_id}` : "/";
  return (
    <div className="flex min-h-full flex-col">
      <header className="flex h-12 items-center justify-between border-b border-line bg-panel px-4">
        <Link to={home} className="flex items-center gap-2 font-semibold">
          <Sprout className="size-4 text-accent" /> plnt
          <span className="font-normal text-muted">console</span>
        </Link>
        <div className="flex items-center gap-3 text-[12px] text-muted">
          <span>
            {who.role === "dev" && "dev mode · no auth"}
            {who.role === "admin" && "operator"}
            {who.role === "tenant" && `tenant ${who.tenant_id}`}
          </span>
          {who.role !== "dev" && (
            <button
              className="flex items-center gap-1 hover:text-ink"
              onClick={() => { setToken(""); void qc.invalidateQueries(); }}
            >
              <LogOut className="size-3.5" /> Sign out
            </button>
          )}
        </div>
      </header>
      <main className="flex-1">
        <Routes>
          <Route path="/" element={isOperator ? <Tenants /> : <Navigate to={home} replace />} />
          <Route path="/t/:tid/*" element={<TenantRoute />} />
          <Route path="*" element={<Navigate to={home} replace />} />
        </Routes>
      </main>
    </div>
  );
}

function TenantRoute() {
  const { tid = "" } = useParams();
  const { who } = useAuth();
  if (who.role === "tenant" && who.tenant_id !== tid) return <Navigate to={`/t/${who.tenant_id}`} replace />;
  return <Tenant tid={tid} />;
}
