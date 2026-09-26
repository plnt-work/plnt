"""TenantContext — the typed view over plnt's AgentSpec.inputs dict.

Per the design (see plan §3 "Tenant-context flow"), we intentionally do NOT
extend AgentSpec with explicit tenant fields. Tenant data lives in the open
`inputs` dict so plnt itself stays unchanged. This module is the typed access
layer that gives compile-time safety where we need it.

Reserved keys in spec.inputs (mirrors the IntegrationsStore reserved-list
extension): tenant_id, user_id, session_id, memory_context.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field, asdict
from typing import Any


# Reserved keys we own inside AgentSpec.inputs. Other keys are skill-specific
# inputs (e.g. business_query, date_range) and are NOT touched here.
TENANT_INPUT_KEYS = frozenset({"tenant_id", "user_id", "session_id", "memory_context"})


@dataclass(frozen=True)
class TenantContext:
    """Identifies the (tenant, user, session) triple for a single agent spawn.

    Memori scopes memory by (entity_id, process_id, session). We map:
        entity_id  = user_id
        process_id = micro-agent role
        session    = session_id
    So one Memori instance per tenant, addressed by (user_id, role) within it.
    """

    tenant_id: str
    user_id: str
    session_id: str
    memory_context: list[dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------ spec interop

    def to_inputs(self) -> dict[str, Any]:
        """Return the dict to merge into `AgentSpec.inputs`.

        Use: `spec.inputs.update(tenant_ctx.to_inputs())` before spawning.
        """
        d = asdict(self)
        # memory_context is potentially large — only include when populated.
        if not d.get("memory_context"):
            d.pop("memory_context", None)
        return d

    @classmethod
    def from_inputs(cls, inputs: dict[str, Any]) -> "TenantContext":
        """Build a TenantContext from spec.inputs. Raises KeyError if missing.

        Callers that should tolerate absent context (e.g. legacy single-user
        invocations) use `from_inputs_optional()` instead.
        """
        return cls(
            tenant_id=str(inputs["tenant_id"]),
            user_id=str(inputs["user_id"]),
            session_id=str(inputs["session_id"]),
            memory_context=list(inputs.get("memory_context") or []),
        )

    @classmethod
    def from_inputs_optional(cls, inputs: dict[str, Any]) -> "TenantContext | None":
        if not (inputs.get("tenant_id") and inputs.get("user_id") and inputs.get("session_id")):
            return None
        return cls.from_inputs(inputs)


# ------------------------------------------------------ current-tenant ContextVar

_CURRENT: ContextVar["TenantContext | None"] = ContextVar("plnt_cloud_current_tenant", default=None)


def current_tenant() -> "TenantContext | None":
    """Return the TenantContext bound to the current async / sync context.

    Used by code that needs to consult tenant identity without an explicit
    parameter — e.g. logging adapters, the recall tool. Returns None when
    no tenant has been bound.
    """
    return _CURRENT.get()


def set_current_tenant(ctx: "TenantContext | None") -> Any:
    """Bind a TenantContext to the current context; returns the token to reset."""
    return _CURRENT.set(ctx)


def reset_current_tenant(token: Any) -> None:
    _CURRENT.reset(token)
