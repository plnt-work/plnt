from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from plnt.executors import LocalExecutor
from plnt.models import ChatResult, ScriptedProvider, ToolCall, Usage
from plnt.server import create_app
from plnt.tenancy import TenantStore

FIXTURES = Path(__file__).parent / "fixtures" / "bundles"
ADMIN = {"Authorization": "Bearer admin-secret"}


def _bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_BUNDLE_PATH", str(FIXTURES))
    monkeypatch.setenv("PLNT_FORCE", "offline")
    store = TenantStore(tmp_path / "tenants")
    provider = ScriptedProvider(
        lambda m, t: (
            ChatResult(content="Shipped!", usage=Usage(80, 5))
            if any(x["role"] == "tool" for x in m)
            else ChatResult(
                tool_calls=[ToolCall("c", "lookup_order", {"order_id": "7"})], usage=Usage(60, 5)
            )
        )
    )
    ex = LocalExecutor(store, provider_factory=lambda p: provider)
    client = TestClient(create_app(store=store, executor=ex, admin_token="admin-secret"))
    return client, ex


def _tenant(client, tid, shop):
    r = client.post("/v1/tenants", json={"id": tid, "name": shop}, headers=ADMIN)
    assert r.status_code == 201, r.text
    key = r.json()["api_key"]
    h = _bearer(key)
    assert (
        client.put(
            f"/v1/tenants/{tid}/secrets/SHOP_API_KEY", json={"value": f"sk-{tid}"}, headers=h
        ).status_code
        == 204
    )
    r = client.post(
        f"/v1/tenants/{tid}/installs",
        json={"bundle": "order-desk", "config": {"shop_name": shop}},
        headers=h,
    )
    assert r.status_code == 201, r.text
    return h


def _wait_finished(client, url, h, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        events = client.get(url, headers=h).json()["events"]
        if events and events[-1]["kind"] == "run_finished":
            return events
        time.sleep(0.05)
    raise AssertionError(f"run did not finish: {events}")


def test_operator_routes_fail_closed_without_admin_token(tmp_path):
    client = TestClient(create_app(store=TenantStore(tmp_path / "t"), admin_token=""))
    assert client.post("/v1/tenants", json={"id": "acme"}).status_code == 503
    assert (
        client.get("/v1/tenants", headers={"Authorization": "Bearer anything"}).status_code == 503
    )


def test_auth_scopes(api):
    client, _ = api
    assert client.post("/v1/tenants", json={"id": "acme"}).status_code == 401
    ha = _tenant(client, "acme", "Acme")
    hb = _tenant(client, "bravo", "Bravo")
    assert client.get("/v1/tenants/acme", headers=ha).status_code == 200
    assert client.get("/v1/tenants/acme", headers=hb).status_code == 401  # B's key on A
    assert client.get("/v1/tenants/acme").status_code == 401
    assert client.get("/v1/tenants", headers=ha).status_code == 401  # tenant key isn't operator
    assert client.get("/v1/tenants/acme", headers=ADMIN).status_code == 200
    assert client.get("/v1/tenants/nope", headers=ADMIN).status_code == 404


def test_full_flow_two_tenants_same_bundle(api):
    client, _ = api
    ha = _tenant(client, "acme", "Acme")
    hb = _tenant(client, "bravo", "Bravo")

    catalog = client.get("/v1/bundles").json()["bundles"]
    assert "order-desk" in {b["slug"] for b in catalog}

    info = client.get("/v1/tenants/acme", headers=ha).json()
    assert info["secrets"] == ["SHOP_API_KEY"] and "sk-acme" not in json.dumps(info)
    assert info["installs"][0]["config"]["shop_name"] == "Acme"

    for tid, h in (("acme", ha), ("bravo", hb)):
        sid = client.post(
            f"/v1/tenants/{tid}/sessions", json={"bundle": "order-desk"}, headers=h
        ).json()["session_id"]
        r = client.post(
            f"/v1/tenants/{tid}/sessions/{sid}/messages", json={"text": "where is 7?"}, headers=h
        )
        assert r.status_code == 202
        events = _wait_finished(client, f"/v1/tenants/{tid}/sessions/{sid}/events", h)
        kinds = [e["kind"] for e in events]
        assert "tool_call" in kinds and kinds[-2] == "assistant_message"
        tool_msg = [e for e in events if e["kind"] == "tool_result"]
        assert tool_msg and tool_msg[0]["payload"]["ok"]

        # SSE replays the same log and closes once the run is finished.
        with client.stream(
            "GET", f"/v1/tenants/{tid}/sessions/{sid}/stream?until_idle=1", headers=h
        ) as s:
            body = "".join(s.iter_text())
        assert "event: assistant_message" in body and "event: run_finished" in body

        usage = client.get(f"/v1/tenants/{tid}/usage", headers=h).json()
        assert usage["model_calls"] == 2 and usage["prompt_tokens"] == 140

    # Each tenant sees only its own sessions.
    sessions_a = client.get("/v1/tenants/acme/sessions", headers=ha).json()["sessions"]
    sid_b = client.get("/v1/tenants/bravo/sessions", headers=hb).json()["sessions"][0]["id"]
    assert sid_b not in {s["id"] for s in sessions_a}
    assert client.get(f"/v1/tenants/acme/sessions/{sid_b}/events", headers=ha).status_code == 404


def test_install_validation_and_catalog_only(api):
    client, _ = api
    h = _bearer(client.post("/v1/tenants", json={"id": "acme"}, headers=ADMIN).json()["api_key"])
    r = client.post(
        "/v1/tenants/acme/installs", json={"bundle": "order-desk", "config": {}}, headers=h
    )
    assert r.status_code == 422 and "shop_name" in r.text
    r = client.post("/v1/tenants/acme/installs", json={"bundle": "/etc", "config": {}}, headers=h)
    assert r.status_code == 422 and "catalog" in r.text
    client.post(
        "/v1/tenants/acme/installs",
        json={"bundle": "order-desk", "config": {"shop_name": "A"}},
        headers=h,
    )
    r = client.patch("/v1/tenants/acme/installs/order-desk", json={"enabled": False}, headers=h)
    assert r.json()["enabled"] is False
    r = client.post("/v1/tenants/acme/sessions", json={"bundle": "order-desk"}, headers=h)
    assert r.status_code == 409
    assert client.delete("/v1/tenants/acme/installs/order-desk", headers=h).status_code == 204
    assert client.get("/v1/tenants/acme/installs", headers=h).json()["installs"] == []


def test_model_settings_and_audit(api):
    client, _ = api
    h = _bearer(client.post("/v1/tenants", json={"id": "acme"}, headers=ADMIN).json()["api_key"])
    r = client.put("/v1/tenants/acme/model", json={"provider": "nope"}, headers=h)
    assert r.status_code == 400
    r = client.put(
        "/v1/tenants/acme/model",
        json={"provider": "ollama", "model": "qwen2.5:7b", "base_url": "http://127.0.0.1:1"},
        headers=h,
    )
    assert r.status_code == 200
    health = client.get("/v1/tenants/acme/model/health", headers=h).json()
    assert health["ok"] is False and health["reachable"] is False
    actions = [
        e["action"] for e in client.get("/v1/tenants/acme/audit", headers=h).json()["events"]
    ]
    assert actions == ["tenant.created", "model.set"]


def test_dev_mode_is_open(tmp_path):
    client = TestClient(create_app(store=TenantStore(tmp_path / "t"), admin_token="", dev=True))
    assert client.post("/v1/tenants", json={"id": "dev"}).status_code == 201
    assert client.get("/v1/tenants/dev").status_code == 200
