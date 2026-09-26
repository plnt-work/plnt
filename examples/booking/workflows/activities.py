"""Temporal Activities — the boundary between deterministic Workflow code
and the actual micro-agent invocation.

`run_microagent` loads a skill bundle, builds the inputs, and dispatches to
`microagents.agent_loop.run_skill` — the Gemini-native function-calling loop.
There is no post-hoc grounding here anymore: the model calls real tools
(places_text_search, bookings_upsert, bookings_cancel, notify_send) during
its own loop, and tool results feed back into its context the way
Anthropic/OpenAI/Google agent docs prescribe.

`notify_booking` is a thin Activity that calls the `notify_send` tool
directly (no LLM). The saga's `notify_booking` step exists so Temporal
retries/timeouts apply at the right granularity even though no model is
involved in this step.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

from temporalio import activity

from memory.preload import remember_turn
from microagents.agent_loop import run_skill
from microagents.loader import load_skill
from microagents.tools import dispatch as dispatch_tool
from tenancy.audit import write_event as audit_write
from tenancy.context import TenantContext, set_current_tenant, reset_current_tenant
from tenancy.factory import for_tenant


# ─────────────────────────────────────────────────────────── DTOs


@dataclass
class MicroagentRequest:
    tenant_id: str
    user_id: str
    session_id: str
    role: str
    inputs: dict[str, Any] = field(default_factory=dict)
    # Optional override of which LLM backend to use. Currently ignored by the
    # cloud agent loop (always calls Gemini); kept on the request so the
    # stub_activities path stays signature-compatible.
    force_backend: str | None = None


@dataclass
class MicroagentResult:
    role: str
    output: dict[str, Any]
    steps: int = 0
    error: str | None = None


# ─────────────────────────────────────────────────────────── activities


@activity.defn(name="run_microagent")
async def run_microagent(req_dict: dict[str, Any]) -> dict[str, Any]:
    """Run one micro-agent to completion. Returns a MicroagentResult dict.

    Takes/returns dicts (not dataclasses) so Temporal's default JSON
    converter doesn't require custom type registration.
    """
    req = MicroagentRequest(**req_dict)

    bundle = for_tenant(req.tenant_id)

    try:
        skill = load_skill(req.role, tenant_id=req.tenant_id)
    except FileNotFoundError as e:
        result = asdict(MicroagentResult(role=req.role, output={}, error=str(e)))
        audit_write(
            tenant_id=req.tenant_id, session_id=req.session_id, user_id=req.user_id,
            role=req.role, status="error", has_output=False, detail=str(e),
        )
        return result

    inputs = dict(req.inputs)
    if req.role == "enquiry-generic" and "doc_context" not in inputs:
        # Retrieval lives here (activity side) — workflow code can't touch
        # the filesystem. Keyword overlap over the tenant's doc chunks.
        from services.doc_chunk import top_chunks
        inputs["doc_context"] = top_chunks(
            req.tenant_id, str(inputs.get("question") or ""), k=3,
        )

    ctx = TenantContext(req.tenant_id, req.user_id, req.session_id)
    token = set_current_tenant(ctx)
    try:
        loop_result = run_skill(
            skill,
            ctx=ctx,
            inputs=inputs,
            memori=bundle.memori,
        )

        if loop_result.error:
            activity.logger.warning(
                "skill %s failed: %s", req.role, loop_result.error,
            )
            audit_write(
                tenant_id=req.tenant_id, session_id=req.session_id, user_id=req.user_id,
                role=req.role, status="error", has_output=bool(loop_result.output),
                detail=loop_result.error,
            )
        else:
            # Persist the turn back to Memori so the next call for this
            # (user, role) can recall it.
            if loop_result.output:
                remember_turn(
                    bundle.memori, ctx,
                    role=req.role, turn_role="assistant",
                    content=json.dumps(loop_result.output, default=str),
                )
            audit_write(
                tenant_id=req.tenant_id, session_id=req.session_id, user_id=req.user_id,
                role=req.role, status="ok", has_output=bool(loop_result.output),
            )

        return asdict(MicroagentResult(
            role=req.role,
            output=loop_result.output,
            steps=loop_result.steps,
            error=loop_result.error,
        ))
    finally:
        reset_current_tenant(token)


@activity.defn(name="notify_booking")
async def notify_booking(req_dict: dict[str, Any]) -> dict[str, Any]:
    """Saga step — dispatches the `notify_send` tool directly (no LLM).

    The tool always writes the tenant's dashboard feed and raises when that
    write fails — that exception is what triggers saga compensation. Email
    (Resend) and Expo push are best-effort inside the tool and never raise.
    """
    tenant_id = str(req_dict.get("tenant_id") or "")
    user_id = str(req_dict.get("user_id") or "")
    session_id = str(req_dict.get("session_id") or "")
    booking_id = str(req_dict.get("booking_id") or "")
    ctx = TenantContext(tenant_id, user_id, session_id)
    result = dispatch_tool("notify_send", ctx, {
        "booking_id": booking_id,
        "kind": str(req_dict.get("kind") or "booking_confirmed"),
        "channel": str(req_dict.get("channel") or "push"),
        "message": str(req_dict.get("message") or ""),
        "status_label": str(req_dict.get("status_label") or "confirmed"),
        "business_name": str(req_dict.get("business_name") or ""),
        "slot": str(req_dict.get("slot") or ""),
        "party_size": req_dict.get("party_size"),
        "user_contact": str(req_dict.get("user_contact") or ""),
    })
    activity.logger.info(
        "notify_booking: tenant=%s session=%s booking_id=%s sent=%s channel=%s",
        tenant_id, session_id, booking_id,
        bool(result.get("sent")), result.get("channel"),
    )
    return {
        **result,
        "sent": bool(result.get("sent", False)),
        "channel": str(result.get("channel") or "unknown"),
    }


# ─────────────────────────────────────────────────────────── orders (multi-service)


@activity.defn(name="create_order")
async def create_order(req_dict: dict[str, Any]) -> dict[str, Any]:
    """Multi-service order create — idempotency-keyed.

    When `provider != "local"` the adapter is invoked first; the local
    ledger row records the provider outcome (provider_ref = reservation id
    on confirmed, URL on deeplink, empty on fallback).
    """
    from services.orders_store import orders_for, order_to_dict
    from providers.registry import get_provider

    tenant_id = str(req_dict.get("tenant_id") or "")
    user_id = str(req_dict.get("user_id") or "")
    session_id = str(req_dict.get("session_id") or "")
    place_id = str(req_dict.get("place_id") or "")
    venue_name = str(req_dict.get("venue_name") or "")
    date = str(req_dict.get("date") or "")
    slot = str(req_dict.get("slot") or "")
    pro_id = str(req_dict.get("pro_id") or "")
    services_list = list(req_dict.get("services") or [])
    idempotency_key = str(req_dict.get("idempotency_key") or "")
    provider_name = str(req_dict.get("provider") or "local")
    user_contact = str(req_dict.get("user_contact") or "")

    if not (tenant_id and user_id and place_id and date and slot and idempotency_key):
        raise ValueError("create_order: missing required fields")
    if not services_list:
        raise ValueError("create_order: services must be non-empty")

    provider_ref = ""
    provider_kind = ""
    if provider_name and provider_name != "local":
        adapter = get_provider(provider_name)
        if adapter is not None:
            slot_iso = f"{date}T{slot}" if "T" not in slot else slot
            pr = adapter.book(
                provider_id=place_id,
                slot=slot_iso,
                user_contact=user_contact,
                idempotency_key=idempotency_key,
            )
            provider_kind = pr.kind
            if pr.kind in ("confirmed", "deeplink"):
                provider_ref = pr.provider_ref
            # "failed" / "unsupported" → fall through to local ledger

    order = orders_for(tenant_id).create_order(
        tenant_id=tenant_id,
        user_id=user_id,
        place_id=place_id,
        venue_name=venue_name,
        date=date,
        slot=slot,
        pro_id=pro_id,
        services=services_list,
        idempotency_key=idempotency_key,
        provider=provider_name,
        provider_ref=provider_ref,
    )
    audit_write(
        tenant_id=tenant_id, session_id=session_id, user_id=user_id,
        role="create_order", status="ok", has_output=True,
        detail=f"order_id={order.order_id} provider={provider_name} kind={provider_kind}",
    )
    return {
        "order": order_to_dict(order),
        "provider_kind": provider_kind,
        "provider_ref": provider_ref,
    }


@activity.defn(name="cancel_order")
async def cancel_order(req_dict: dict[str, Any]) -> dict[str, Any]:
    """Multi-service order cancel — idempotent.

    Fans out to the provider adapter's `cancel()` when the order was
    booked through a non-local provider AND we hold a provider_ref.
    """
    from services.orders_store import orders_for
    from providers.registry import get_provider

    tenant_id = str(req_dict.get("tenant_id") or "")
    user_id = str(req_dict.get("user_id") or "")
    session_id = str(req_dict.get("session_id") or "")
    order_id = str(req_dict.get("order_id") or "")
    reason = str(req_dict.get("reason") or "")

    if not (tenant_id and order_id):
        raise ValueError("cancel_order: missing required fields")

    store = orders_for(tenant_id)
    order = store.get_order(order_id)

    provider_status = ""
    if order and order.provider and order.provider != "local" and order.provider_ref:
        adapter = get_provider(order.provider)
        if adapter is not None:
            can_cancel = getattr(adapter, "can_book_directly", lambda: False)()
            if can_cancel:
                pr = adapter.cancel(provider_ref=order.provider_ref, reason=reason)
                provider_status = pr.kind

    status = store.cancel(order_id, reason)
    audit_write(
        tenant_id=tenant_id, session_id=session_id, user_id=user_id,
        role="cancel_order", status="ok", has_output=True,
        detail=f"order_id={order_id} status={status} provider_status={provider_status}",
    )
    return {
        "order_id": order_id,
        "status": status,
        "provider_status": provider_status,
    }
