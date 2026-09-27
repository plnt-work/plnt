"""Parent mode end to end on a workspace: decide → agents in parallel/chained
→ merge, every event carrying the agent that produced it, the transcript
fold, session titles, and read-only mode."""

from __future__ import annotations

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from plnt.bundles import catalog
from plnt.executors import LocalExecutor
from plnt.models import ChatResult, ScriptedProvider, ToolCall, Usage
from plnt.server import create_app
from plnt.tenancy import TenantStore, installs

TASK = "audit app/store.py for bugs and add tests for it"


def _script(messages, tools):
    """One provider for parent and agents; branches on what it is asked."""
    system = messages[0]["content"]
    names = {(t.get("function") or {}).get("name") for t in tools or []}
    if "You are the parent agent" in system:
        latest = messages[-1]["content"].rsplit("User: ", 1)[-1]
        if "hello" in latest.lower():
            reply = "Hi! Give me a task on the workspace."
            return ChatResult(content=json.dumps({"kind": "chat", "reason": "greeting",
                                                  "reply": reply}), usage=Usage(20, 5))
        return ChatResult(content=json.dumps({
            "kind": "agents", "reason": "a review plus tests that depend on it",
            "agents": [
                {"id": "review", "role": "code-reviewer", "intent": "find bugs in app/store.py"},
                {"id": "tests", "role": "test-writer", "intent": "write tests for app/store.py",
                 "depends_on": ["review"]},
            ]}), usage=Usage(40, 10))
    if "You write the single reply" in system:
        return ChatResult(
            content="Review: off-by-one in app/store.py:3. Tests: tests/test_store.py.",
            usage=Usage(60, 12),
        )
    done = [m for m in messages if m["role"] == "tool"]
    if not done:
        # Both bundles must read before they answer (require_tool = read_file).
        return ChatResult(tool_calls=[ToolCall("c1", "read_file", {"path": "app/store.py"})],
                          usage=Usage(30, 5))
    if "write_file" in names and len(done) == 1:
        call = ToolCall("c2", "write_file",
                        {"path": "tests/test_store.py", "content": "def test_x(): pass\n"})
        return ChatResult(tool_calls=[call], usage=Usage(30, 5))
    return ChatResult(content="done: " + messages[-1]["content"][:60], usage=Usage(50, 10))


@pytest.fixture
def project(tmp_path):
    src = tmp_path / "proj"
    (src / "app").mkdir(parents=True)
    (src / "app" / "store.py").write_text("ITEMS = []\n\ndef page(n):\n    return ITEMS[n:n+9]\n")
    (src / "README.md").write_text("# proj\n")
    return src


@pytest.fixture
def env(tmp_path, monkeypatch, project):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    monkeypatch.delenv("PLNT_PARENT_DYNAMIC_ROLES", raising=False)
    store = TenantStore(tmp_path / "tenants")
    tenant, _ = store.create("acme", "Acme")
    bundles, _ = catalog.available()
    installs.install(tenant, bundles["code-reviewer"], {"focus": "bugs"})
    installs.install(tenant, bundles["test-writer"], {})
    ex = LocalExecutor(store, provider_factory=lambda p: ScriptedProvider(_script))
    return store, ex


def test_parent_runs_two_agents_in_order_and_merges(env, project):
    store, ex = env
    sid = ex.start_session("acme", "", workspace=str(project))  # no bundle: parent mode
    row = ex.db(store.get("acme")).session(sid)
    assert row["mode"] == "parent" and row["workspace"] == "proj"
    assert row["workspace_kind"] == "path"
    assert row["title"] == ""
    ex.send("acme", sid, "hello", wait=True)
    ex.send("acme", sid, TASK, wait=True)
    ev = ex.events_since("acme", sid)
    kinds = [e["kind"] for e in ev]

    # Turn 1: the parent answered small talk itself; no agent ran.
    first = ev[:kinds.index("run_finished") + 1]
    assert [e["kind"] for e in first] == [
        "user_message", "run_started", "model_call", "model_result",
        "parent_decision", "assistant_message", "run_finished",
    ]
    assert first[1]["payload"]["workspace"] == "proj"
    assert first[4]["agent_id"] == "parent" and first[5]["payload"]["source"] == "parent"
    # The title is the first message.
    assert ex.db(store.get("acme")).session(sid)["title"] == "hello"

    # Turn 2: decision → two agents (spawned with their schema) → merged reply.
    second = ev[len(first):]
    dec = next(e for e in second if e["kind"] == "parent_decision")
    assert dec["payload"]["decision"] == "agents"
    assert [a["id"] for a in dec["payload"]["agents"]] == ["review", "tests"]
    spawned = [e for e in second if e["kind"] == "agent_spawned"]
    assert [e["agent_id"] for e in spawned] == ["review", "tests"]
    rv = spawned[0]["payload"]
    assert rv["bundle"] == "code-reviewer" and rv["tools"] == ["list_files", "read_file", "search"]
    assert rv["require_tool"] == "read_file" and rv["config"]["focus"] == "bugs"
    assert rv["budget"]["tokens"] == 30000 and rv["model"]["provider"] and rv["read_only"] is False
    assert spawned[1]["payload"]["depends_on"] == ["review"]
    assert "write_file" in spawned[1]["payload"]["tools"]
    # Every tool call is attributed to its agent, and the tools really ran on the copy.
    calls = [(e["agent_id"], e["payload"]["tool"]) for e in second if e["kind"] == "tool_call"]
    assert calls == [("review", "read_file"), ("tests", "read_file"), ("tests", "write_file")]
    tenant = store.get("acme")
    assert (tenant.workdir(sid) / "tests" / "test_store.py").read_text().startswith("def test_x")
    assert not (project / "tests").exists()  # the source folder is untouched
    fin = {e["agent_id"]: e["payload"] for e in second if e["kind"] == "agent_finished"}
    assert fin["review"]["outcome"] == "ok" and fin["tests"]["outcome"] == "ok"
    assert fin["review"]["tokens"] == 95 and fin["tests"]["wall_seconds"] >= 0
    reply = next(e for e in second if e["kind"] == "assistant_message")
    assert reply["payload"]["source"] == "synth"
    assert reply["payload"]["agents"] == ["review", "tests"]
    assert "off-by-one" in reply["payload"]["text"]
    assert second[-1]["kind"] == "run_finished" and second[-1]["payload"]["outcome"] == "ok"

    # Usage is booked per agent and for the parent.
    by = {r["bundle"] for r in ex.db(tenant).usage_summary()["by_bundle_model"]}
    assert by == {"parent", "code-reviewer", "test-writer"}


def test_transcript_folds_events_into_turns(env, project):
    store, ex = env
    sid = ex.start_session("acme", "", workspace=str(project))
    ex.send("acme", sid, TASK, wait=True)
    tr = ex.transcript("acme", sid)
    assert tr["mode"] == "parent" and len(tr["turns"]) == 1
    assert tr["title"] == TASK and tr["workspace"] == "proj"
    turn = tr["turns"][0]
    assert turn["parent"]["kind"] == "agents" and len(turn["parent"]["plan"]) == 2
    agents = {a["id"]: a for a in turn["agents"]}
    assert agents["review"]["bundle"] == "code-reviewer" and agents["review"]["status"] == "done"
    assert agents["review"]["steps"][0] == {"kind": "tool_call", "step": 1, "tool": "read_file",
                                            "args": {"path": "app/store.py"}, "ok": True}
    assert agents["tests"]["depends_on"] == ["review"]
    assert agents["tests"]["answer"].startswith("done:")
    assert turn["reply"]["source"] == "synth" and turn["outcome"] == "ok" and turn["tokens"] > 0


def test_title_is_shortened_and_set_once(env):
    store, ex = env
    sid = ex.start_session("acme", "code-reviewer")
    ex.send("acme", sid, "  \n" + "x" * 200 + "\nsecond line", wait=True)
    ex.send("acme", sid, "another message", wait=True)
    title = ex.db(store.get("acme")).session(sid)["title"]
    assert title.endswith("…") and len(title) == 78


def test_read_only_executor_strips_write_and_execute(tmp_path, monkeypatch, project):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    store = TenantStore(tmp_path / "t")
    tenant, _ = store.create("ro")
    bundles, _ = catalog.available()
    installs.install(tenant, bundles["code-reviewer"], {})
    installs.install(tenant, bundles["test-writer"], {})

    def script(messages, tools):
        names = {(t.get("function") or {}).get("name") for t in tools or []}
        if "You are the parent agent" in messages[0]["content"]:
            return _script(messages, tools)
        if "You write the single reply" in messages[0]["content"]:
            return _script(messages, tools)
        if any(m["role"] == "tool" for m in messages):
            return ChatResult(content="tools were: " + ",".join(sorted(names)), usage=Usage(1, 1))
        return ChatResult(tool_calls=[ToolCall("c", "read_file", {"path": "README.md"})],
                          usage=Usage(1, 1))

    ex = LocalExecutor(store, provider_factory=lambda p: ScriptedProvider(script),
                       read_only=True, dynamic_roles=True)
    sid = ex.start_session("ro", "", workspace=str(project))
    ex.send("ro", sid, TASK, wait=True)
    ev = ex.events_since("ro", sid)
    spawned = {e["agent_id"]: e["payload"] for e in ev if e["kind"] == "agent_spawned"}
    assert spawned["tests"]["tools"] == ["list_files", "read_file", "search"]
    assert spawned["tests"]["read_only"] is True
    started = next(e for e in ev if e["kind"] == "run_started")["payload"]
    assert started["read_only"] is True and started["dynamic_roles"] is True
    fin = {e["agent_id"]: e["payload"]["answer"] for e in ev if e["kind"] == "agent_finished"}
    assert fin["tests"] == "tools were: list_files,read_file,search"


def test_dynamic_role_gets_builtin_tools_over_the_workspace(tmp_path, monkeypatch, project):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    store = TenantStore(tmp_path / "t")
    tenant, _ = store.create("dyn")
    bundles, _ = catalog.available()
    installs.install(tenant, bundles["code-reviewer"], {})

    def script(messages, tools):
        names = {(t.get("function") or {}).get("name") for t in tools or []}
        sysm = messages[0]["content"]
        if "You are the parent agent" in sysm:
            return ChatResult(content=json.dumps({"kind": "agents", "reason": "needs a lister",
                "agents": [{"id": "lister", "role": "file-lister", "bundle": None,
                            "intent": "list the files"}]}), usage=Usage(1, 1))
        if any(m["role"] == "tool" for m in messages):
            return ChatResult(content=messages[-1]["content"], usage=Usage(1, 1))
        assert names == {"list_files", "read_file", "write_file", "search", "execute"}
        return ChatResult(tool_calls=[ToolCall("c", "list_files", {"path": "."})],
                          usage=Usage(1, 1))

    ex = LocalExecutor(store, provider_factory=lambda p: ScriptedProvider(script),
                       dynamic_roles=True)
    sid = ex.start_session("dyn", "", workspace=str(project))
    ex.send("dyn", sid, "list the files", wait=True)
    tr = ex.transcript("dyn", sid)
    a = tr["turns"][0]["agents"][0]
    assert a["bundle"] is None and a["role"] == "file-lister" and a["status"] == "done"
    assert "app/" in a["answer"] and "store.py" in a["answer"]


def test_workspace_policy_is_enforced(env, project, tmp_path):
    store, ex = env
    ex.allow_local_paths = False
    with pytest.raises(Exception, match="not allowed"):
        ex.start_session("acme", "", workspace=str(project))
    ex.allow_local_paths = True
    with pytest.raises(Exception, match="not allowed"):
        ex.start_session("acme", "", workspace="https://example.com/x.git")
    # No session row is left behind for a refused workspace.
    assert ex.db(store.get("acme")).sessions() == []


def test_parent_session_needs_an_enabled_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    store = TenantStore(tmp_path / "t")
    store.create("empty")
    ex = LocalExecutor(store, provider_factory=lambda p: ScriptedProvider(_script))
    with pytest.raises(Exception, match="no enabled agents"):
        ex.start_session("empty", "")


def test_kill_stops_the_remaining_agents(env, project):
    store, ex = env
    started = threading.Event()

    def slow(messages, tools):
        if "You are the parent agent" in messages[0]["content"]:
            return _script(messages, tools)
        started.set()
        time.sleep(0.5)
        return _script(messages, tools)

    ex.provider_factory = lambda p: ScriptedProvider(slow)
    sid = ex.start_session("acme", "", workspace=str(project))
    ex.send("acme", sid, TASK)
    started.wait(5)
    assert ex.kill("acme", sid, "operator")
    ex.wait("acme", sid, 10)
    ev = ex.events_since("acme", sid)
    fin = {e["agent_id"]: e["payload"]["outcome"] for e in ev if e["kind"] == "agent_finished"}
    assert fin["tests"] == "skipped" and ev[-1]["payload"]["outcome"] != "ok"


def test_http_sessions_with_workspace_and_transcript(env, project):
    store, ex = env
    app = create_app(store=store, executor=ex, admin_token="adm")
    c = TestClient(app)
    h = {"Authorization": "Bearer adm"}
    r = c.post("/v1/tenants/acme/sessions", json={"user_id": "u1", "workspace": str(project)},
               headers=h)
    assert r.status_code == 201
    sid = r.json()["session_id"]
    c.post(f"/v1/tenants/acme/sessions/{sid}/messages", json={"text": TASK}, headers=h)
    ex.wait("acme", sid, 10)
    tr = c.get(f"/v1/tenants/acme/sessions/{sid}/transcript", headers=h).json()
    assert tr["turns"][0]["parent"]["kind"] == "agents"
    assert len(tr["turns"][0]["agents"]) == 2
    rows = c.get("/v1/tenants/acme/sessions", headers=h).json()["sessions"]
    assert rows[0]["mode"] == "parent" and rows[0]["title"] == TASK
    assert rows[0]["workspace"] == "proj" and rows[0]["workspace_kind"] == "path"
    assert c.get("/v1/tenants/acme/sessions/nope/transcript", headers=h).status_code == 404
    bad = c.post("/v1/tenants/acme/sessions", json={"workspace": "nope"}, headers=h)
    assert bad.status_code == 422 and "not a demo" in bad.json()["detail"]
