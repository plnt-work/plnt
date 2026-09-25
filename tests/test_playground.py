from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from plnt.executors import LocalExecutor
from plnt.models import ChatResult, ScriptedProvider, ToolCall, Usage
from plnt.server import create_app
from plnt.server.playground import DEMO_TENANTS, PlaygroundLimits, playground_router, seed_demo
from plnt.tenancy import TenantStore, installs


def _script(messages, tools):
    names = {(t.get("function") or {}).get("name") for t in tools or []}
    if any(m["role"] == "tool" for m in messages):
        return ChatResult(content="Answer from the tool result.", usage=Usage(50, 10))
    tool = "lookup_faq" if "lookup_faq" in names else "check_availability"
    args = {"question": "open?"} if tool == "lookup_faq" else {"date": "tomorrow", "party_size": 2}
    return ChatResult(tool_calls=[ToolCall("c", tool, args)], usage=Usage(40, 5))


@pytest.fixture
def pg(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    store = TenantStore(tmp_path / "tenants")
    ex = LocalExecutor(store, provider_factory=lambda p: ScriptedProvider(_script))
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


def test_seed_is_idempotent_and_isolated(tmp_path):
    store = TenantStore(tmp_path / "t")
    seed_demo(store)
    seed_demo(store)
    ids = sorted(t.id for t in store.list())
    assert ids == sorted(t["id"] for t in DEMO_TENANTS)
    luigi = store.get("luigis-bistro")
    assert {i.slug for i in installs.list_installed(luigi)} == {"booking-desk", "support-desk"}
    dental = store.get("bright-smile-dental")
    faq = installs.active(dental, "support-desk").config["faq"]
    assert all("Luigi" not in f["a"] for f in faq)


def test_info_lists_demo_tenants_and_agents(pg):
    client, _, _ = pg
    info = client.get("/v1/playground").json()
    assert [t["id"] for t in info["tenants"]] == [t["id"] for t in DEMO_TENANTS]
    luigi = info["tenants"][0]
    assert {a["slug"] for a in luigi["agents"]} == {"booking-desk", "support-desk"}
    assert info["limits"]["max_message_chars"] == 500


def test_chat_flow_over_sse(pg):
    client, _, _ = pg
    r = client.post(
        "/v1/playground/sessions", json={"tenant": "bright-smile-dental", "bundle": "support-desk"}
    )
    assert r.status_code == 201
    sid, token = r.json()["session_id"], r.json()["token"]
    r = client.post(f"/v1/playground/sessions/{sid}/messages?token={token}", json={"text": "Open?"})
    assert r.status_code == 202
    body = _wait(client, sid, token)
    assert "event: tool_call" in body and "Answer from the tool result." in body


def test_sessions_are_private_to_their_token(pg):
    client, _, _ = pg
    a = client.post(
        "/v1/playground/sessions", json={"tenant": "luigis-bistro", "bundle": "support-desk"}
    ).json()
    b = client.post(
        "/v1/playground/sessions", json={"tenant": "luigis-bistro", "bundle": "support-desk"}
    ).json()
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
    r = client.post(
        "/v1/playground/sessions", json={"tenant": "private-co", "bundle": "support-desk"}
    )
    assert r.status_code == 404
    # A token minted for a demo session cannot be replayed against another tenant's session id.
    s = client.post(
        "/v1/playground/sessions", json={"tenant": "luigis-bistro", "bundle": "support-desk"}
    ).json()
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
    s = client.post(
        "/v1/playground/sessions", json={"tenant": "luigis-bistro", "bundle": "support-desk"}
    ).json()
    url = f"/v1/playground/sessions/{s['session_id']}/messages?token={s['token']}"
    assert client.post(url, json={"text": "x" * 501}).status_code == 422


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
        return client.post(
            "/v1/playground/sessions",
            json={
                "tenant": "luigis-bistro",
                "bundle": "support-desk",
            },
        )

    s = new().json()
    assert new().status_code == 201 and new().status_code == 429
    url = f"/v1/playground/sessions/{s['session_id']}/messages?token={s['token']}"
    assert client.post(url, json={"text": "hi"}).status_code == 202
    ex.wait("luigis-bistro", s["session_id"].split(".", 1)[1], 5)
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
