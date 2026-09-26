"""Temporal worker bootstrap.

A single worker process hosts all of plnt-cloud's Workflows + Activities for
one Temporal namespace. Run one worker per (tenant) namespace in production;
in dev a single default-namespace worker is enough.

Run:
    python -m workflows.worker
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions

from workflows.session import ConversationWorkflow


TASK_QUEUE = os.environ.get("PLNT_CLOUD_TASK_QUEUE", "plnt-cloud-default")
TEMPORAL_ADDR = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NS = os.environ.get("TEMPORAL_NAMESPACE", "default")
STUB_ACTIVITY = os.environ.get("PLNT_CLOUD_STUB_ACTIVITY", "").lower() in ("1", "true", "yes")


def _activities():
    """Return the list of Activity callables to register with this worker.

    Two activity names are used across slices 1+2:
      * `run_microagent` — the micro-agent dispatcher (real or stub)
      * `notify_booking` — the saga's notification step (real or stub)

    PLNT_CLOUD_STUB_ACTIVITY=1 → stubs (slice 1/2 demo without LLM).
    Otherwise → real activities (LLM-driven, real notification adapters).
    """
    if STUB_ACTIVITY:
        from workflows.stub_activities import stub_run_microagent, stub_notify_booking
        return [stub_run_microagent, stub_notify_booking]
    from workflows.activities import (
        run_microagent, notify_booking, create_order, cancel_order,
    )
    return [run_microagent, notify_booking, create_order, cancel_order]


async def main() -> None:
    logging.basicConfig(
        level=os.environ.get("PLNT_CLOUD_LOG", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    log = logging.getLogger("plnt_cloud.worker")
    log.info("connecting to Temporal at %s (namespace=%s) stub=%s",
             TEMPORAL_ADDR, TEMPORAL_NS, STUB_ACTIVITY)

    client = await Client.connect(TEMPORAL_ADDR, namespace=TEMPORAL_NS)

    acts = _activities()
    # The default workflow sandbox blocks httpx (it touches urllib.request),
    # which the activity-side micro-agents drag in. Workflow code never
    # actually calls httpx — the activities do — but the sandbox loads the
    # whole import chain to validate determinism. Mark the offenders as
    # passthrough so the sandbox doesn't re-evaluate them on each activation.
    restrictions = SandboxRestrictions.default.with_passthrough_modules(
        "httpx", "httpcore", "h11", "h2", "hpack", "anyio", "sniffio",
        "openai", "sqlite3",
        "plnt", "workflows.activities", "workflows.bookings_store",
        "services", "services.places", "tenancy", "tenancy.factory",
        "memory", "memory.memori_adapter", "memory.preload",
        # MA-P1: agent loop + tool registry are activity-side; the sandbox
        # would otherwise re-validate their httpx/sqlite imports every
        # workflow activation. Forgetting any of these = silent
        # RestrictedWorkflowAccessError → chat returns no replies.
        "microagents", "microagents.loader", "microagents.agent_loop",
        "microagents.tools", "microagents.tools.places",
        "microagents.tools.bookings", "microagents.tools.notify",
        # MA-P4/P5: multi-service orders + real notify + provider fan-out.
        # Every module the activities layer touches must be here or the
        # sandbox rejects the imports at workflow activation time.
        "services.orders_store", "services.catalogue", "services.doc_chunk",
        "services.push_tokens", "services.expo_push",
        "services.business_owners", "services.installed_agents",
        "providers", "providers.base", "providers.resy", "providers.registry",
    )
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ConversationWorkflow],
        activities=acts,
        workflow_runner=SandboxedWorkflowRunner(restrictions=restrictions),
    )

    log.info("worker ready on task_queue=%s activities=%s",
             TASK_QUEUE, [a.__name__ for a in acts])

    stop = asyncio.Event()

    def _on_signal(*_: object) -> None:
        log.info("shutdown signal received")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            # Windows
            signal.signal(sig, lambda *_: _on_signal())

    async with worker:
        await stop.wait()
    log.info("worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
