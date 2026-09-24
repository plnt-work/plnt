"""MA-P1 tests: tool registry, tool dispatch, agent loop with mocked Gemini.

The agent loop normally posts to Gemini's OpenAI-compatible chat-completions
endpoint. These tests patch `microagents.agent_loop._post` so we can drive
the loop with canned responses — no LLM, no network.

What we verify:
  * Tool registry: all four MA-P1 tools registered with valid OpenAI specs.
  * Single-shot path: tools-less skill with response_schema produces a
    parsed dict.
  * Tool-call loop: model emits tool_calls, dispatcher routes to the right
    Python callable, tool result feeds back as a `tool` message, model
    terminates with a structured final.
  * Idempotency through the tool path: same idempotency_key → same
    booking_id, with was_new flipping on the second call.
  * Error propagation: a tool that raises shows up as an `error` in the
    tool_result the model sees (and in the loop transcript).
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from microagents.agent_loop import LoopResult, _build_initial_messages, run_skill
from microagents.loader import load_skill, clear_cache
from microagents import tools as tool_registry
from tenancy.context import TenantContext


# ─────────────────────────────────────────────────────────── helpers


def _ctx() -> TenantContext:
    return TenantContext(tenant_id="t-test", user_id="u-test", session_id="s-test")


def _final(content: str) -> dict[str, Any]:
    """Build a fake Gemini response where the model returned a final message."""
    return {"choices": [{"message": {"content": content, "tool_calls": None}}]}


def _tool_call(name: str, args: dict[str, Any], call_id: str = "c1") -> dict[str, Any]:
    """Build a fake Gemini response where the model wants to call one tool."""
    return {"choices": [{"message": {
        "content": "",
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)},
        }],
    }}]}


@pytest.fixture(autouse=True)
def _clear_skill_cache():
    """Pick up any in-test skill.toml mutations and avoid bleed between tests."""
    clear_cache()
    yield
    clear_cache()


# ─────────────────────────────────────────────────────────── tool registry


def test_all_ma_p1_tools_registered():
    names = tool_registry.all_names()
    assert "places_text_search" in names
    assert "bookings_upsert" in names
    assert "bookings_cancel" in names
    assert "notify_send" in names


def test_tool_openai_spec_shape():
    for name in ("places_text_search", "bookings_upsert", "bookings_cancel", "notify_send"):
        spec = tool_registry.get(name).openai_spec()
        assert spec["type"] == "function"
        fn = spec["function"]
        assert fn["name"] == name
        assert isinstance(fn["description"], str) and fn["description"]
        params = fn["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params


def test_tool_specs_for_subset_preserves_order():
    specs = tool_registry.specs_for(["bookings_cancel", "places_text_search"])
    assert [s["function"]["name"] for s in specs] == ["bookings_cancel", "places_text_search"]


def test_unknown_tool_raises():
    with pytest.raises(KeyError):
        tool_registry.get("does_not_exist")


# ─────────────────────────────────────────────────────────── single-shot


def test_classify_intent_single_shot(monkeypatch, tmp_path):
    """tools=[] + response_schema → one HTTP call, parse JSON."""
    monkeypatch.setenv("PLNT_CLOUD_URL", "https://example.invalid/v1beta/openai")
    monkeypatch.setenv("PLNT_CLOUD_API_KEY", "fake")

    canned = _final('{"kind": "book", "business_query": "Joe\'s Pizza", '
                    '"service": "table", "date_hint": "tomorrow at 7pm"}')

    captured: dict[str, Any] = {}

    def fake_post(**kwargs):
        captured.update(kwargs)
        return canned

    monkeypatch.setattr("microagents.agent_loop._post", fake_post)

    skill = load_skill("classify_intent")
    result = run_skill(
        skill,
        ctx=_ctx(),
        inputs={"text": "book a table at Joe's tomorrow at 7pm"},
        memori=None,
    )
    assert result.error is None
    assert result.steps == 1
    assert result.output["kind"] == "book"
    # tools-less skill with schema → response_format wired up.
    assert captured.get("tools") is None
    rf = captured.get("response_format")
    assert rf and rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "classify_intent"


# ─────────────────────────────────────────────────────────── tool loop


def test_tool_call_loop_dispatches_and_feeds_back(monkeypatch):
    """resolve_business: model calls places_text_search, gets disabled=true (no key
    in this test), then emits a final answer using LLM fallback. Loop must:
      - post once → tool_call
      - dispatch places_text_search
      - append a `tool` message carrying the JSON result
      - post again → final
    """
    monkeypatch.setenv("PLNT_CLOUD_URL", "https://example.invalid/v1beta/openai")
    monkeypatch.setenv("PLNT_CLOUD_API_KEY", "fake")
    monkeypatch.delenv("PLNT_CLOUD_PLACES_KEY", raising=False)
    # places_svc reads PLNT_CLOUD_API_KEY too; force "disabled" by clearing both.
    monkeypatch.setenv("PLNT_CLOUD_API_KEY", "")
    monkeypatch.setenv("PLNT_CLOUD_API_KEY", "fake")
    # Force places_svc to report disabled regardless of the gemini key.
    monkeypatch.setattr("services.places.is_enabled", lambda: False)

    calls: list[dict[str, Any]] = []

    def fake_post(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _tool_call("places_text_search", {"query": "pizza in mumbai"})
        # Second call: the model emits its final structured answer.
        return _final(json.dumps({
            "candidates": [{"name": "Joey's Pizza", "neighborhood": "Bandra"}],
            "best_match": {"name": "Joey's Pizza", "neighborhood": "Bandra"},
            "confidence": 0.7,
            "needs_disambiguation": False,
            "source": "llm",
        }))

    monkeypatch.setattr("microagents.agent_loop._post", fake_post)

    skill = load_skill("resolve_business")
    result = run_skill(
        skill,
        ctx=_ctx(),
        inputs={"business_query": "pizza in mumbai", "user_text": "find me pizza in mumbai"},
        memori=None,
    )
    assert result.error is None
    assert len(calls) == 2
    # Loop transcript has the tool round.
    assert len(result.transcript) == 1
    assert result.transcript[0]["tool"] == "places_text_search"
    assert result.transcript[0]["result"]["enabled"] is False
    # Second call to Gemini must include the tool message in the conversation.
    second_msgs = calls[1]["messages"]
    assert any(m.get("role") == "tool" and m.get("name") == "places_text_search"
               for m in second_msgs)
    # Final output parsed.
    assert result.output["source"] == "llm"
    assert result.output["best_match"]["name"] == "Joey's Pizza"


def test_max_steps_bounded(monkeypatch):
    """Skill with max_steps=2 stuck in a tool loop returns an error after the cap."""
    monkeypatch.setenv("PLNT_CLOUD_URL", "https://example.invalid/v1beta/openai")
    monkeypatch.setenv("PLNT_CLOUD_API_KEY", "fake")
    monkeypatch.setattr("services.places.is_enabled", lambda: False)

    call_count = {"n": 0}

    def fake_post(**kwargs):
        call_count["n"] += 1
        return _tool_call("places_text_search", {"query": "q"}, call_id=f"c{call_count['n']}")

    monkeypatch.setattr("microagents.agent_loop._post", fake_post)

    skill = load_skill("cancel_booking")  # max_steps=2 in toml
    # Use cancel_booking's tool by name so dispatch works even though we
    # patched the model to always call places_text_search; the agent_loop
    # dispatches by name from the registry, not the skill's tool list.
    result = run_skill(
        skill,
        ctx=_ctx(),
        inputs={"booking_id": "bk_x", "reason": "test"},
        memori=None,
    )
    assert result.error is not None
    assert "max_steps" in result.error


# ─────────────────────────────────────────────────────────── idempotency via tool


def test_bookings_upsert_tool_is_deterministic_and_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    from tenancy import factory as tf
    from workflows import bookings_store as bs
    tf.clear_cache(); bs.clear_cache()

    ctx = TenantContext("t-idem", "u", "s")
    args = {
        "idempotency_key": "k1",
        "business_id": "biz",
        "slot": "2026-06-22T19:00:00",
        "user_contact": "u@example.com",
    }
    r1 = tool_registry.dispatch("bookings_upsert", ctx, args)
    r2 = tool_registry.dispatch("bookings_upsert", ctx, args)
    assert r1["booking_id"].startswith("bk_")
    assert r1["booking_id"] == r2["booking_id"]
    assert r1["was_new"] is True
    assert r2["was_new"] is False


def test_bookings_cancel_tool_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    from tenancy import factory as tf
    from workflows import bookings_store as bs
    tf.clear_cache(); bs.clear_cache()

    ctx = TenantContext("t-can", "u", "s")
    tool_registry.dispatch("bookings_upsert", ctx, {
        "idempotency_key": "k", "business_id": "b",
        "slot": "2026-06-22T19:00:00", "user_contact": "u",
    })
    bid = tool_registry.dispatch("bookings_upsert", ctx, {
        "idempotency_key": "k", "business_id": "b",
        "slot": "2026-06-22T19:00:00", "user_contact": "u",
    })["booking_id"]

    first = tool_registry.dispatch("bookings_cancel", ctx, {"booking_id": bid, "reason": "x"})
    second = tool_registry.dispatch("bookings_cancel", ctx, {"booking_id": bid, "reason": "y"})
    missing = tool_registry.dispatch("bookings_cancel", ctx, {"booking_id": "bk_notreal"})
    assert first["status"] == "cancelled"
    assert second["status"] == "already_cancelled"
    assert missing["status"] == "not_found"


# ─────────────────────────────────────────────────────────── tool error path


def test_tool_exception_surfaces_in_tool_result(monkeypatch):
    """A tool that raises must produce a tool_result with error field — the
    model gets to see the error and decide how to recover."""
    monkeypatch.setenv("PLNT_CLOUD_URL", "https://example.invalid/v1beta/openai")
    monkeypatch.setenv("PLNT_CLOUD_API_KEY", "fake")

    # Stub places_text_search to raise.
    def boom(ctx, **kwargs):  # noqa: ARG001
        raise RuntimeError("places exploded")
    monkeypatch.setitem(tool_registry._REGISTRY, "places_text_search",
                        tool_registry.Tool(
                            name="places_text_search", description="x",
                            schema={"type": "object", "properties": {}, "required": []},
                            fn=boom))

    calls: list[dict[str, Any]] = []

    def fake_post(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _tool_call("places_text_search", {"query": "q"})
        # On the second round the model sees the error and produces a final.
        return _final(json.dumps({
            "candidates": [], "best_match": None,
            "confidence": 0.0, "needs_disambiguation": True, "source": "llm",
        }))

    monkeypatch.setattr("microagents.agent_loop._post", fake_post)

    skill = load_skill("resolve_business")
    result = run_skill(skill, ctx=_ctx(),
                       inputs={"business_query": "x", "user_text": "x"}, memori=None)
    assert result.error is None
    tr = result.transcript[0]
    assert tr["tool"] == "places_text_search"
    assert "error" in tr["result"]
    assert "places exploded" in tr["result"]["error"]


# ─────────────────────────────────────────────────────────── memory injection


def test_memory_preloaded_into_system_prompt():
    """When memori.recall returns entries, _build_initial_messages folds them
    into the system prompt prefix the way `_inject_memory_into_prompt` used to."""
    from microagents.loader import LoadedSkill
    fake_skill = LoadedSkill(
        role="classify_intent", prompt="SYSTEM RULES",
        manifest={"runtime": {"tools": [], "max_steps": 1}},
    )
    msgs = _build_initial_messages(
        fake_skill, {"text": "hi"},
        [{"role": "user", "content": "previously asked about pizza"}],
    )
    sys_msg = msgs[0]["content"]
    assert "SYSTEM RULES" in sys_msg
    assert "PRIOR CONVERSATION CONTEXT" in sys_msg
    assert "pizza" in sys_msg
