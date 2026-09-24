// Typed env. EXPO_PUBLIC_* vars are baked into the bundle at build time.
// Reads are lazy via getters so a test that imports a downstream module
// (e.g. lib/api/venues for its mock helpers) doesn't trip the missing-
// var guard at import time. The throw still fires at first real access,
// preserving the HDGEcalls "don't silently fall back" rule.
const RAW = {
  apiBase: () => process.env.EXPO_PUBLIC_API_BASE,
  wsBase: () => process.env.EXPO_PUBLIC_WS_BASE,
  defaultTenant: () => process.env.EXPO_PUBLIC_DEFAULT_TENANT,
  tenant: () => process.env.EXPO_PUBLIC_TENANT_ID,
};

function required(get: () => string | undefined, label: string, key: string): string {
  const v = get();
  if (!v) {
    throw new Error(
      `[env] ${label} (${key}) is unset. Copy .env.development.example to ` +
        `.env.development and fill in your cloudflared hostnames.`,
    );
  }
  return v;
}

export const env = {
  get apiBase(): string {
    return required(RAW.apiBase, "EXPO_PUBLIC_API_BASE", "apiBase");
  },
  get wsBase(): string {
    return required(RAW.wsBase, "EXPO_PUBLIC_WS_BASE", "wsBase");
  },
  get defaultTenant(): string {
    return RAW.defaultTenant() || "demo";
  },
  /** Tenant id used for per-tenant API calls (bookings, venues, push).
   *  EXPO_PUBLIC_TENANT_ID overrides; defaults to "demo". */
  get tenant(): string {
    return RAW.tenant() || "demo";
  },
};
