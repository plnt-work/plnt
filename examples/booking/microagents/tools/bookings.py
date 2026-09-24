"""bookings_upsert / bookings_cancel — BookingsStore behind real tool calls.

Replaces the `_ground_create_booking` / `_ground_cancel_booking` post-hoc
overlays. The model decides when to call these; the deterministic SHA1
booking_id derivation and per-tenant idempotency guarantees stay in
BookingsStore, just no longer retrofitted onto invented model output.
"""
from __future__ import annotations

from typing import Any

from tenancy.context import TenantContext

from microagents.tools import Tool, register

# NOTE: `workflows.bookings_store` and `workflows.saga_booking` are imported
# lazily inside the tool bodies. Importing them at module top creates a
# cycle: `workflows/__init__.py` re-exports `workflows.activities`, which
# imports `microagents.agent_loop`, which imports this module via the
# tool registry's side-effect import.


_UPSERT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "idempotency_key": {
            "type": "string",
            "description": (
                "Caller-supplied key — same key returns the same booking_id "
                "across retries. The orchestrator supplies it; pass through."
            ),
        },
        "business_id": {"type": "string", "description": "Business identifier (Place ID or internal id)."},
        "slot": {"type": "string", "description": "ISO 8601 slot datetime, e.g. 2026-06-22T19:00:00."},
        "user_contact": {"type": "string", "description": "Phone or email to attach to the booking."},
    },
    "required": ["idempotency_key", "business_id", "slot"],
}


def _bookings_upsert(
    ctx: TenantContext,
    *,
    idempotency_key: str,
    business_id: str,
    slot: str,
    user_contact: str = "",
) -> dict[str, Any]:
    """Tool body. Returns {booking_id, status, was_new}.

    booking_id is `bk_<sha1(idempotency_key)[:12]>` — deterministic, so a
    retry hits the same row in the per-tenant BookingsStore.
    """
    from workflows.bookings_store import bookings_for
    from workflows.saga_booking import deterministic_booking_id

    booking_id = deterministic_booking_id(idempotency_key)
    store = bookings_for(ctx.tenant_id)
    bid, was_new = store.upsert_confirmed(
        idempotency_key=idempotency_key,
        booking_id=booking_id,
        business_id=business_id,
        slot=slot,
        user_contact=user_contact,
    )
    return {
        "booking_id": bid,
        "status": "confirmed",
        "was_new": was_new,
    }


_CANCEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "booking_id": {"type": "string", "description": "Booking id returned by create_booking."},
        "reason": {"type": "string", "description": "Free-text cancellation reason."},
    },
    "required": ["booking_id"],
}


def _bookings_cancel(
    ctx: TenantContext, *, booking_id: str, reason: str = "",
) -> dict[str, Any]:
    """Tool body. Returns {booking_id, status} where status is one of
    'cancelled' | 'already_cancelled' | 'not_found'. Idempotent.
    """
    from workflows.bookings_store import bookings_for

    status = bookings_for(ctx.tenant_id).cancel(booking_id, reason)
    return {"booking_id": booking_id, "status": status}


register(Tool(
    name="bookings_upsert",
    description=(
        "Persist a confirmed booking to the per-tenant store. The idempotency_key "
        "guarantees retries are no-ops. Returns the canonical booking_id (deterministic "
        "from the key). Always call this rather than inventing a booking_id."
    ),
    schema=_UPSERT_SCHEMA,
    fn=_bookings_upsert,
))

register(Tool(
    name="bookings_cancel",
    description=(
        "Cancel a previously created booking. Safe to call repeatedly — returns "
        "status='already_cancelled' the second time, 'not_found' for unknown ids."
    ),
    schema=_CANCEL_SCHEMA,
    fn=_bookings_cancel,
))
