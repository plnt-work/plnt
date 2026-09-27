"""Public playground: anonymous visitors chat with real demo tenants.

Enabled with `plnt serve --playground`. It seeds demo tenants, each bound to a
sample workspace with the developer bundles installed, then exposes a narrow
anonymous API:

  GET  /v1/playground                          demo tenants, their agents, limits
  POST /v1/playground/sessions                 {tenant, bundle?} -> {session_id, token}
  GET  /v1/playground/sessions/{sid}/transcript?token=…         turns (see plnt.tenancy.transcript)
  POST /v1/playground/sessions/{sid}/messages  {text}          (token required)
  GET  /v1/playground/sessions/{sid}/stream?token=…             SSE (EventSource-friendly)
  POST /v1/playground/sessions/{sid}/kill                       (token required)

Guards: only seeded demo tenants are reachable; every session has its own
capability token (HMAC), so visitors cannot read each other's sessions; each
session works on its own copy of the demo workspace; the executor is
read-only unless PLNT_PLAYGROUND_EXECUTE=1 (no shell, no writes); per-IP rate
limits; a global daily token cap; short messages only. No operator or tenant
routes are opened by this module.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import shutil
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from plnt.bundles import catalog
from plnt.bundles.bundle import BUILTIN_TOOLS, READ_ONLY_TOOLS, BundleError
from plnt.executors import LocalExecutor, SessionError
from plnt.tenancy import installs
from plnt.tenancy import workspace as ws
from plnt.tenancy.tenants import TenantNotFound, TenantStore

MAX_MESSAGE_CHARS = 1000
WORKDIR_TTL_SECONDS = 24 * 3600

# Demo workspaces (demo/workspaces/<id>): small sample projects visitors can
# point the parent and its agents at. Each demo tenant works on one of them.
DEMO_TENANTS: list[dict[str, Any]] = [
    {
        "id": "notes-api",
        "name": "notes-api",
        "workspace": "demo:notes-api",
        "blurb": "A small FastAPI notes service. No tests, a couple of real bugs.",
        "tasks": [
            "Explain how this project is put together.",
            "Audit app/store.py and app/main.py for bugs.",
            "Write tests for the notes store.",
            "Review the API for authorization problems and write a changelog entry for the fixes.",
        ],
        "installs": {
            "repo-explainer": {},
            "code-reviewer": {"focus": "bugs"},
            "test-writer": {"framework": "pytest"},
            "changelog-writer": {},
        },
    },
    {
        "id": "cli-tool",
        "name": "cli-tool",
        "workspace": "demo:cli-tool",
        "blurb": "A command-line todo list with a date bug and one existing test.",
        "tasks": [
            "What does this tool do and how do I run it?",
            "Find the bug in the date handling.",
            "Add tests for todo/dates.py.",
            "Review todo/cli.py for style and write release notes for 1.2.0.",
        ],
        "installs": {
            "repo-explainer": {"audience": "new-contributor"},
            "code-reviewer": {"focus": "all"},
            "test-writer": {"framework": "pytest"},
            "changelog-writer": {"style": "release-notes"},
        },
    },
]


def seed_demo(store: TenantStore) -> None:
    """Create (or refresh the config of) the demo tenants. Idempotent."""
    bundles, _ = catalog.available()
    for spec in DEMO_TENANTS:
        try:
            tenant = store.get(spec["id"])
        except TenantNotFound:
            tenant, _ = store.create(spec["id"], spec["name"])
        for slug, cfg in spec["installs"].items():
            if slug not in bundles:
                raise BundleError(f"playground needs bundle {slug!r} in the catalog")
            installs.install(tenant, bundles[slug], cfg)


def sweep_workdirs(store: TenantStore, ttl: float = WORKDIR_TTL_SECONDS) -> int:
    """Delete demo sessions' workspace copies older than `ttl`. Returns how many."""
    cutoff = time.time() - ttl
    removed = 0
    for spec in DEMO_TENANTS:
        try:
            tenant = store.get(spec["id"])
        except TenantNotFound:
            continue
        work = tenant.home / "work"
        if not work.is_dir():
            continue
        for d in work.iterdir():
            try:
                if d.is_dir() and d.stat().st_mtime < cutoff:
                    shutil.rmtree(d, ignore_errors=True)
                    removed += 1
            except OSError:
                continue
    return removed


# ------------------------------------------------------------------ limits


class RateLimiter:
    """Sliding-window counter per (key, bucket)."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, bucket: str, limit: int, window_s: float) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[(key, bucket)]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


@dataclass
class PlaygroundLimits:
    sessions_per_10min: int = int(os.environ.get("PLNT_PLAYGROUND_SESSIONS_PER_10MIN", "10"))
    messages_per_10min: int = int(os.environ.get("PLNT_PLAYGROUND_MESSAGES_PER_10MIN", "30"))
    daily_tokens: int = int(os.environ.get("PLNT_PLAYGROUND_DAILY_TOKENS", "2000000"))


class SessionCreate(BaseModel):
    tenant: str
    bundle: str = ""  # empty: the tenant's parent picks agents per message


class MessageBody(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


def _client_ip(request: Request) -> str:
    # Behind a proxy, set PLNT_TRUST_PROXY=1 so X-Forwarded-For is honoured.
    if os.environ.get("PLNT_TRUST_PROXY") == "1":
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def playground_router(
    store: TenantStore, executor: LocalExecutor, limits: PlaygroundLimits | None = None
) -> APIRouter:
    limits = limits or PlaygroundLimits()
    key = secrets.token_bytes(32)  # session tokens die with the process
    limiter = RateLimiter()
    demo_ids = {t["id"] for t in DEMO_TENANTS}
    day_tokens = {"day": time.strftime("%Y-%m-%d"), "used": 0}
    r = APIRouter(prefix="/v1/playground", tags=["playground"])

    def token_for(tenant: str, sid: str) -> str:
        return hmac.new(key, f"{tenant}/{sid}".encode(), hashlib.sha256).hexdigest()[:32]

    def check(tenant: str, sid: str, token: str) -> None:
        if tenant not in demo_ids or not hmac.compare_digest(token, token_for(tenant, sid)):
            raise HTTPException(404, "unknown playground session")

    def tokens_used_today() -> int:
        today = time.strftime("%Y-%m-%d")
        if day_tokens["day"] != today:
            day_tokens.update(day=today, used=0)
        return day_tokens["used"]

    def add_usage(tenant: str, sid: str, after_seq: int) -> None:
        for e in executor.events_since(tenant, sid, after_seq):
            if e["kind"] == "run_finished":
                tokens_used_today()
                day_tokens["used"] += int(e["payload"].get("tokens") or 0)

    def split(sid_full: str) -> tuple[str, str]:
        tenant, _, sid = sid_full.partition(".")
        if not sid:
            raise HTTPException(404, "unknown playground session")
        return tenant, sid

    @r.get("")
    def info() -> dict[str, Any]:
        out = []
        for spec in DEMO_TENANTS:
            try:
                tenant = store.get(spec["id"])
            except TenantNotFound:
                continue
            agents = []
            for inst in installs.list_installed(tenant):
                b = inst.load()
                tools = list(b.manifest.runtime.tools)
                if executor.read_only:
                    tools = [t for t in tools if t in READ_ONLY_TOOLS or t not in BUILTIN_TOOLS]
                agents.append(
                    {
                        "slug": inst.slug,
                        "version": inst.version,
                        "description": b.manifest.meta.description,
                        "tools": tools,
                        "require_tool": b.manifest.runtime.require_tool,
                        "config": inst.config,
                    }
                )
            name = spec["workspace"].removeprefix("demo:")
            try:
                root = ws.demo_root(name)
                files = sum(1 for p in root.rglob("*") if p.is_file())
            except ws.WorkspaceError:
                files = 0
            out.append(
                {
                    "id": tenant.id,
                    "name": tenant.name,
                    "blurb": spec["blurb"],
                    "workspace": {
                        "name": name,
                        "description": spec["blurb"],
                        "file_count": files,
                        "suggested_tasks": list(spec["tasks"]),
                    },
                    "agents": agents,
                }
            )
        used = tokens_used_today()
        try:
            profile = store.get(DEMO_TENANTS[0]["id"]).model_profile("small").to_event()
        except Exception:  # noqa: BLE001 — info must not fail because no model is set
            profile = None
        return {
            "tenants": out,
            "parent": {
                "description": "Start a session without a bundle and the workspace's parent "
                "decides, per message, which agents run and what each one does.",
                "dynamic_roles": executor.dynamic_roles,
            },
            "execute_enabled": not executor.read_only,
            "models": (
                [{"id": profile["model"], "label": profile["model"],
                  "provider": profile["provider"]}] if profile else []
            ),
            "limits": {
                "max_message_chars": MAX_MESSAGE_CHARS,
                "messages_per_10min": limits.messages_per_10min,
                "daily_tokens_left": max(0, limits.daily_tokens - used),
            },
        }

    @r.post("/sessions", status_code=201)
    def create(body: SessionCreate, request: Request) -> dict[str, str]:
        if body.tenant not in demo_ids:
            raise HTTPException(404, "not a playground tenant")
        if not limiter.allow(_client_ip(request), "session", limits.sessions_per_10min, 600):
            raise HTTPException(429, "too many new sessions; try again in a few minutes")
        sweep_workdirs(store)
        spec = next(t for t in DEMO_TENANTS if t["id"] == body.tenant)
        try:
            sid = executor.start_session(
                body.tenant, body.bundle, user_id="playground", workspace=spec["workspace"]
            )
        except BundleError as e:
            raise HTTPException(404, str(e)) from None
        except ws.WorkspaceError as e:
            raise HTTPException(503, f"demo workspace unavailable: {e}") from None
        return {"session_id": f"{body.tenant}.{sid}", "token": token_for(body.tenant, sid)}

    @r.post("/sessions/{sid_full}/messages", status_code=202)
    def message(
        sid_full: str, body: MessageBody, request: Request, token: str = ""
    ) -> dict[str, str]:
        tenant, sid = split(sid_full)
        check(tenant, sid, token)
        if tokens_used_today() >= limits.daily_tokens:
            raise HTTPException(
                503,
                "the playground's daily model budget is used up; "
                "try again tomorrow or run plnt locally",
            )
        if not limiter.allow(_client_ip(request), "message", limits.messages_per_10min, 600):
            raise HTTPException(429, "too many messages; try again in a few minutes")
        before = executor.events_since(tenant, sid)
        last = before[-1]["seq"] if before else 0
        try:
            run_id = executor.send(tenant, sid, body.text)
        except SessionError as e:
            raise HTTPException(409, str(e)) from None

        def account() -> None:
            executor.wait(tenant, sid, 300)
            add_usage(tenant, sid, last)

        threading.Thread(target=account, daemon=True).start()
        return {"run_id": run_id}

    @r.get("/sessions/{sid_full}/transcript")
    def transcript(sid_full: str, token: str = "") -> dict[str, Any]:
        tenant, sid = split(sid_full)
        check(tenant, sid, token)
        return executor.transcript(tenant, sid)

    @r.post("/sessions/{sid_full}/kill")
    def kill(sid_full: str, token: str = "") -> dict[str, bool]:
        tenant, sid = split(sid_full)
        check(tenant, sid, token)
        return {"killed": executor.kill(tenant, sid, "stopped by playground visitor")}

    @r.get("/sessions/{sid_full}/stream")
    async def stream(
        sid_full: str, request: Request, token: str = "", after: int = 0, until_idle: bool = False
    ) -> EventSourceResponse:
        tenant, sid = split(sid_full)
        check(tenant, sid, token)

        async def gen():
            last = after
            deadline = time.monotonic() + 600  # visitors reconnect; don't hold sockets forever
            while not await request.is_disconnected() and time.monotonic() < deadline:
                events = await asyncio.to_thread(executor.events_since, tenant, sid, last)
                for e in events:
                    last = e["seq"]
                    yield {"id": str(e["seq"]), "event": e["kind"], "data": json.dumps(e)}
                    if until_idle and e["kind"] == "run_finished":
                        return
                await asyncio.sleep(0.2)

        return EventSourceResponse(gen())

    return r
