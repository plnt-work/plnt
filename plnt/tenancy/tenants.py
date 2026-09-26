"""Tenants: identity, API keys, secrets, model choice, audit log.

On-disk layout (everything a tenant owns is under one directory, so
isolation is a path check and deleting a tenant is one `rm -rf`):

    $PLNT_HOME/tenants/<tid>/
      tenant.json        id, name, created_at, api_key_hash (sha256; plaintext never stored)
      secrets.json       name -> value, mode 0600; write-only over the API
      model.json         optional per-tenant model profile (bring your own model)
      bundles/           installed bundles (plnt.tenancy.installs)
      audit.jsonl        append-only audit log
      data.db            sessions, events, usage (plnt.tenancy.db)
      work/<session>/    workdir for filesystem tools
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets as _secrets
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plnt.config import paths
from plnt.models.profiles import ModelProfile, local_profile, resolve_profile

_TID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_SECRET_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_AUDIT_LOCK = threading.Lock()


class TenantError(ValueError):
    pass


class TenantNotFound(KeyError):  # noqa: N818
    pass


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _write_json(path: Path, data: Any, mode: int | None = None) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    if mode is not None:
        os.chmod(tmp, mode)
    tmp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


@dataclass(frozen=True)
class Tenant:
    id: str
    home: Path

    # ------------------------------------------------------------ metadata

    @property
    def meta(self) -> dict[str, Any]:
        return _read_json(self.home / "tenant.json", {})

    @property
    def name(self) -> str:
        return str(self.meta.get("name") or self.id)

    def summary(self) -> dict[str, Any]:
        m = self.meta
        return {"id": self.id, "name": self.name, "created_at": m.get("created_at")}

    def verify_key(self, presented: str) -> bool:
        expected = str(self.meta.get("api_key_hash") or "")
        return bool(expected) and _secrets.compare_digest(_hash_key(presented), expected)

    def rotate_key(self) -> str:
        key = "pk_" + _secrets.token_urlsafe(32)
        meta = self.meta
        meta["api_key_hash"] = _hash_key(key)
        _write_json(self.home / "tenant.json", meta)
        return key

    # ------------------------------------------------------------ secrets

    def _secrets(self) -> dict[str, str]:
        return _read_json(self.home / "secrets.json", {})

    def set_secret(self, name: str, value: str) -> None:
        if not _SECRET_NAME_RE.match(name):
            raise TenantError(f"secret name {name!r} must be UPPER_SNAKE_CASE")
        data = self._secrets()
        data[name] = value
        _write_json(self.home / "secrets.json", data, mode=0o600)

    def delete_secret(self, name: str) -> bool:
        data = self._secrets()
        existed = data.pop(name, None) is not None
        _write_json(self.home / "secrets.json", data, mode=0o600)
        return existed

    def secret_names(self) -> list[str]:
        return sorted(self._secrets())

    def secret_values(self) -> dict[str, str]:
        """Plaintext values — only for injecting into this tenant's tool calls."""
        return self._secrets()

    # ------------------------------------------------------------ model

    def model_config(self) -> dict[str, Any] | None:
        return _read_json(self.home / "model.json", None)

    def set_model_config(self, cfg: dict[str, Any] | None) -> None:
        path = self.home / "model.json"
        if cfg is None:
            path.unlink(missing_ok=True)
            return
        allowed = {
            "provider",
            "base_url",
            "model",
            "deep_model",
            "api_key_secret",
            "num_ctx",
            "temperature",
            "max_tokens",
            "timeout",
            "native_tools",
            "cost_in_per_m",
            "cost_out_per_m",
        }
        extra = sorted(set(cfg) - allowed)
        if extra:
            raise TenantError(f"unknown model settings {extra}; allowed: {sorted(allowed)}")
        if cfg.get("provider") not in ("ollama", "openai"):
            raise TenantError("model.provider must be 'ollama' or 'openai'")
        if not cfg.get("base_url") or not cfg.get("model"):
            raise TenantError("model.base_url and model.model are required")
        _write_json(path, cfg)

    def model_profile(self, hint: str = "auto") -> ModelProfile:
        """This tenant's model if configured, else the server default."""
        cfg = self.model_config()
        if not cfg:
            return resolve_profile(hint)  # type: ignore[arg-type]
        key = ""
        if cfg.get("api_key_secret"):
            key = self._secrets().get(cfg["api_key_secret"], "")
            if not key:
                raise TenantError(
                    f"model.api_key_secret {cfg['api_key_secret']!r} is not set "
                    f"for tenant {self.id}"
                )
        model = cfg.get("deep_model") if hint == "deep" and cfg.get("deep_model") else cfg["model"]
        base = local_profile()  # env defaults for fields the tenant did not set
        return ModelProfile(
            provider=cfg["provider"],
            base_url=cfg["base_url"],
            model=model,
            api_key=key,
            temperature=float(cfg.get("temperature", base.temperature)),
            max_tokens=int(cfg.get("max_tokens", base.max_tokens)),
            num_ctx=int(cfg.get("num_ctx", base.num_ctx)),
            timeout=float(cfg.get("timeout", base.timeout)),
            native_tools=cfg.get("native_tools", base.native_tools),
            cost_in_per_m=float(cfg.get("cost_in_per_m", 0.0)),
            cost_out_per_m=float(cfg.get("cost_out_per_m", 0.0)),
            source="tenant",
            reason=f"tenant {self.id} model.json",
        )

    # ------------------------------------------------------------ audit

    def audit(self, action: str, **fields: Any) -> None:
        evt = {"ts": time.time(), "action": action, **fields}
        line = json.dumps(evt, default=str) + "\n"
        with _AUDIT_LOCK, (self.home / "audit.jsonl").open("a", encoding="utf-8") as f:
            f.write(line)

    def audit_events(self, limit: int = 200, action: str | None = None) -> list[dict[str, Any]]:
        path = self.home / "audit.jsonl"
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if action is None or evt.get("action") == action:
                out.append(evt)
        return out[-limit:]

    # ------------------------------------------------------------ dirs

    @property
    def bundles_dir(self) -> Path:
        return self.home / "bundles"

    def workdir(self, session_id: str) -> Path:
        d = self.home / "work" / session_id
        d.mkdir(parents=True, exist_ok=True)
        return d


class TenantStore:
    def __init__(self, root: Path | None = None):
        self.root = (root or paths().home / "tenants").expanduser()
        self.root.mkdir(parents=True, exist_ok=True)

    def _home(self, tid: str) -> Path:
        if not _TID_RE.match(tid or ""):
            raise TenantError(
                f"tenant id {tid!r} must be 2-63 chars of lowercase letters, digits and '-'"
            )
        return self.root / tid

    def create(self, tid: str, name: str = "") -> tuple[Tenant, str]:
        """Create a tenant. Returns (tenant, plaintext api key) — the key is shown once."""
        home = self._home(tid)
        if (home / "tenant.json").exists():
            raise TenantError(f"tenant {tid!r} already exists")
        for d in (home, home / "bundles", home / "work"):
            d.mkdir(parents=True, exist_ok=True)
        _write_json(
            home / "tenant.json", {"id": tid, "name": name or tid, "created_at": time.time()}
        )
        t = Tenant(tid, home)
        key = t.rotate_key()
        t.audit("tenant.created", name=name or tid)
        return t, key

    def get(self, tid: str) -> Tenant:
        home = self._home(tid)
        if not (home / "tenant.json").exists():
            raise TenantNotFound(tid)
        return Tenant(tid, home)

    def exists(self, tid: str) -> bool:
        try:
            return (self._home(tid) / "tenant.json").exists()
        except TenantError:
            return False

    def list(self) -> list[Tenant]:
        return [
            Tenant(p.name, p) for p in sorted(self.root.iterdir()) if (p / "tenant.json").exists()
        ]

    def delete(self, tid: str) -> None:
        home = self.get(tid).home
        shutil.rmtree(home)

    def find_by_key(self, presented: str) -> Tenant | None:
        """Resolve a tenant API key to its tenant (keys are unique per tenant)."""
        for t in self.list():
            if t.verify_key(presented):
                return t
        return None
