"""The parent's decision parsing and its two model calls, without a model."""

from __future__ import annotations

import json

import pytest

from plnt.agent import parent
from plnt.agent.parent import AgentPlan, ParentError, Specialist, parse_decision
from plnt.models import ChatResult, ScriptedProvider, Usage

SPECS = [
    Specialist("support-desk", "0.1.0", "Answers questions from the FAQ.", ["lookup_faq"]),
    Specialist("booking-desk", "0.1.0", "Books tables.", ["check_availability", "book_table"]),
]


def test_parse_agents_maps_slugs_and_dependencies():
    text = json.dumps({
        "kind": "agents", "reason": "two asks",
        "agents": [
            {"id": "faq", "role": "support-desk", "intent": "vegan options?"},
            {"id": "book", "role": "Booking Desk", "bundle": "booking-desk",
             "intent": "table for 2", "depends_on": ["faq", "nope"]},
        ],
    })
    d = parse_decision(text, SPECS, dynamic_roles=False)
    assert d.kind == "agents" and [a.bundle for a in d.agents] == ["support-desk", "booking-desk"]
    assert d.agents[1].role == "booking-desk" and d.agents[1].depends_on == ["faq"]


def test_parse_drops_invented_roles_unless_allowed():
    text = json.dumps({"kind": "agents", "reason": "r", "agents": [
        {"id": "x", "role": "file-lister", "bundle": None, "intent": "list files"}]})
    with pytest.raises(ParentError):
        parse_decision(text, SPECS, dynamic_roles=False)
    d = parse_decision(text, SPECS, dynamic_roles=True)
    assert d.agents[0].bundle is None and d.agents[0].role == "file-lister"


def test_parse_chat_needs_a_reply_and_survives_code_fences():
    d = parse_decision('```json\n{"kind":"chat","reason":"hi","reply":"Hello!"}\n```', SPECS, False)
    assert d.kind == "chat" and d.reply == "Hello!"
    with pytest.raises(ParentError):
        parse_decision('{"kind":"chat","reason":"hi"}', SPECS, False)
    with pytest.raises(ParentError) as ei:
        parse_decision("I am not JSON", SPECS, False)
    assert "doctor" in ei.value.hint


def test_decide_sends_specialists_and_records_usage():
    seen = []
    plan = json.dumps({"kind": "agents", "reason": "book",
                       "agents": [{"id": "b", "role": "booking-desk", "intent": "t"}]})
    prov = ScriptedProvider(lambda m, t: ChatResult(
        content=plan, usage=Usage(30, 10), provider="scripted", model="m"))
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello"}]
    d = parent.decide(prov, text="table for 2", history=history, specialists=SPECS,
                      business="Luigi's", emit=lambda k, **p: seen.append((k, p)))
    sys_prompt = prov.calls[0]["messages"][0]["content"]
    assert "booking-desk" in sys_prompt and "Luigi's" in sys_prompt and "invent" not in sys_prompt
    assert "Customer: hi" in prov.calls[0]["messages"][1]["content"]
    assert prov.calls[0]["response_schema"] is not None
    assert d.agents[0].bundle == "booking-desk"
    assert [k for k, _ in seen] == ["model_call", "model_result"] and seen[1][1]["tokens"] == 40


def test_synthesize_merges_or_falls_back():
    plans = [AgentPlan("a", "support-desk", "q", "support-desk"),
             AgentPlan("b", "booking-desk", "t", "booking-desk")]
    results = [(plans[0], {"answer": "Yes, vegan risotto."}), (plans[1], {"error": "no slots"})]
    prov = ScriptedProvider(lambda m, t: ChatResult(content="Vegan risotto yes; no table tonight."))
    merged = parent.synthesize(prov, text="x", results=results)
    assert merged == "Vegan risotto yes; no table tonight."
    assert "no table" not in prov.calls[0]["messages"][0]["content"]
    empty = ScriptedProvider(lambda m, t: ChatResult(content=""))
    out = parent.synthesize(empty, text="x", results=results)
    assert "[support-desk] Yes, vegan risotto." in out and "failed: no slots" in out
