"""Slice-1 end-to-end test.

Covers:
  1. ConversationWorkflow drives the three-skill happy path end-to-end:
        classify_intent  →  resolve_business  →  check_availability
     We mock `run_microagent` at the Activity boundary so the test runs
     without Ollama / external LLMs. The real Activity is exercised by
     plnt's own runner tests.
  2. Tenant isolation: two tenants writing to Memori in parallel see no
     cross-contamination on recall.

Uses Temporal's WorkflowEnvironment.start_local() — boots a real Temporal
dev-server in-process via the bundled temporal CLI. No Docker required.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows.session import ConversationWorkflow, SessionInput
from workflows.stub_activities import stub_run_microagent, stub_notify_booking


TASK_QUEUE = "plnt-cloud-test"


# ─────────────────────────────────────────────────────────── fixtures


@pytest.fixture
async def env() -> WorkflowEnvironment:
    """Boot a local Temporal server for the duration of the test."""
    async with await WorkflowEnvironment.start_local() as e:
        yield e


# ─────────────────────────────────────────────────────────── tests


async def test_book_flow_end_to_end(env: WorkflowEnvironment) -> None:
    """User sends a booking message; Workflow yields three replies."""
    client: Client = env.client
    wf_id = f"test-{uuid.uuid4().hex[:8]}"

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ConversationWorkflow],
        activities=[stub_run_microagent],
    ):
        handle = await client.start_workflow(
            ConversationWorkflow.run,
            SessionInput(
                tenant_id="demo",
                user_id="alice",
                session_id="sess1",
                force_backend="offline",
            ),
            id=wf_id,
            task_queue=TASK_QUEUE,
        )

        await handle.signal(
            "user_message",
            "find me an appointment at Joe's Pizza tomorrow at 7pm",
        )

        # Poll up to ~10s for the full turn (chain + synthesizer) to land.
        replies: list[dict[str, Any]] = []
        for _ in range(100):
            replies = await handle.query("replies_since", 0)
            if any(r["role"] == "say" for r in replies):
                break
            await asyncio.sleep(0.1)

        roles = [r["role"] for r in replies]
        # The three chain steps must all appear, in order, alongside the
        # user echo + interim system bubbles + final synthesized `say`.
        chain = [r for r in roles if r in
                 ("classify_intent", "resolve_business", "check_availability")]
        assert chain == ["classify_intent", "resolve_business", "check_availability"], roles

        # check_availability produced non-empty slots.
        avail = next(r for r in replies if r["role"] == "check_availability")
        assert "slots" in avail["content"] and len(avail["content"]["slots"]) == 3

        # Workflow is still alive — sessions are long-lived.
        state = await handle.query("state")
        assert state["closed"] is False

        await handle.signal("close")


async def test_tenant_isolation_in_memory_layer(tmp_path, monkeypatch) -> None:
    """Two tenants writing to Memori in parallel see no cross-contamination.

    This is a pure-Python test of the per-tenant Memori adapter — no Temporal
    needed. Pairs with the Workflow test above to give us coverage on both
    halves of the isolation story (Workflow boundary + memory partition).
    """
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    monkeypatch.setenv("PLNT_CLOUD_MEMORY_BACKEND", "stub")

    # Re-import so the env vars take effect (factory and adapter cache on home).
    from memory import memori_adapter as ma
    from tenancy import factory as tf
    ma.clear_cache()
    tf.clear_cache()

    bundle_a = tf.for_tenant("acme")
    bundle_b = tf.for_tenant("globex")

    # Tenant A: alice talks to classify_intent.
    bundle_a.memori.remember(
        user_id="alice", role="classify_intent", session_id="s1",
        turn_role="user", content="book Joe's Pizza",
    )
    # Tenant B: same user_id, same role, different content.
    bundle_b.memori.remember(
        user_id="alice", role="classify_intent", session_id="s1",
        turn_role="user", content="DIFFERENT TENANT MESSAGE",
    )

    a_recall = bundle_a.memori.recall(user_id="alice", role="classify_intent")
    b_recall = bundle_b.memori.recall(user_id="alice", role="classify_intent")

    a_contents = {r["content"] for r in a_recall}
    b_contents = {r["content"] for r in b_recall}

    assert "book Joe's Pizza" in a_contents
    assert "DIFFERENT TENANT MESSAGE" not in a_contents, (
        "tenant A saw tenant B's writes — partition is broken"
    )
    assert "DIFFERENT TENANT MESSAGE" in b_contents
    assert "book Joe's Pizza" not in b_contents


async def test_memori_recall_returns_empty_when_no_history(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    monkeypatch.setenv("PLNT_CLOUD_MEMORY_BACKEND", "stub")

    from memory import memori_adapter as ma
    from tenancy import factory as tf
    ma.clear_cache()
    tf.clear_cache()

    bundle = tf.for_tenant("fresh-tenant")
    out = bundle.memori.recall(user_id="nobody", role="any_skill")
    assert out == []


# ─────────────────────────────────────────────────────────── slice-1 additions


def test_geolocation_parser_strips_and_returns_coords() -> None:
    from workflows.session import _extract_geolocation

    text, loc = _extract_geolocation("pizza near me [@18.55,73.85]")
    assert text == "pizza near me"
    assert loc == {"lat": 18.55, "lng": 73.85}

    text, loc = _extract_geolocation("plain message with no marker")
    assert text == "plain message with no marker"
    assert loc is None

    # Malformed marker → don't fail, just leave the text alone.
    text, loc = _extract_geolocation("weird [@notanumber,73.85]")
    assert loc is None


async def test_geolocation_parsed(env: WorkflowEnvironment) -> None:
    """WS message with a trailing "[@lat,lng]" tail must land as
    `user_location` in the resolve_business inputs."""
    client: Client = env.client
    wf_id = f"test-{uuid.uuid4().hex[:8]}"

    seen: list[dict[str, Any]] = []

    from temporalio import activity

    @activity.defn(name="run_microagent")
    async def capturing_run_microagent(req_dict: dict[str, Any]) -> dict[str, Any]:
        seen.append(req_dict)
        return await stub_run_microagent(req_dict)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ConversationWorkflow],
        activities=[capturing_run_microagent],
    ):
        handle = await client.start_workflow(
            ConversationWorkflow.run,
            SessionInput(tenant_id="demo", user_id="alice",
                         session_id=f"sess-{uuid.uuid4().hex[:6]}",
                         force_backend="offline"),
            id=wf_id, task_queue=TASK_QUEUE,
        )
        await handle.signal("user_message", "book Joe's Pizza tomorrow [@18.55,73.85]")

        for _ in range(100):
            replies = await handle.query("replies_since", 0)
            if any(r["role"] == "say" for r in replies):
                break
            await asyncio.sleep(0.1)
        await handle.signal("close")

    resolve_calls = [r for r in seen if r.get("role") == "resolve_business"]
    assert resolve_calls, "resolve_business was never invoked"
    loc = resolve_calls[0]["inputs"].get("user_location")
    assert loc == {"lat": 18.55, "lng": 73.85}
    # The stripped text should NOT carry the marker anymore.
    assert "[@" not in resolve_calls[0]["inputs"].get("user_text", "")


async def test_candidate_platform_set(env: WorkflowEnvironment) -> None:
    """Resolved candidates carry a `platform` tag so downstream dispatch fires."""
    client: Client = env.client
    wf_id = f"test-{uuid.uuid4().hex[:8]}"

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ConversationWorkflow],
        activities=[stub_run_microagent],
    ):
        handle = await client.start_workflow(
            ConversationWorkflow.run,
            SessionInput(tenant_id="demo", user_id="alice",
                         session_id=f"sess-{uuid.uuid4().hex[:6]}",
                         force_backend="offline"),
            id=wf_id, task_queue=TASK_QUEUE,
        )
        await handle.signal("user_message", "book Joe's Pizza tomorrow at 7pm")

        replies: list[dict[str, Any]] = []
        for _ in range(100):
            replies = await handle.query("replies_since", 0)
            if any(r["role"] == "say" for r in replies):
                break
            await asyncio.sleep(0.1)
        await handle.signal("close")

    resolve = next(r for r in replies if r["role"] == "resolve_business")
    cands = resolve["content"].get("candidates") or []
    assert cands, "expected at least one candidate"
    assert cands[0].get("platform") == "google"


def test_platform_to_provider_mapping() -> None:
    from workflows.session import provider_for_platform

    assert provider_for_platform("google") == "house_rules"
    assert provider_for_platform("resy") == "resy"
    assert provider_for_platform("") == "house_rules"


async def test_platform_plumbed_into_booking_provider(env: WorkflowEnvironment) -> None:
    """A resolve with platform="google" must land as provider="house_rules"
    on the create_booking activity input when the user confirms."""
    client: Client = env.client
    wf_id = f"test-{uuid.uuid4().hex[:8]}"

    seen: list[dict[str, Any]] = []

    from temporalio import activity

    @activity.defn(name="run_microagent")
    async def capturing_run_microagent(req_dict: dict[str, Any]) -> dict[str, Any]:
        seen.append(req_dict)
        return await stub_run_microagent(req_dict)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ConversationWorkflow],
        activities=[capturing_run_microagent, stub_notify_booking],
    ):
        handle = await client.start_workflow(
            ConversationWorkflow.run,
            SessionInput(tenant_id="demo", user_id="alice",
                         session_id=f"sess-{uuid.uuid4().hex[:6]}",
                         force_backend="offline"),
            id=wf_id, task_queue=TASK_QUEUE,
        )
        await handle.signal("user_message", "book Joe's Pizza tomorrow at 7pm")

        replies: list[dict[str, Any]] = []
        for _ in range(100):
            replies = await handle.query("replies_since", 0)
            if any(r["role"] == "say" for r in replies):
                break
            await asyncio.sleep(0.1)

        avail = next(r for r in replies if r["role"] == "check_availability")
        slot = avail["content"]["slots"][0]
        await handle.signal("user_message", f"yes book {slot}")

        for _ in range(100):
            replies = await handle.query("replies_since", 0)
            if any(r["role"] == "booking_saga" for r in replies):
                break
            await asyncio.sleep(0.1)
        await handle.signal("close")

    creates = [r for r in seen if r.get("role") == "create_booking"]
    assert creates, "create_booking was never invoked"
    assert creates[0]["inputs"].get("provider") == "house_rules"


def test_resy_deeplink(monkeypatch) -> None:
    """ResyAdapter.book() returns a deeplink whose URL encodes venue + date + seats."""
    from providers.resy import ResyAdapter

    # Un-configured adapter still returns a deeplink (universal fallback).
    monkeypatch.delenv("PLNT_CLOUD_RESY_KEY", raising=False)
    monkeypatch.delenv("PLNT_CLOUD_RESY_AUTH", raising=False)

    adapter = ResyAdapter()
    result = adapter.book(
        provider_id="12345", slot="2026-08-15T19:30:00",
        user_contact="alice@example.com", party_size=4,
    )
    assert result.kind == "deeplink"
    assert "12345" in result.provider_ref
    assert "2026-08-15" in result.provider_ref
    assert "seats=4" in result.provider_ref
    assert result.metadata.get("verified_at")
    assert result.metadata.get("venue_id") == "12345"


def test_house_rules_availability() -> None:
    from providers.house_rules import HouseRulesAdapter

    # 2026-08-15 is a Saturday; 2026-08-14 is a Friday.
    schedule = {
        "open_hours": {
            "fri": [["18:00", "21:00"]],
            "sat": [["11:00", "14:00"]],
        },
        "closed_dates": ["2026-08-15"],
        "turn_minutes": 60,
        "party_size_range": [1, 8],
    }
    adapter = HouseRulesAdapter(schedule=schedule)

    fri_slots = adapter.availability(provider_id="house", date_iso="2026-08-14", party_size=2)
    assert fri_slots == ["2026-08-14T18:00:00", "2026-08-14T19:00:00", "2026-08-14T20:00:00"]

    closed = adapter.availability(provider_id="house", date_iso="2026-08-15", party_size=2)
    assert closed == []

    too_big = adapter.availability(provider_id="house", date_iso="2026-08-14", party_size=99)
    assert too_big == []


def test_house_rules_book() -> None:
    from providers.house_rules import HouseRulesAdapter

    result = HouseRulesAdapter(schedule={"open_hours": {"mon": [["09:00", "17:00"]]}}).book(
        provider_id="house", slot="2026-08-17T10:00:00",
        user_contact="alice@example.com", party_size=2,
        idempotency_key="idem-42",
    )
    assert result.kind == "house_confirmed"
    assert result.provider == "house_rules"
    assert result.metadata.get("slot") == "2026-08-17T10:00:00"
    assert result.provider_ref == "idem-42"
