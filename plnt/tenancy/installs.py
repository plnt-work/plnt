"""Per-tenant bundle installs.

Installing copies the bundle into the tenant's directory, so a tenant keeps
running exactly what it installed even if the catalog copy changes:

    <tenant>/bundles/<slug>@<version>/        copy of the bundle
    <tenant>/bundles/<slug>@<version>/.install.json
        {slug, version, enabled, config, installed_at, source, digest}

Several versions may be present; the highest enabled one is active.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plnt.bundles.bundle import Bundle, BundleError, load_bundle, parse_version
from plnt.tenancy.tenants import Tenant

INSTALL_FILE = ".install.json"


@dataclass
class Installation:
    tenant_id: str
    slug: str
    version: str
    path: Path
    enabled: bool
    config: dict[str, Any]
    installed_at: float
    source: str
    digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "version": self.version,
            "enabled": self.enabled,
            "config": self.config,
            "installed_at": self.installed_at,
            "source": self.source,
            "digest": self.digest,
        }

    def load(self) -> Bundle:
        return load_bundle(self.path)


def _read(path: Path, tenant_id: str) -> Installation | None:
    try:
        meta = json.loads((path / INSTALL_FILE).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return Installation(
        tenant_id=tenant_id,
        slug=meta["slug"],
        version=meta["version"],
        path=path,
        enabled=bool(meta.get("enabled", True)),
        config=dict(meta.get("config") or {}),
        installed_at=float(meta.get("installed_at") or 0),
        source=str(meta.get("source") or ""),
        digest=str(meta.get("digest") or ""),
    )


def _write(inst: Installation) -> None:
    (inst.path / INSTALL_FILE).write_text(json.dumps(inst.to_dict(), indent=2), encoding="utf-8")


def install(tenant: Tenant, bundle: Bundle, config: dict[str, Any] | None = None) -> Installation:
    """Validate `config` against the bundle and install it for this tenant only."""
    effective = bundle.validate_config(config)
    dest = tenant.bundles_dir / f"{bundle.slug}@{bundle.version}"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        bundle.path, dest, ignore=shutil.ignore_patterns("__pycache__", ".install.json")
    )
    inst = Installation(
        tenant_id=tenant.id,
        slug=bundle.slug,
        version=bundle.version,
        path=dest,
        enabled=True,
        config=effective,
        installed_at=time.time(),
        source=str(bundle.path),
        digest=bundle.digest(),
    )
    _write(inst)
    tenant.audit("bundle.installed", bundle=bundle.slug, version=bundle.version, digest=inst.digest)
    return inst


def list_installed(tenant: Tenant) -> list[Installation]:
    if not tenant.bundles_dir.is_dir():
        return []
    rows = [
        i
        for d in sorted(tenant.bundles_dir.iterdir())
        if d.is_dir() and (i := _read(d, tenant.id)) is not None
    ]
    return rows


def active(tenant: Tenant, slug: str) -> Installation:
    """The highest enabled installed version of `slug`."""
    candidates = [i for i in list_installed(tenant) if i.slug == slug]
    if not candidates:
        raise BundleError(f"bundle {slug!r} is not installed for tenant {tenant.id!r}")
    enabled = [i for i in candidates if i.enabled]
    if not enabled:
        raise BundleError(f"bundle {slug!r} is disabled for tenant {tenant.id!r}")
    return max(enabled, key=lambda i: parse_version(i.version))


def update(
    tenant: Tenant, slug: str, *, enabled: bool | None = None, config: dict[str, Any] | None = None
) -> Installation:
    """Enable/disable, or replace the config (re-validated) of every installed version."""
    rows = [i for i in list_installed(tenant) if i.slug == slug]
    if not rows:
        raise BundleError(f"bundle {slug!r} is not installed for tenant {tenant.id!r}")
    for inst in rows:
        if config is not None:
            inst.config = inst.load().validate_config(config)
        if enabled is not None:
            inst.enabled = enabled
        _write(inst)
    tenant.audit("bundle.updated", bundle=slug, enabled=enabled, config_changed=config is not None)
    return max(rows, key=lambda i: parse_version(i.version))


def uninstall(tenant: Tenant, slug: str) -> None:
    rows = [i for i in list_installed(tenant) if i.slug == slug]
    if not rows:
        raise BundleError(f"bundle {slug!r} is not installed for tenant {tenant.id!r}")
    for inst in rows:
        shutil.rmtree(inst.path)
    tenant.audit("bundle.uninstalled", bundle=slug)
