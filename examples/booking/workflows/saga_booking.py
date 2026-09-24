"""Booking saga — invoked by ConversationWorkflow when intent kind=confirm.

Implements the saga pattern:
  1. create_booking      (micro-agent, idempotency-keyed)
  2. notify_booking      (system Activity — could be SMS/email/push)
On any failure of step 2, the compensation runs:
  3. cancel_booking      (micro-agent, idempotent)

The saga is a deterministic async helper, not a Workflow itself — kept inline
in ConversationWorkflow's run context for slice 2 simplicity. A future
upgrade promotes it to a child Workflow when bookings span multiple sessions
or need their own audit/replay history.

Idempotency: the create_booking step receives `idempotency_key` derived from
(session_id, business_id, slot). Activity retries see the same key →
BookingsStore returns the existing booking_id, no duplicates.

Compensation: a try/except around the post-create steps. ApplicationError
escapes the saga; the parent workflow records it as a saga_failed reply so
the channel can surface the rollback to the user.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError


@dataclass
class SagaInput:
    tenant_id: str
    user_id: str
    session_id: str
    business_id: str
    slot: str
    user_contact: str
    provider: str = "house_rules"
    business_name: str = ""
    # Test hook: when set, the notify activity raises so compensation runs.
    force_fail_step: str | None = None
    force_backend: str | None = None


@dataclass
class SagaResult:
    booking_id: str | None
    status: str         # confirmed | compensated | failed
    note: str = ""


def idempotency_key(session_id: str, business_id: str, slot: str) -> str:
    """Stable derivation. Activity retries hit the same row in BookingsStore."""
    return f"{session_id}:{business_id}:{slot}"


def _booking_request(s: SagaInput) -> dict[str, Any]:
    key = idempotency_key(s.session_id, s.business_id, s.slot)
    return {
        "tenant_id": s.tenant_id,
        "user_id": s.user_id,
        "session_id": s.session_id,
        "role": "create_booking",
        "inputs": {
            "business_id": s.business_id,
            "slot": s.slot,
            "user_contact": s.user_contact,
            "idempotency_key": key,
            "provider": s.provider,
        },
        "force_backend": s.force_backend,
    }


def _cancel_request(s: SagaInput, booking_id: str, reason: str) -> dict[str, Any]:
    return {
        "tenant_id": s.tenant_id,
        "user_id": s.user_id,
        "session_id": s.session_id,
        "role": "cancel_booking",
        "inputs": {"booking_id": booking_id, "reason": reason},
        "force_backend": s.force_backend,
    }


def _notify_request(
    s: SagaInput, booking_id: str, kind: str = "booking_confirmed",
) -> dict[str, Any]:
    return {
        "tenant_id": s.tenant_id,
        "user_id": s.user_id,
        "session_id": s.session_id,
        "booking_id": booking_id,
        "kind": kind,
        "status_label": "cancelled" if kind == "booking_compensated" else "confirmed",
        "business_name": s.business_name,
        "slot": s.slot,
        "user_contact": s.user_contact,
        "force_fail": kind == "booking_confirmed" and s.force_fail_step == "notify",
    }


async def run_booking_saga(s: SagaInput) -> SagaResult:
    """Run the saga from inside a Temporal Workflow.

    Must be called from within a `@workflow.run` execution — uses
    `workflow.execute_activity`. Returns a SagaResult describing outcome.
    """
    retry = RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=3)

    # ─── step 1: create_booking ───
    create = await workflow.execute_activity(
        "run_microagent",
        args=[_booking_request(s)],
        start_to_close_timeout=timedelta(seconds=20),
        retry_policy=retry,
    )
    booking_output = create.get("output", {}) or {}
    booking_id = str(booking_output.get("booking_id") or "")
    if not booking_id:
        return SagaResult(
            booking_id=None, status="failed",
            note=f"create_booking returned no booking_id: {create.get('error') or 'unknown'}",
        )

    # ─── step 2: notify_booking (can fail → compensation) ───
    try:
        await workflow.execute_activity(
            "notify_booking",
            args=[_notify_request(s, booking_id)],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
    except ActivityError as e:
        # ─── compensation: cancel_booking ───
        try:
            await workflow.execute_activity(
                "run_microagent",
                args=[_cancel_request(
                    s, booking_id,
                    reason=f"compensation: notify failed ({type(e).__name__})",
                )],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=retry,
            )
        except ApplicationError:
            # Cancel itself failed — surface so a human can clean up.
            return SagaResult(
                booking_id=booking_id, status="failed",
                note="notify failed AND cancel failed — manual review required",
            )
        await _notify_compensated(_notify_request(s, booking_id, kind="booking_compensated"))
        return SagaResult(
            booking_id=booking_id, status="compensated",
            note=f"notify failed; booking {booking_id} cancelled",
        )

    return SagaResult(
        booking_id=booking_id, status="confirmed",
        note="booking confirmed and notified",
    )


async def _notify_compensated(req: dict[str, Any]) -> None:
    """Best-effort booking_compensated feed entry after a rollback.

    The saga already compensated; a second notify failure must not change
    its outcome, so ActivityError is swallowed here.
    """
    try:
        await workflow.execute_activity(
            "notify_booking",
            args=[req],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
    except ActivityError:
        pass


# ─────────────────────────────────────────────────────────── helpers


def deterministic_booking_id(idem_key: str) -> str:
    """Mirrors the create_booking stub's id derivation — used by the
    BookingsStore upsert path AND the cancel_booking compensation when it
    needs to recognise a booking by idempotency_key.
    """
    return "bk_" + hashlib.sha1(idem_key.encode()).hexdigest()[:12]


def deterministic_order_id(idem_key: str) -> str:
    """Same shape as `deterministic_booking_id`, but for the multi-service
    OrdersStore. Two keyspaces so a booking_id and an order_id never
    collide even when the input key does.
    """
    return "ord_" + hashlib.sha1(idem_key.encode()).hexdigest()[:12]


# ─────────────────────────────────────────────────────────── multi-service saga


@dataclass
class MultiSagaInput:
    tenant_id: str
    user_id: str
    session_id: str
    place_id: str
    venue_name: str
    date: str            # YYYY-MM-DD
    slot: str            # HH:mm
    pro_id: str
    services: list[dict]
    user_contact: str = ""
    provider: str = "local"
    force_fail_step: str | None = None


def _multi_idempotency_key(s: "MultiSagaInput") -> str:
    svc_ids = sorted(str(x.get("id") or "") for x in s.services)
    return f"{s.user_id}:{s.place_id}:{s.date}:{s.slot}:{','.join(svc_ids)}:{s.pro_id}"


def _multi_create_request(s: "MultiSagaInput", key: str) -> dict[str, Any]:
    return {
        "tenant_id": s.tenant_id,
        "user_id": s.user_id,
        "session_id": s.session_id,
        "place_id": s.place_id,
        "venue_name": s.venue_name,
        "date": s.date,
        "slot": s.slot,
        "pro_id": s.pro_id,
        "services": list(s.services),
        "user_contact": s.user_contact,
        "provider": s.provider,
        "idempotency_key": key,
    }


def _multi_cancel_request(s: "MultiSagaInput", order_id: str, reason: str) -> dict[str, Any]:
    return {
        "tenant_id": s.tenant_id,
        "user_id": s.user_id,
        "session_id": s.session_id,
        "order_id": order_id,
        "reason": reason,
    }


def _multi_notify_request(
    s: "MultiSagaInput", order_id: str, kind: str = "booking_confirmed",
) -> dict[str, Any]:
    verb = "cancelled" if kind == "booking_compensated" else "confirmed"
    return {
        "tenant_id": s.tenant_id,
        "user_id": s.user_id,
        "session_id": s.session_id,
        "booking_id": order_id,
        "kind": kind,
        "channel": "push",
        "status_label": verb,
        "business_name": s.venue_name,
        "slot": f"{s.date}T{s.slot}",
        "user_contact": s.user_contact,
        "message": f"Your booking at {s.venue_name} on {s.date} at {s.slot} is {verb}.",
        "force_fail": kind == "booking_confirmed" and s.force_fail_step == "notify",
    }


async def run_multi_service_saga(s: MultiSagaInput) -> SagaResult:
    """Multi-service order saga: create_order → notify_booking; on notify
    failure, compensate with cancel_order.
    """
    retry = RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=3)
    key = _multi_idempotency_key(s)

    # ─── step 1: create_order ───
    create = await workflow.execute_activity(
        "create_order",
        args=[_multi_create_request(s, key)],
        start_to_close_timeout=timedelta(seconds=20),
        retry_policy=retry,
    )
    order_dict = (create or {}).get("order", {}) or {}
    order_id = str(order_dict.get("order_id") or "")
    if not order_id:
        return SagaResult(
            booking_id=None, status="failed",
            note="create_order returned no order_id",
        )

    # ─── step 2: notify_booking ───
    try:
        await workflow.execute_activity(
            "notify_booking",
            args=[_multi_notify_request(s, order_id)],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
    except ActivityError as e:
        # ─── compensation: cancel_order ───
        try:
            await workflow.execute_activity(
                "cancel_order",
                args=[_multi_cancel_request(
                    s, order_id,
                    reason=f"compensation: notify failed ({type(e).__name__})",
                )],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=retry,
            )
        except ApplicationError:
            return SagaResult(
                booking_id=order_id, status="failed",
                note="notify failed AND cancel failed — manual review required",
            )
        await _notify_compensated(_multi_notify_request(s, order_id, kind="booking_compensated"))
        return SagaResult(
            booking_id=order_id, status="compensated",
            note=f"notify failed; order {order_id} cancelled",
        )

    return SagaResult(
        booking_id=order_id, status="confirmed",
        note="order confirmed and notified",
    )
