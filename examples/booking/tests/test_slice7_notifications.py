"""Slice-7 merchant-notification tests.

Feed module roundtrip, saga → feed wiring (stub activities, real Temporal
dev-server), admin endpoints, and the Resend email path (monkeypatched
httpx — no network).
"""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

from workflows.session import ConversationWorkflow, SessionInput
from workflows.stub_activities import stub_run_microagent, stub_notify_booking


TASK_QUEUE = "plnt-cloud-slice7-test"
ADMIN_TOKEN = "test-admin-token"
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    monkeypatch.setenv("PLNT_CLOUD_MEMORY_BACKEND", "stub")
    monkeypatch.delenv("PLNT_CLOUD_RESEND_KEY", raising=False)

    from memory import memori_adapter as ma
    from tenancy import factory as tf
    from workflows import bookings_store as bs
    tf.clear_cache(); ma.clear_cache(); bs.clear_cache()
    yield tmp_path
    tf.clear_cache(); ma.clear_cache(); bs.clear_cache()


@pytest.fixture
async def env() -> WorkflowEnvironment:
    async with await WorkflowEnvironment.start_local() as e:
        yield e


# ─────────────────────────────────────────────────────────── feed module


def test_feed_roundtrip():
    from tenancy import notifications as ntf

    e1, created1 = ntf.append("t7", "booking_confirmed", "Booking confirmed",
                              "Booking bk_1 is confirmed.", {"booking_id": "bk_1"})
    e2, created2 = ntf.append("t7", "booking_confirmed", "Booking confirmed",
                              "Booking bk_2 is confirmed.", {"booking_id": "bk_2"})
    assert created1 and created2

    rows = ntf.list_notifications("t7")
    assert [r["id"] for r in rows] == [e2["id"], e1["id"]]  # newest first
    assert all(r["read"] is False for r in rows)
    assert ntf.unread_count("t7") == 2
    assert ntf.list_notifications("t7", limit=1) == [rows[0]]

    assert ntf.mark_read("t7", [e1["id"]]) == 1
    assert ntf.unread_count("t7") == 1
    unread = ntf.list_notifications("t7", unread_only=True)
    assert [r["id"] for r in unread] == [e2["id"]]
    # Marking again is a no-op.
    assert ntf.mark_read("t7", [e1["id"]]) == 0


def test_feed_append_idempotent_per_booking_kind():
    from tenancy import notifications as ntf

    e1, c1 = ntf.append("t7i", "booking_confirmed", "t", "b", {"booking_id": "bk_x"})
    e2, c2 = ntf.append("t7i", "booking_confirmed", "t2", "b2", {"booking_id": "bk_x"})
    assert (c1, c2) == (True, False)
    assert e1["id"] == e2["id"]
    assert len(ntf.list_notifications("t7i")) == 1
    # Different kind for the same booking IS a new entry.
    _, c3 = ntf.append("t7i", "booking_compensated", "t", "b", {"booking_id": "bk_x"})
    assert c3 is True
    assert len(ntf.list_notifications("t7i")) == 2


# ─────────────────────────────────────────────────────────── saga → feed


async def _drive_until_role(handle, role: str, timeout_s: float = 10.0) -> list[dict]:
    deadline = asyncio.get_event_loop().time() + timeout_s
    replies: list[dict] = []
    while asyncio.get_event_loop().time() < deadline:
        replies = await handle.query("replies_since", 0)
        if any(r["role"] == role for r in replies):
            return replies
        await asyncio.sleep(0.1)
    return replies


async def test_saga_happy_path_writes_confirmed_notification(env: WorkflowEnvironment):
    from tenancy import notifications as ntf

    wf_id = f"s7-happy-{uuid.uuid4().hex[:8]}"
    async with Worker(
        env.client, task_queue=TASK_QUEUE,
        workflows=[ConversationWorkflow],
        activities=[stub_run_microagent, stub_notify_booking],
    ):
        handle = await env.client.start_workflow(
            ConversationWorkflow.run,
            SessionInput(tenant_id="s7-demo", user_id="alice", session_id="s1",
                         user_contact="alice@example.com"),
            id=wf_id, task_queue=TASK_QUEUE,
        )
        await handle.signal("user_message", "book a table at Joe's Pizza tomorrow at 7pm")
        await _drive_until_role(handle, "check_availability")
        await handle.signal("user_message", "yes book it")
        replies = await _drive_until_role(handle, "booking_saga")
        saga = [r for r in replies if r["role"] == "booking_saga"][-1]
        assert saga["content"]["status"] == "confirmed"
        booking_id = saga["content"]["booking_id"]
        await handle.signal("close")

    rows = ntf.list_notifications("s7-demo")
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "booking_confirmed"
    assert row["read"] is False
    assert row["data"]["booking_id"] == booking_id
    assert row["data"]["user_contact"] == "alice@example.com"
    assert row["data"]["business_name"]
    assert row["data"]["slot"]


async def test_saga_compensation_writes_compensated_notification(env: WorkflowEnvironment):
    from tenancy import notifications as ntf

    wf_id = f"s7-comp-{uuid.uuid4().hex[:8]}"
    async with Worker(
        env.client, task_queue=TASK_QUEUE,
        workflows=[ConversationWorkflow],
        activities=[stub_run_microagent, stub_notify_booking],
    ):
        handle = await env.client.start_workflow(
            ConversationWorkflow.run,
            SessionInput(tenant_id="s7-comp", user_id="bob", session_id="s2",
                         force_fail_step="notify"),
            id=wf_id, task_queue=TASK_QUEUE,
        )
        await handle.signal("user_message", "book a table at Mario's tomorrow at 8pm")
        await _drive_until_role(handle, "check_availability")
        await handle.signal("user_message", "yes")
        replies = await _drive_until_role(handle, "booking_saga")
        saga = [r for r in replies if r["role"] == "booking_saga"][-1]
        assert saga["content"]["status"] == "compensated"
        booking_id = saga["content"]["booking_id"]
        await handle.signal("close")

    rows = ntf.list_notifications("s7-comp")
    assert [r["kind"] for r in rows] == ["booking_compensated"]
    assert rows[0]["data"]["booking_id"] == booking_id


# ─────────────────────────────────────────────────────────── endpoints


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PLNT_CLOUD_ADMIN_TOKEN", ADMIN_TOKEN)
    from surface.admin_v2 import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_notifications_endpoints(client):
    from tenancy import notifications as ntf

    tid = "t7api"
    e1, _ = ntf.append(tid, "booking_confirmed", "Booking confirmed", "b1",
                       {"booking_id": "bk_a"})
    e2, _ = ntf.append(tid, "booking_compensated", "Booking cancelled (compensated)", "b2",
                       {"booking_id": "bk_a"})

    r = client.get(f"/v1/admin/tenants/{tid}/notifications", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["unread_count"] == 2
    assert [n["id"] for n in body["notifications"]] == [e2["id"], e1["id"]]
    assert set(body["notifications"][0]) == {"id", "ts", "kind", "title", "body", "data", "read"}

    r = client.post(f"/v1/admin/tenants/{tid}/notifications/read",
                    headers=AUTH, json={"ids": [e1["id"]]})
    assert r.status_code == 200
    assert r.json() == {"updated": 1}

    r = client.get(f"/v1/admin/tenants/{tid}/notifications",
                   params={"unread": "true"}, headers=AUTH)
    body = r.json()
    assert body["unread_count"] == 1
    assert [n["id"] for n in body["notifications"]] == [e2["id"]]

    r = client.get(f"/v1/admin/tenants/{tid}/notifications",
                   params={"limit": 1}, headers=AUTH)
    assert len(r.json()["notifications"]) == 1

    r = client.get(f"/v1/admin/tenants/{tid}/notifications")
    assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────── email (Resend)


def _write_tenant_json(home, tid: str, **fields):
    tdir = home / "tenants" / tid
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "tenant.json").write_text(json.dumps({"tenant_id": tid, **fields}))


def _dispatch_notify(tid: str, booking_id: str):
    from microagents.tools import dispatch
    from tenancy.context import TenantContext
    return dispatch("notify_send", TenantContext(tid, "u1", "s1"), {
        "booking_id": booking_id,
        "business_name": "Joe's Pizza",
        "slot": "2026-08-08T19:00:00",
    })


def test_email_sent_when_key_and_owner_email(_isolated_home, monkeypatch):
    monkeypatch.setenv("PLNT_CLOUD_RESEND_KEY", "re_test_123")
    _write_tenant_json(_isolated_home, "t7mail", owner_email="owner@example.com")

    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        class R:
            def raise_for_status(self): pass
        return R()

    monkeypatch.setattr("microagents.tools.notify.httpx.post", fake_post)
    result = _dispatch_notify("t7mail", "bk_mail1")
    assert result["sent"] is True and result["email_sent"] is True
    assert len(calls) == 1
    url, kw = calls[0]
    assert url == "https://api.resend.com/emails"
    assert kw["json"]["to"] == ["owner@example.com"]
    assert kw["json"]["from"] == "bookings@plnt.work"
    assert kw["headers"]["Authorization"] == "Bearer re_test_123"

    # notify_email overrides owner_email.
    _write_tenant_json(_isolated_home, "t7mail2",
                       owner_email="owner@example.com", notify_email="ops@example.com")
    _dispatch_notify("t7mail2", "bk_mail2")
    assert calls[-1][1]["json"]["to"] == ["ops@example.com"]

    # Idempotent re-notify: feed dedupes, no second email for same booking.
    n_before = len(calls)
    result = _dispatch_notify("t7mail", "bk_mail1")
    assert result["deduped"] is True
    assert len(calls) == n_before


def test_email_not_sent_without_key(_isolated_home, monkeypatch):
    _write_tenant_json(_isolated_home, "t7nokey", owner_email="owner@example.com")
    calls = []
    monkeypatch.setattr("microagents.tools.notify.httpx.post",
                        lambda *a, **k: calls.append(a))
    result = _dispatch_notify("t7nokey", "bk_nokey")
    assert result["sent"] is True and result["email_sent"] is False
    assert calls == []
    from tenancy.notifications import list_notifications
    assert len(list_notifications("t7nokey")) == 1


async def test_email_failure_does_not_fail_activity(_isolated_home, monkeypatch):
    from workflows.activities import notify_booking
    from tenancy.notifications import list_notifications

    monkeypatch.setenv("PLNT_CLOUD_RESEND_KEY", "re_test_123")
    _write_tenant_json(_isolated_home, "t7fail", owner_email="owner@example.com")

    def boom(*a, **k):
        raise RuntimeError("resend down")

    monkeypatch.setattr("microagents.tools.notify.httpx.post", boom)
    result = await ActivityEnvironment().run(notify_booking, {
        "tenant_id": "t7fail", "user_id": "u1", "session_id": "s1",
        "booking_id": "bk_boom", "business_name": "Joe's Pizza",
    })
    assert result["sent"] is True
    assert result["email_sent"] is False
    rows = list_notifications("t7fail")
    assert len(rows) == 1 and rows[0]["data"]["booking_id"] == "bk_boom"
