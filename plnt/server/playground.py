"""Public playground: anonymous visitors chat with real demo tenants.

Enabled with `plnt serve --playground`. It seeds a few demo businesses, each
with its own installed bundles and config, then exposes a narrow anonymous API:

  GET  /v1/playground                          demo tenants, their agents, limits
  POST /v1/playground/sessions                 {tenant, bundle} -> {session_id, token}
  POST /v1/playground/sessions/{sid}/messages  {text}          (token required)
  GET  /v1/playground/sessions/{sid}/stream?token=…             SSE (EventSource-friendly)
  POST /v1/playground/sessions/{sid}/kill                       (token required)

Guards: only seeded demo tenants are reachable; every session has its own
capability token (HMAC), so visitors cannot read each other's conversations;
per-IP rate limits; a global daily token cap; short messages only. No
operator or tenant routes are opened by this module.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from plnt.bundles import catalog
from plnt.bundles.bundle import BundleError
from plnt.executors import LocalExecutor, SessionError
from plnt.tenancy import installs
from plnt.tenancy.tenants import TenantNotFound, TenantStore

MAX_MESSAGE_CHARS = 500

_WEEK_HOURS = {
    f"hours_{d}": "12:00-15:00, 18:00-22:30" for d in ("tue", "wed", "thu", "fri", "sat")
}

DEMO_TENANTS: list[dict[str, Any]] = [
    {
        "id": "luigis-bistro",
        "name": "Luigi's Bistro",
        "blurb": "Italian restaurant. Takes table bookings and answers questions.",
        "installs": {
            "booking-desk": {
                "business_name": "Luigi's Bistro",
                "handoff_contact": "hello@luigis.example",
                "timezone": "Europe/Rome",
                "tables_per_slot": 2,
                "max_party_size": 6,
                **_WEEK_HOURS,
                "hours_sun": "12:00-15:00",
            },
            "support-desk": {
                "business_name": "Luigi's Bistro",
                "handoff_contact": "hello@luigis.example",
                "faq": [
                    {
                        "q": "When are you open?",
                        "a": "Tuesday to Saturday 12-3pm and 6-10:30pm, Sunday lunch 12-3pm. "
                        "Closed Mondays.",
                    },
                    {
                        "q": "Do you have vegan or gluten-free options?",
                        "a": "Yes: a vegan risotto and gluten-free pasta on request.",
                    },
                    {
                        "q": "Is there parking?",
                        "a": "Free parking behind the restaurant, 12 spaces.",
                    },
                ],
            },
        },
    },
    {
        "id": "bright-smile-dental",
        "name": "Bright Smile Dental",
        "blurb": "Dental clinic. Answers patient questions from its own FAQ only.",
        "installs": {
            "support-desk": {
                "business_name": "Bright Smile Dental",
                "handoff_contact": "front-desk@brightsmile.example",
                "tone": "formal",
                "faq": [
                    {"q": "When are you open?", "a": "Monday to Friday, 8am to 4pm."},
                    {
                        "q": "Do you take emergency patients?",
                        "a": "Yes, call before 10am for a same-day emergency slot.",
                    },
                    {
                        "q": "How much is a check-up?",
                        "a": "A check-up with cleaning is $95 without insurance.",
                    },
                ],
            },
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
    bundle: str


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
                agents.append(
                    {
                        "slug": inst.slug,
                        "version": inst.version,
                        "description": b.manifest.meta.description,
                        "tools": b.manifest.runtime.tools,
                        "require_tool": b.manifest.runtime.require_tool,
                        "config": inst.config,
                    }
                )
            out.append(
                {"id": tenant.id, "name": tenant.name, "blurb": spec["blurb"], "agents": agents}
            )
        used = tokens_used_today()
        return {
            "tenants": out,
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
            raise HTTPException(429, "too many new conversations; try again in a few minutes")
        try:
            sid = executor.start_session(body.tenant, body.bundle, user_id="playground")
        except BundleError as e:
            raise HTTPException(404, str(e)) from None
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
