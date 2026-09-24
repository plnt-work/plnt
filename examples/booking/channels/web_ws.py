"""Web WebSocket channel — slice 1's only inbound surface.

Endpoint: GET /v1/ws/{tenant_id}/{session_id}?user_id=<id>

Per the design, tenant identification is URL-prefixed. On connect we either
start a new ConversationWorkflow or attach to an existing one for the
(tenant, user, session) triple. Inbound messages are sent as `user_message`
signals; outbound replies are surfaced by polling the Workflow's
`replies_since` query.

Polling is correct for slice 1 — Temporal doesn't push from Workflow to
client natively. Slice 3 introduces a per-tenant Redis (or in-process)
pubsub that the WS subscribes to; Activities then publish replies. The
Workflow query stays as the durable source of truth either way.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from temporalio.client import Client, WorkflowHandle
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode

from workflows.session import SessionInput, ConversationWorkflow


log = logging.getLogger("plnt_cloud.channels.web_ws")
router = APIRouter()


TASK_QUEUE = os.environ.get("PLNT_CLOUD_TASK_QUEUE", "plnt-cloud-default")
TEMPORAL_ADDR = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NS = os.environ.get("TEMPORAL_NAMESPACE", "default")
POLL_INTERVAL_S = float(os.environ.get("PLNT_CLOUD_WS_POLL_S", "0.25"))


_client: Client | None = None


async def get_client() -> Client:
    """Lazy, process-wide Temporal client."""
    global _client
    if _client is None:
        _client = await Client.connect(TEMPORAL_ADDR, namespace=TEMPORAL_NS)
    return _client


def _workflow_id(tenant_id: str, user_id: str, session_id: str) -> str:
    return f"session:{tenant_id}:{user_id}:{session_id}"


async def _start_or_attach_session(
    client: Client, wf_id: str, inp: SessionInput,
) -> WorkflowHandle:
    """Start a new ConversationWorkflow or attach to an in-flight one.

    Workflow IDs are deterministic per (tenant, user, session); when the user
    reconnects to the same session we want the same long-lived Workflow, not
    a duplicate. start_workflow raises ALREADY_EXISTS on conflict — we catch
    that and return a handle to the existing run.
    """
    try:
        return await client.start_workflow(
            ConversationWorkflow.run,
            inp,
            id=wf_id,
            task_queue=TASK_QUEUE,
        )
    except WorkflowAlreadyStartedError:
        # Same (tenant, user, session) reconnecting → resume the existing run.
        return client.get_workflow_handle(wf_id)
    except RPCError as e:
        if e.status == RPCStatusCode.ALREADY_EXISTS:
            return client.get_workflow_handle(wf_id)
        raise


@router.websocket("/v1/ws/{tenant_id}/{session_id}")
async def ws_handler(
    ws: WebSocket,
    tenant_id: str,
    session_id: str,
    user_id: str = Query(default=""),
    force_backend: str = Query(default=""),
    key: str = Query(default=""),
) -> None:
    """One WebSocket connection per browser tab.

    Authentication: the tenant's API key must match (`?key=<token>`). The
    key is issued at provisioning time via POST /v1/admin/tenants and
    rotated via POST /v1/admin/tenants/{tid}/rotate-key.

    The Workflow's lifetime is the SESSION (not the connection) — a user
    can reconnect and resume the same conversation. We use deterministic
    Workflow IDs derived from (tenant, user, session) so re-attach is a
    no-op when the Workflow is already running.
    """
    # ── auth ──
    from surface.admin import verify_tenant_key
    if not verify_tenant_key(tenant_id, key):
        # WS close code 1008 = policy violation.
        await ws.close(code=1008, reason="invalid or missing tenant api key")
        log.warning("ws auth failed tenant=%s session=%s", tenant_id, session_id)
        return

    if not user_id:
        # Anonymous slice-1 path: derive a stable per-session user id.
        user_id = f"anon-{session_id}"

    await ws.accept()
    log.info("ws connected tenant=%s user=%s session=%s", tenant_id, user_id, session_id)

    client = await get_client()
    wf_id = _workflow_id(tenant_id, user_id, session_id)

    handle = await _start_or_attach_session(
        client, wf_id,
        SessionInput(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            force_backend=force_backend or None,
        ),
    )

    await ws.send_json({"event": "session_started", "workflow_id": wf_id})

    stop = asyncio.Event()

    async def inbound() -> None:
        """Forward client messages → workflow signals."""
        try:
            while not stop.is_set():
                msg = await ws.receive_text()
                if not msg:
                    continue
                await handle.signal("user_message", msg)
                await ws.send_json({"event": "ack", "received_chars": len(msg)})
        except WebSocketDisconnect:
            stop.set()
        except Exception as e:  # noqa: BLE001
            log.exception("inbound loop error")
            stop.set()
            try:
                await ws.send_json({"event": "error", "where": "inbound", "detail": str(e)})
            except Exception:
                pass

    async def outbound() -> None:
        """Poll workflow.replies_since → forward over WS."""
        last_seq = 0
        try:
            while not stop.is_set():
                try:
                    replies: list[dict[str, Any]] = await handle.query(
                        "replies_since", last_seq,
                    )
                except Exception as e:  # noqa: BLE001
                    log.warning("query failed: %s", e)
                    await asyncio.sleep(POLL_INTERVAL_S * 2)
                    continue
                for r in replies:
                    await ws.send_json({
                        "event": "reply",
                        "seq": r["seq"],
                        "role": r["role"],
                        "content": r["content"],
                    })
                    if int(r["seq"]) > last_seq:
                        last_seq = int(r["seq"])
                await asyncio.sleep(POLL_INTERVAL_S)
        except WebSocketDisconnect:
            stop.set()
        except Exception as e:  # noqa: BLE001
            log.exception("outbound loop error")
            stop.set()
            try:
                await ws.send_json({"event": "error", "where": "outbound", "detail": str(e)})
            except Exception:
                pass

    inb = asyncio.create_task(inbound())
    out = asyncio.create_task(outbound())
    try:
        await stop.wait()
    finally:
        for t in (inb, out):
            if not t.done():
                t.cancel()
        try:
            await ws.close()
        except Exception:
            pass
        log.info("ws closed tenant=%s user=%s session=%s last_seq=N/A",
                 tenant_id, user_id, session_id)
