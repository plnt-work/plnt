"""Slice-2 booking-saga tests.

Two flows:
  1. **Happy path**: classify(book) → resolve → check_availability → confirm
     → saga(create_booking → notify) → booking row marked confirmed
  2. **Compensation path**: same prefix, but force_fail_step="notify" makes
     the notify activity raise. The saga compensates by calling cancel_booking;
     booking row ends up cancelled.

Uses Temporal's WorkflowEnvironment.start_local() — real Temporal dev-server
in-process. No Docker, no Ollama (stub activities supply canned data).
"""
from __future__ import annotations

import asyncio
import uuid

import pytest

from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows.session import ConversationWorkflow, SessionInput
from workflows.stub_activities import stub_run_microagent, stub_notify_booking


TASK_QUEUE = "plnt-cloud-saga-test"


@pytest.fixture
async def env() -> WorkflowEnvironment:
    async with await WorkflowEnvironment.start_local() as e:
        yield e


async def _drive_until_role(handle, role: str, timeout_s: float = 10.0) -> list[dict]:
    """Poll the workflow until a reply with `role` appears; return all replies.

    The workflow also pushes user-echo and interim `system` bubbles, so tests
    must select by role rather than by reply count/position.
    """
    deadline = asyncio.get_event_loop().time() + timeout_s
    replies: list[dict] = []
    while asyncio.get_event_loop().time() < deadline:
        replies = await handle.query("replies_since", 0)
        if any(r["role"] == role for r in replies):
            return replies
        await asyncio.sleep(0.1)
    return replies


def _trace_roles(replies: list[dict]) -> list[str]:
    skip = {"user", "system", "say"}
    return [r["role"] for r in replies if r["role"] not in skip]


async def test_saga_happy_path(env: WorkflowEnvironment, tmp_path, monkeypatch) -> None:
    """Book → check → confirm → saga commits. Booking ends up confirmed."""
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    monkeypatch.setenv("PLNT_CLOUD_MEMORY_BACKEND", "stub")

    # Clear caches so the new PLNT_CLOUD_HOME takes effect.
    from tenancy import factory as tf
    from memory import memori_adapter as ma
    from workflows import bookings_store as bs
    tf.clear_cache(); ma.clear_cache(); bs.clear_cache()

    wf_id = f"saga-happy-{uuid.uuid4().hex[:8]}"
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[ConversationWorkflow],
        activities=[stub_run_microagent, stub_notify_booking],
    ):
        handle = await env.client.start_workflow(
            ConversationWorkflow.run,
            SessionInput(
                tenant_id="saga-demo",
                user_id="alice",
                session_id="s1",
                user_contact="alice@example.com",
            ),
            id=wf_id,
            task_queue=TASK_QUEUE,
        )

        # Step 1: ask for a booking — trace ends at check_availability.
        await handle.signal("user_message", "book a table at Joe's Pizza tomorrow at 7pm")
        first_round = await _drive_until_role(handle, "check_availability")
        assert _trace_roles(first_round) == [
            "classify_intent", "resolve_business", "check_availability",
        ]

        # Step 2: confirm → triggers the saga.
        await handle.signal("user_message", "yes book it")
        after_confirm = await _drive_until_role(handle, "booking_saga")

        saga = [r for r in after_confirm if r["role"] == "booking_saga"][-1]
        assert saga["content"]["status"] == "confirmed"
        assert str(saga["content"]["booking_id"]).startswith("bk_")

        await handle.signal("close")

    # Verify the booking row landed in the per-tenant store with status=confirmed.
    from workflows.bookings_store import bookings_for
    store = bookings_for("saga-demo")
    counts = store.count_by_status()
    assert counts.get("confirmed", 0) == 1
    assert counts.get("cancelled", 0) == 0


async def test_saga_compensation_on_notify_failure(env: WorkflowEnvironment, tmp_path, monkeypatch) -> None:
    """force_fail_step=notify → saga compensates, booking ends up cancelled."""
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    monkeypatch.setenv("PLNT_CLOUD_MEMORY_BACKEND", "stub")

    from tenancy import factory as tf
    from memory import memori_adapter as ma
    from workflows import bookings_store as bs
    tf.clear_cache(); ma.clear_cache(); bs.clear_cache()

    wf_id = f"saga-fail-{uuid.uuid4().hex[:8]}"
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[ConversationWorkflow],
        activities=[stub_run_microagent, stub_notify_booking],
    ):
        handle = await env.client.start_workflow(
            ConversationWorkflow.run,
            SessionInput(
                tenant_id="saga-fail",
                user_id="bob",
                session_id="s2",
                force_fail_step="notify",
            ),
            id=wf_id,
            task_queue=TASK_QUEUE,
        )

        await handle.signal("user_message", "book a table at Mario's tomorrow at 8pm")
        await _drive_until_role(handle, "check_availability")

        await handle.signal("user_message", "yes")
        after_confirm = await _drive_until_role(handle, "booking_saga")

        saga = [r for r in after_confirm if r["role"] == "booking_saga"][-1]
        assert saga["content"]["status"] == "compensated", (
            f"expected compensated, got {saga['content']}"
        )
        booking_id = saga["content"]["booking_id"]
        assert booking_id and booking_id.startswith("bk_")

        await handle.signal("close")

    from workflows.bookings_store import bookings_for
    store = bookings_for("saga-fail")
    booking = store.get(booking_id)
    assert booking is not None
    assert booking.status == "cancelled"
    assert booking.cancel_reason and "notify" in booking.cancel_reason


async def test_booking_idempotency_in_store(tmp_path, monkeypatch) -> None:
    """Pure store test — same idempotency_key returns same booking_id."""
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))

    from tenancy import factory as tf
    from workflows import bookings_store as bs
    tf.clear_cache(); bs.clear_cache()

    store = bs.bookings_for("idem-demo")
    bid1, was_new1 = store.upsert_confirmed(
        idempotency_key="sess1:biz_a:slot1",
        booking_id="bk_abc123",
        business_id="biz_a", slot="slot1", user_contact="x",
    )
    bid2, was_new2 = store.upsert_confirmed(
        idempotency_key="sess1:biz_a:slot1",
        booking_id="bk_DIFFERENT",   # caller's would-be new id ignored
        business_id="biz_a", slot="slot1", user_contact="x",
    )
    assert (bid1, was_new1) == ("bk_abc123", True)
    assert (bid2, was_new2) == ("bk_abc123", False)


async def test_cancel_is_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))

    from tenancy import factory as tf
    from workflows import bookings_store as bs
    tf.clear_cache(); bs.clear_cache()

    store = bs.bookings_for("cancel-demo")
    store.upsert_confirmed(
        idempotency_key="k", booking_id="bk_x",
        business_id="b", slot="s", user_contact="u",
    )
    assert store.cancel("bk_x", "first") == "cancelled"
    assert store.cancel("bk_x", "second") == "already_cancelled"
    assert store.cancel("bk_missing", "third") == "not_found"
