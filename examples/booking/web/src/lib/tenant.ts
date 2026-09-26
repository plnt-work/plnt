/**
 * Tenant resolution for the consumer surface.
 *
 * Precedence: ?tenant= query > subdomain (<slug>.chat.plnt.work or
 * <slug>.localhost) > VITE_DEFAULT_TENANT > "demo". The subdomain rule is
 * what lets one static bundle serve every tenant on a wildcard domain
 * with zero middleware.
 */

const SUBDOMAIN_RE = /^([a-z0-9][a-z0-9-]*)\.(?:chat\.plnt\.work|localhost)$/;

/** Tenant slug from the hostname, or null when not on a tenant subdomain. */
export function subdomainTenant(
  hostname: string = window.location.hostname,
): string | null {
  const m = SUBDOMAIN_RE.exec(hostname.toLowerCase());
  return m ? m[1] : null;
}

/** Effective tenant id for this page load. */
export function resolveTenant(
  search: string = window.location.search,
  hostname: string = window.location.hostname,
): string {
  const fromQuery = new URLSearchParams(search).get("tenant");
  if (fromQuery) return fromQuery;
  return (
    subdomainTenant(hostname) ||
    (import.meta.env.VITE_DEFAULT_TENANT as string | undefined) ||
    "demo"
  );
}
