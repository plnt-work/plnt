from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from plnt.executors import LocalExecutor
from plnt.models import ChatResult, ScriptedProvider, ToolCall, Usage
from plnt.server import create_app
from plnt.server.playground import (
    DEMO_TENANTS,
    PlaygroundLimits,
    playground_router,
    seed_demo,
    sweep_workdirs,
)
from plnt.tenancy import TenantStore, installs


def _script(messages, tools):
    names = {(t.get("function") or {}).get("name") for t in tools or []}
    if any(m["role"] == "tool" for m in messages):
        return ChatResult(content="Answer from the tool result.", usage=Usage(50, 10))
    tool = "list_files" if "list_files" in names else "read_file"
    return ChatResult(tool_calls=[ToolCall("c", tool, {"path": "."})], usage=Usage(40, 5))


@pytest.fixture
def pg(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    store = TenantStore(tmp_path / "tenants")
    ex = LocalExecutor(store, provider_factory=lambda p: ScriptedProvider(_script),
                       read_only=True, dynamic_roles=True, allow_local_paths=False)
    app = create_app(store=store, executor=ex, admin_token="adm", playground=True)
    return TestClient(app), store, ex


def _wait(client, sid, token, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with client.stream(
            "GET", f"/v1/playground/sessions/{sid}/stream?token={token}&until_idle=1"
        ) as s:
            body = ""
            for chunk in s.iter_text():
                body += chunk
                if "event: run_finished" in body:
                    return body
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_seed_is_idempotent_and_installs_dev_bundles(tmp_path):
    store = TenantStore(tmp_path / "t")
    seed_demo(store)
    seed_demo(store)
    ids = sorted(t.id for t in store.list())
    assert ids == sorted(t["id"] for t in DEMO_TENANTS)
    notes = store.get("notes-api")
    assert {i.slug for i in installs.list_installed(notes)} == {
        "repo-explainer", "code-reviewer", "test-writer", "changelog-writer"}
    assert installs.active(notes, "code-reviewer").config["focus"] == "bugs"
    assert installs.active(store.get("cli-tool"), "code-reviewer").config["focus"] == "all"


def test_info_lists_workspaces_agents_and_policy(pg):
    client, _, _ = pg
    info = client.get("/v1/playground").json()
    assert [t["id"] for t in info["tenants"]] == [t["id"] for t in DEMO_TENANTS]
    notes = info["tenants"][0]
    assert notes["workspace"]["name"] == "notes-api" and notes["workspace"]["file_count"] >= 6
    assert len(notes["workspace"]["suggested_tasks"]) == 4
    agents = {a["slug"]: a for a in notes["agents"]}
    assert set(agents) == {"repo-explainer", "code-reviewer", "test-writer", "changelog-writer"}
    # Read-only playground: the tool list already reflects what is stripped.
    assert agents["test-writer"]["tools"] == ["list_files", "read_file", "search"]
    assert info["execute_enabled"] is False and info["parent"]["dynamic_roles"] is True
    assert info["limits"]["max_message_chars"] == 1000


def test_session_gets_its_own_workspace_copy(pg):
    client, store, _ = pg
    r = client.post("/v1/playground/sessions", json={"tenant": "notes-api"})
    assert r.status_code == 201
    sid_full = r.json()["session_id"]
    sid = sid_full.split(".", 1)[1]
    tenant = store.get("notes-api")
    assert (tenant.workdir(sid) / "app" / "store.py").is_file()
    row = LocalExecutor(store).db(tenant).session(sid)
    assert row["workspace"] == "notes-api" and row["workspace_kind"] == "demo"
    # A client cannot pick another workspace: the field is not accepted.
    r2 = client.post("/v1/playground/sessions",
                     json={"tenant": "cli-tool", "workspace": "/etc"})
    assert r2.status_code == 201
    sid2 = r2.json()["session_id"].split(".", 1)[1]
    assert (store.get("cli-tool").workdir(sid2) / "todo" / "cli.py").is_file()


def test_chat_flow_over_sse(pg):
    client, _, _ = pg
    r = client.post(
        "/v1/playground/sessions", json={"tenant": "notes-api", "bundle": "repo-explainer"}
    )
    assert r.status_code == 201
    sid, token = r.json()["session_id"], r.json()["token"]
    r = client.post(f"/v1/playground/sessions/{sid}/messages?token={token}",
                    json={"text": "What is this?"})
    assert r.status_code == 202
    body = _wait(client, sid, token)
    assert "event: tool_call" in body and "Answer from the tool result." in body
    tr = client.get(f"/v1/playground/sessions/{sid}/transcript?token={token}").json()
    assert tr["title"] == "What is this?" and tr["workspace"] == "notes-api"


def test_sessions_are_private_to_their_token(pg):
    client, _, _ = pg
    a = client.post("/v1/playground/sessions", json={"tenant": "notes-api"}).json()
    b = client.post("/v1/playground/sessions", json={"tenant": "notes-api"}).json()
    # B's token does not open A's session, and no token opens nothing.
    for tok in (b["token"], "", "0" * 32):
        assert (
            client.post(
                f"/v1/playground/sessions/{a['session_id']}/messages?token={tok}",
                json={"text": "hi"},
            ).status_code
            == 404
        )
        assert (
            client.get(f"/v1/playground/sessions/{a['session_id']}/stream?token={tok}").status_code
            == 404
        )


def test_only_demo_tenants_are_reachable(pg):
    client, store, _ = pg
    store.create("private-co")
    r = client.post("/v1/playground/sessions", json={"tenant": "private-co"})
    assert r.status_code == 404
    # A token minted for a demo session cannot be replayed against another tenant's session id.
    s = client.post("/v1/playground/sessions", json={"tenant": "notes-api"}).json()
    forged = "private-co." + s["session_id"].split(".", 1)[1]
    assert (
        client.post(
            f"/v1/playground/sessions/{forged}/messages?token={s['token']}", json={"text": "hi"}
        ).status_code
        == 404
    )
    # Operator routes are still closed to anonymous callers.
    assert client.get("/v1/tenants").status_code == 401


def test_message_limits(pg):
    client, _, _ = pg
    s = client.post("/v1/playground/sessions", json={"tenant": "notes-api"}).json()
    url = f"/v1/playground/sessions/{s['session_id']}/messages?token={s['token']}"
    assert client.post(url, json={"text": "x" * 1001}).status_code == 422


def test_sweep_removes_old_workspace_copies(pg):
    client, store, _ = pg
    s = client.post("/v1/playground/sessions", json={"tenant": "notes-api"}).json()
    sid = s["session_id"].split(".", 1)[1]
    d = store.get("notes-api").workdir(sid)
    assert d.is_dir()
    assert sweep_workdirs(store, ttl=3600) == 0
    assert sweep_workdirs(store, ttl=-1) == 1 and not d.exists()


def test_rate_limit_and_daily_budget(tmp_path, monkeypatch):
    from fastapi import FastAPI

    monkeypatch.setenv("PLNT_FORCE", "offline")
    store = TenantStore(tmp_path / "t")
    seed_demo(store)
    ex = LocalExecutor(store, provider_factory=lambda p: ScriptedProvider(_script))
    app = FastAPI()
    app.include_router(
        playground_router(
            store, ex, PlaygroundLimits(sessions_per_10min=2, messages_per_10min=1, daily_tokens=10)
        )
    )
    client = TestClient(app)

    def new():
        return client.post("/v1/playground/sessions",
                           json={"tenant": "notes-api", "bundle": "repo-explainer"})

    s = new().json()
    assert new().status_code == 201 and new().status_code == 429
    url = f"/v1/playground/sessions/{s['session_id']}/messages?token={s['token']}"
    assert client.post(url, json={"text": "hi"}).status_code == 202
    ex.wait("notes-api", s["session_id"].split(".", 1)[1], 5)
    time.sleep(0.2)  # usage accounting runs after the turn
    # 105 tokens used > daily cap of 10: further messages are refused with 503.
    assert client.post(url, json={"text": "again"}).status_code == 503
    assert client.get("/v1/playground").json()["limits"]["daily_tokens_left"] == 0


def test_cors_for_playground(pg):
    client, _, _ = pg
    r = client.options(
        "/v1/playground",
        headers={"Origin": "https://plnt.work", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") in ("*", "https://plnt.work")


def test_root_points_to_the_playground(pg):
    client, _, _ = pg
    body = client.get("/").json()
    assert body["playground"] == "/v1/playground" and body["health"] == "/v1/health"


def test_cors_origin_patterns(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    monkeypatch.setenv(
        "PLNT_PLAYGROUND_ORIGINS", "https://plnt.work, https://plnt-site*.vercel.app"
    )
    store = TenantStore(tmp_path / "tenants")
    ex = LocalExecutor(store, provider_factory=lambda p: ScriptedProvider(_script))
    client = TestClient(create_app(store=store, executor=ex, admin_token="adm", playground=True))

    def allowed(origin: str) -> str | None:
        r = client.options("/v1/playground", headers={
            "Origin": origin, "Access-Control-Request-Method": "GET"})
        return r.headers.get("access-control-allow-origin")

    assert allowed("https://plnt.work") == "https://plnt.work"
    preview = "https://plnt-site-git-feature-x-someone.vercel.app"
    assert allowed(preview) == preview
    assert allowed("https://evil.example") is None
    assert allowed("https://other-site.vercel.app") is None
