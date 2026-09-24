"""Per-tenant factory — replaces the 5 module singletons in plnt/surface/server.py.

For each tenant_id we lazily build a TenantBundle that owns the tenant's
isolated state surfaces:

  * home dir        — $PLNT_CLOUD_HOME/tenants/<tid>/ (default ~/.plnt-cloud/...)
  * integrations    — per-tenant IntegrationsStore(home/"integrations.toml")
  * blackboard root — home/"runs" (plnt's Blackboard takes `root=` kwarg)
  * memori          — per-tenant Memori instance (entity_id=user, process_id=role)
  * skills dir      — pointed at plnt-cloud/microagents/skills/
  * agents dir      — home/"agents" (per-tenant installed skill bundles)

Cached so the bundle for a given tenant is shared across requests. Eviction
is not automatic — call `clear_cache()` in tests.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plnt.surface.integrations import IntegrationsStore
    from memory.memori_adapter import MemoriAdapter


def cloud_home() -> Path:
    """Root directory for all tenant state. Override with $PLNT_CLOUD_HOME."""
    raw = os.environ.get("PLNT_CLOUD_HOME") or "~/.plnt-cloud"
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def microagents_skills_dir() -> Path:
    """Where the slice-1 skill bundles live (microagents/skills/)."""
    # Resolved relative to this file so dev installs (editable) and packaged
    # installs both find it.
    return (Path(__file__).resolve().parent.parent / "microagents" / "skills").resolve()


@dataclass(frozen=True)
class TenantBundle:
    """All tenant-scoped state surfaces. Pass this into Activities / Workflows."""

    tenant_id: str
    home: Path
    blackboard_root: Path
    integrations: "IntegrationsStore"
    memori: "MemoriAdapter"
    skills_dir: Path
    agents_dir: Path


@lru_cache(maxsize=256)
def for_tenant(tenant_id: str) -> TenantBundle:
    """Get (and lazily construct) the TenantBundle for `tenant_id`.

    Cached process-wide. Bundle construction is cheap (no I/O beyond mkdir),
    so the cache mostly saves the IntegrationsStore reload cost.
    """
    if not tenant_id or "/" in tenant_id or ".." in tenant_id:
        raise ValueError(f"invalid tenant_id {tenant_id!r}")

    home = cloud_home() / "tenants" / tenant_id
    home.mkdir(parents=True, exist_ok=True)

    blackboard_root = home / "runs"
    blackboard_root.mkdir(parents=True, exist_ok=True)

    integrations_dir = home / "integrations"
    integrations_dir.mkdir(parents=True, exist_ok=True)

    agents_dir = home / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    # plnt's IntegrationsStore takes a `path=` kwarg pointing at the TOML file.
    from plnt.surface.integrations import IntegrationsStore
    integrations = IntegrationsStore(path=integrations_dir / "integrations.toml")

    # Memori (or stub) per tenant. Lazy import so a missing memorisdk install
    # doesn't break import of this module.
    from memory.memori_adapter import memori_for
    memori = memori_for(tenant_id, home=home)

    return TenantBundle(
        tenant_id=tenant_id,
        home=home,
        blackboard_root=blackboard_root,
        integrations=integrations,
        memori=memori,
        skills_dir=microagents_skills_dir(),
        agents_dir=agents_dir,
    )


def clear_cache() -> None:
    """Drop the cached bundles. Used in tests; never in production code paths."""
    for_tenant.cache_clear()
