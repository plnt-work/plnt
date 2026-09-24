"""Memory preload — called by the orchestrator before each micro-agent spawn.

Looks up recent memory for the (tenant, user, skill) tuple and stuffs the
results into `spec.inputs["memory_context"]`. The runner's `_wrap_user_message`
appends it to the user prompt downstream.

This is the default Memori binding (per the design's "hybrid" choice). Skills
that also want on-demand recall during their tool loop declare
`tools = ["search", "execute", "recall"]` in `skill.toml` and dispatch the
recall tool from the runner — that codepath is added in slice 2 (it needs
the `ALLOWED_TOOLS` extension that the plan defers).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plnt.execution.spec import AgentSpec
    from memory.memori_adapter import MemoriAdapter
    from tenancy.context import TenantContext


def preload_memory_into_inputs(
    spec: "AgentSpec",
    ctx: "TenantContext",
    memori: "MemoriAdapter",
    *,
    k: int = 5,
) -> "AgentSpec":
    """Mutate `spec.inputs["memory_context"]` in place with recent (user, role) memory.

    Returns the same spec for chaining. No-op when recall yields nothing.

    Why mutate in place: `AgentSpec` is Pydantic; constructing a new model
    triggers full revalidation on every spawn. Mutating the open `inputs`
    dict (whose schema is `dict[str, Any]`) skips that cost.
    """
    query = spec.inputs.get("intent") or spec.inputs.get("text") or ""
    if not isinstance(query, str):
        query = str(query)

    memories = memori.recall(user_id=ctx.user_id, role=spec.role, query=query, k=k)
    if memories:
        spec.inputs["memory_context"] = memories
    return spec


def remember_turn(
    memori: "MemoriAdapter",
    ctx: "TenantContext",
    *,
    role: str,
    turn_role: str,
    content: str,
) -> None:
    """Persist a single conversation turn to the tenant's Memori.

    `role` is the micro-agent role (process_id in Memori terms).
    `turn_role` is the conversation role: 'user' | 'assistant' | 'system'.
    """
    memori.remember(
        user_id=ctx.user_id,
        role=role,
        session_id=ctx.session_id,
        turn_role=turn_role,
        content=content,
    )
