"""LocalExecutor — runs tenant sessions in-process, with a durable event log.

One call to `send()` is one *turn*: the tenant's installed bundle answers
one user message, calling tools as needed. Everything the turn does is
appended to the tenant's SQLite event log, so clients can stream it
(`events_since`) and resume after a disconnect.

Per-tenant guarantees enforced here:
  * the tenant's own bundle version, config, secrets and model
  * filesystem tools confined to <tenant>/work/<session>/
  * token and wall-clock budgets from the bundle's [budget]
  * the ACC loop detector and manual `kill()` stop a run between steps
  * usage (tokens, cost) recorded per model call; audit entry per turn

Temporal-backed durable execution (for multi-node deployments) is the
optional `plnt[temporal]` executor; this one is the default.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from plnt.agent import ToolDef, filesystem_tools, run_agent
from plnt.bundles.bundle import Bundle, BundleError
from plnt.bundles.sdk import ToolContext
from plnt.control.acc import ACCMonitor
from plnt.models import ModelError, ModelProfile, ModelProvider, get_provider
from plnt.tenancy import installs
from plnt.tenancy.db import TenantDB
from plnt.tenancy.tenants import Tenant, TenantError, TenantStore


class SessionError(ValueError):
    pass


@dataclass
class _RunState:
    run_id: str
    stop_reason: str | None = None
    tokens: int = 0
    thread: threading.Thread | None = field(default=None, repr=False)


class LocalExecutor:
    def __init__(
        self,
        store: TenantStore | None = None,
        provider_factory: Callable[[ModelProfile], ModelProvider] | None = None,
    ):
        self.store = store or TenantStore()
        # Injectable for tests; defaults to the real providers.
        self.provider_factory = provider_factory or get_provider
        self._runs: dict[tuple[str, str], _RunState] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ helpers

    def db(self, tenant: Tenant) -> TenantDB:
        return TenantDB(tenant.home / "data.db")

    def _session(self, tenant: Tenant, sid: str) -> dict[str, Any]:
        row = self.db(tenant).session(sid)
        if row is None:
            raise SessionError(f"session {sid!r} not found for tenant {tenant.id!r}")
        return row

    # ------------------------------------------------------------ API

    def start_session(self, tenant_id: str, bundle: str, user_id: str = "") -> str:
        tenant = self.store.get(tenant_id)
        installs.active(tenant, bundle)  # raises if not installed / disabled
        sid = self.db(tenant).create_session(bundle, user_id)
        tenant.audit("session.started", session_id=sid, bundle=bundle, user_id=user_id)
        return sid

    def send(self, tenant_id: str, sid: str, text: str, *, wait: bool = False) -> str:
        """Start a turn. Returns its run_id; `wait=True` blocks until it finishes."""
        tenant = self.store.get(tenant_id)
        self._session(tenant, sid)
        key = (tenant_id, sid)
        with self._lock:
            cur = self._runs.get(key)
            if cur and cur.thread and cur.thread.is_alive():
                raise SessionError(f"session {sid} is already running {cur.run_id}")
            state = _RunState(run_id="r_" + uuid.uuid4().hex[:12])
            self._runs[key] = state
        t = threading.Thread(
            target=self._turn,
            args=(tenant, sid, text, state),
            name=f"plnt-{tenant_id}-{sid}",
            daemon=True,
        )
        state.thread = t
        t.start()
        if wait:
            t.join()
        return state.run_id

    def kill(self, tenant_id: str, sid: str, reason: str = "killed by operator") -> bool:
        state = self._runs.get((tenant_id, sid))
        if not state or not state.thread or not state.thread.is_alive():
            return False
        state.stop_reason = reason
        return True

    def wait(self, tenant_id: str, sid: str, timeout: float | None = None) -> None:
        state = self._runs.get((tenant_id, sid))
        if state and state.thread:
            state.thread.join(timeout)

    def events_since(self, tenant_id: str, sid: str, after: int = 0) -> list[dict[str, Any]]:
        tenant = self.store.get(tenant_id)
        self._session(tenant, sid)
        return self.db(tenant).events_since(sid, after)

    # ------------------------------------------------------------ the turn

    def _tools(
        self, tenant: Tenant, sid: str, bundle: Bundle, config: dict[str, Any]
    ) -> list[ToolDef]:
        workdir = tenant.workdir(sid)
        builtin = filesystem_tools(workdir, [workdir])
        out = [builtin[n] for n in bundle.builtin_tools]
        ctx = ToolContext(
            tenant_id=tenant.id,
            session_id=sid,
            bundle=bundle.slug,
            config=dict(config),
            _secrets=tenant.secret_values(),
        )
        for spec in bundle.tools.values():
            out.append(
                ToolDef(
                    name=spec.name,
                    description=spec.description,
                    parameters=spec.parameters,
                    fn=lambda args, s=spec: s.call(args, ctx),
                )
            )
        return out

    def _turn(self, tenant: Tenant, sid: str, text: str, state: _RunState) -> None:
        db = self.db(tenant)
        session = db.session(sid) or {}
        run_id = state.run_id
        history = db.history(sid)

        def log(kind: str, **payload: Any) -> None:
            db.append(sid, kind, payload, run_id=run_id)

        db.set_status(sid, "running")
        log("user_message", text=text)
        started = time.monotonic()
        outcome = "error"
        try:
            inst = installs.active(tenant, session.get("bundle", ""))
            bundle = inst.load()
            missing = bundle.missing_secrets(set(tenant.secret_names()))
            if missing:
                raise SessionError(f"tenant has not set required secrets {missing}")
            profile = tenant.model_profile(bundle.manifest.runtime.model_hint)
            provider = self.provider_factory(profile)
            log("run_started", bundle=bundle.slug, version=bundle.version, model=profile.to_event())

            budget = bundle.manifest.budget
            acc = ACCMonitor(kill_fn=lambda _agent, why: self._stop(state, why))

            def emit(kind: str, **payload: Any) -> None:
                log(kind, **payload)
                if kind == "model_result":
                    db.record_usage(
                        session_id=sid,
                        run_id=run_id,
                        bundle=bundle.slug,
                        provider=str(payload.get("provider") or profile.provider),
                        model=str(payload.get("model") or profile.model),
                        prompt_tokens=int(payload.get("prompt_tokens") or 0),
                        completion_tokens=int(payload.get("completion_tokens") or 0),
                        cost_usd=float(payload.get("cost_usd") or 0.0),
                    )
                    state.tokens += int(payload.get("tokens") or 0)
                    if state.tokens > budget.tokens:
                        self._stop(
                            state, f"token budget exceeded ({state.tokens} > {budget.tokens})"
                        )
                elif kind == "tool_call":
                    acc.observe({"kind": "tool_call", "agent_id": run_id, "payload": payload})

            system = bundle.render_prompt(inst.config)
            result = run_agent(
                system=system,
                messages=[
                    {"role": "system", "content": system},
                    *history,
                    {"role": "user", "content": text},
                ],
                tools=self._tools(tenant, sid, bundle, inst.config),
                provider=provider,
                max_steps=bundle.manifest.runtime.max_steps,
                response_schema=bundle.manifest.response_schema,
                deadline=started + budget.wall_seconds,
                emit=emit,
                native_tools=profile.native_tools,
                should_stop=lambda: state.stop_reason,
            )
            if result.stopped == "final":
                log(
                    "assistant_message",
                    text=result.answer,
                    output=result.output if isinstance(result.output, dict) else None,
                )
                outcome = "ok"
            else:
                outcome = result.stopped
                log("run_error", stopped=result.stopped, error=result.error, hint=result.error_hint)
        except ModelError as e:
            log("run_error", stopped="error", error=e.args[0] if e.args else str(e), hint=e.hint)
        except (BundleError, SessionError, TenantError) as e:
            log("run_error", stopped="error", error=str(e), hint="")
        except Exception as e:  # noqa: BLE001 — a turn must always end with an event
            log("run_error", stopped="crash", error=f"{type(e).__name__}: {e}", hint="")
        finally:
            elapsed = round(time.monotonic() - started, 3)
            log("run_finished", outcome=outcome, wall_seconds=elapsed, tokens=state.tokens)
            db.set_status(sid, "idle")
            tenant.audit(
                "run.finished",
                session_id=sid,
                run_id=run_id,
                outcome=outcome,
                tokens=state.tokens,
                wall_seconds=elapsed,
            )

    @staticmethod
    def _stop(state: _RunState, reason: str) -> bool:
        if state.stop_reason is None:
            state.stop_reason = reason
        return True
