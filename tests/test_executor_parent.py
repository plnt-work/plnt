"""Parent mode end to end: decide → agents in parallel/chained → merge, with
every event carrying the agent that produced it, and the transcript fold."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from plnt.bundles import catalog
from plnt.executors import LocalExecutor
from plnt.models import ChatResult, ScriptedProvider, ToolCall, Usage
from plnt.server import create_app
from plnt.tenancy import TenantStore, installs

FAQ = [{"q": "Do you have vegan options?", "a": "Yes: a vegan risotto."}]
BOOK_CFG = {"business_name": "Luigi's", "handoff_contact": "h@l.example", "timezone": "UTC",
            "hours_sat": "18:00-22:00", "tables_per_slot": 2}


def _script(messages, tools):
    """One provider for parent and agents; branches on what it is asked."""
    system = messages[0]["content"]
    names = {(t.get("function") or {}).get("name") for t in tools or []}
    if "You are the parent agent" in system:
        latest = messages[-1]["content"].rsplit("Customer: ", 1)[-1]
        if "hello" in latest.lower():
            reply = "Hi! Ask me about the menu or a table."
            return ChatResult(content=json.dumps({"kind": "chat", "reason": "greeting",
                                                  "reply": reply}), usage=Usage(20, 5))
        return ChatResult(content=json.dumps({
            "kind": "agents", "reason": "menu question plus a booking",
            "agents": [
                {"id": "faq", "role": "support-desk", "intent": "vegan options?"},
                {"id": "book", "role": "booking-desk", "intent": "table for 2 Saturday 19:00",
                 "depends_on": ["faq"]},
            ]}), usage=Usage(40, 10))
    if "single reply a customer" in system:
        return ChatResult(content="Vegan risotto is on the menu, and your table for 2 is booked.",
                          usage=Usage(60, 12))
    if any(m["role"] == "tool" for m in messages):
        return ChatResult(content="done: " + messages[-1]["content"][:60], usage=Usage(50, 10))
    if "lookup_faq" in names:
        call = ToolCall("c1", "lookup_faq", {"question": "vegan?"})
    else:
        call = ToolCall("c2", "check_availability", {"date": "2026-10-03", "party_size": 2})
    return ChatResult(tool_calls=[call], usage=Usage(30, 5))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    monkeypatch.delenv("PLNT_PARENT_DYNAMIC_ROLES", raising=False)
    store = TenantStore(tmp_path / "tenants")
    tenant, _ = store.create("luigi", "Luigi's")
    bundles, _ = catalog.available()
    installs.install(tenant, bundles["support-desk"],
                     {"business_name": "Luigi's", "handoff_contact": "h@l.example", "faq": FAQ})
    installs.install(tenant, bundles["booking-desk"], BOOK_CFG)
    ex = LocalExecutor(store, provider_factory=lambda p: ScriptedProvider(_script))
    return store, ex


def test_parent_runs_two_agents_in_order_and_merges(env):
    store, ex = env
    sid = ex.start_session("luigi", "")  # no bundle: parent mode
    assert ex.db(store.get("luigi")).session(sid)["mode"] == "parent"
    ex.send("luigi", sid, "hello", wait=True)
    ex.send("luigi", sid, "any vegan options? and a table for 2 on Saturday 7pm", wait=True)
    ev = ex.events_since("luigi", sid)
    kinds = [e["kind"] for e in ev]

    # Turn 1: the parent answered small talk itself; no agent ran.
    first = ev[:kinds.index("run_finished") + 1]
    assert [e["kind"] for e in first] == [
        "user_message", "run_started", "model_call", "model_result",
        "parent_decision", "assistant_message", "run_finished",
    ]
    assert first[4]["agent_id"] == "parent" and first[5]["payload"]["source"] == "parent"

    # Turn 2: decision → two agents (spawned with their schema) → merged reply.
    second = ev[len(first):]
    dec = next(e for e in second if e["kind"] == "parent_decision")
    assert dec["payload"]["decision"] == "agents"
    assert [a["id"] for a in dec["payload"]["agents"]] == ["faq", "book"]
    spawned = [e for e in second if e["kind"] == "agent_spawned"]
    assert [e["agent_id"] for e in spawned] == ["faq", "book"]
    faq = spawned[0]["payload"]
    assert faq["bundle"] == "support-desk" and faq["tools"] == ["lookup_faq"]
    assert faq["require_tool"] == "lookup_faq" and faq["config"]["faq"] == FAQ
    assert faq["budget"]["tokens"] == 8000 and faq["model"]["provider"]
    assert spawned[1]["payload"]["depends_on"] == ["faq"]
    # Every tool call is attributed to its agent.
    calls = [(e["agent_id"], e["payload"]["tool"]) for e in second if e["kind"] == "tool_call"]
    assert calls == [("faq", "lookup_faq"), ("book", "check_availability")]
    # The booking agent saw the FAQ agent's result (it depended on it).
    fin = {e["agent_id"]: e["payload"] for e in second if e["kind"] == "agent_finished"}
    assert fin["faq"]["outcome"] == "ok" and fin["book"]["outcome"] == "ok"
    assert fin["faq"]["tokens"] == 95 and fin["book"]["wall_seconds"] >= 0
    reply = next(e for e in second if e["kind"] == "assistant_message")
    assert reply["payload"]["source"] == "synth" and reply["payload"]["agents"] == ["faq", "book"]
    assert "risotto" in reply["payload"]["text"]
    assert second[-1]["kind"] == "run_finished" and second[-1]["payload"]["outcome"] == "ok"

    # Usage is booked per agent and for the parent.
    by = {r["bundle"] for r in ex.db(store.get("luigi")).usage_summary()["by_bundle_model"]}
    assert by == {"parent", "support-desk", "booking-desk"}


def test_transcript_folds_events_into_turns(env):
    store, ex = env
    sid = ex.start_session("luigi", "")
    ex.send("luigi", sid, "vegan? and a table for 2 Saturday 7pm", wait=True)
    tr = ex.transcript("luigi", sid)
    assert tr["mode"] == "parent" and len(tr["turns"]) == 1
    turn = tr["turns"][0]
    assert turn["parent"]["kind"] == "agents" and len(turn["parent"]["plan"]) == 2
    agents = {a["id"]: a for a in turn["agents"]}
    assert agents["faq"]["bundle"] == "support-desk" and agents["faq"]["status"] == "done"
    assert agents["faq"]["steps"][0] == {"kind": "tool_call", "step": 1, "tool": "lookup_faq",
                                         "args": {"question": "vegan?"}, "ok": True}
    assert agents["book"]["depends_on"] == ["faq"] and agents["book"]["answer"].startswith("done:")
    assert turn["reply"]["source"] == "synth" and turn["outcome"] == "ok" and turn["tokens"] > 0


def test_single_agent_session_still_works_and_has_a_transcript(env):
    store, ex = env
    sid = ex.start_session("luigi", "support-desk")
    ex.send("luigi", sid, "vegan?", wait=True)
    kinds = [e["kind"] for e in ex.events_since("luigi", sid)]
    assert "parent_decision" not in kinds and "agent_spawned" not in kinds
    tr = ex.transcript("luigi", sid)
    assert tr["mode"] == "agent" and tr["turns"][0]["agents"][0]["bundle"] == "support-desk"
    assert tr["turns"][0]["agents"][0]["status"] == "done"
    assert tr["turns"][0]["reply"]["source"] == "agent"


def test_parent_session_needs_an_enabled_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    store = TenantStore(tmp_path / "t")
    store.create("empty")
    ex = LocalExecutor(store, provider_factory=lambda p: ScriptedProvider(_script))
    with pytest.raises(Exception, match="no enabled agents"):
        ex.start_session("empty", "")


def test_kill_stops_the_remaining_agents(env, monkeypatch):
    store, ex = env
    import threading
    started = threading.Event()

    def slow(messages, tools):
        if "You are the parent agent" in messages[0]["content"]:
            return _script(messages, tools)
        started.set()
        import time
        time.sleep(0.5)
        return _script(messages, tools)

    ex.provider_factory = lambda p: ScriptedProvider(slow)
    sid = ex.start_session("luigi", "")
    ex.send("luigi", sid, "vegan? and a table Saturday 7pm")
    started.wait(5)
    assert ex.kill("luigi", sid, "operator")
    ex.wait("luigi", sid, 10)
    ev = ex.events_since("luigi", sid)
    fin = {e["agent_id"]: e["payload"]["outcome"] for e in ev if e["kind"] == "agent_finished"}
    assert fin["book"] == "skipped" and ev[-1]["payload"]["outcome"] != "ok"


def test_http_sessions_without_bundle_and_transcript(env):
    store, ex = env
    app = create_app(store=store, executor=ex, admin_token="adm")
    c = TestClient(app)
    h = {"Authorization": "Bearer adm"}
    r = c.post("/v1/tenants/luigi/sessions", json={"user_id": "u1"}, headers=h)
    assert r.status_code == 201
    sid = r.json()["session_id"]
    c.post(f"/v1/tenants/luigi/sessions/{sid}/messages",
           json={"text": "vegan? table for 2 Sat 7pm"}, headers=h)
    ex.wait("luigi", sid, 10)
    tr = c.get(f"/v1/tenants/luigi/sessions/{sid}/transcript", headers=h).json()
    assert tr["turns"][0]["parent"]["kind"] == "agents" and len(tr["turns"][0]["agents"]) == 2
    assert c.get("/v1/tenants/luigi/sessions", headers=h).json()["sessions"][0]["mode"] == "parent"
    assert c.get("/v1/tenants/luigi/sessions/nope/transcript", headers=h).status_code == 404
