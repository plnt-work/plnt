"""LocalExecutor: runs tenant sessions in-process, with a durable event log.

One call to `send()` is one *turn*. A session runs in one of two modes:

  agent   the session is bound to one installed bundle, which answers every
          message with its own tools (fast: no planning call);
  parent  no bundle is fixed. The parent (plnt.agent.parent) reads the
          message, decides between replying, asking, or running one or more
          agents, runs them (in parallel where independent, chained where
          one depends on another), and merges their results into one reply.

Everything a turn does is appended to the tenant's SQLite event log with
the agent that did it, so clients can stream it, resume after a disconnect,
and show what the parent decided and what each agent did.

Per-tenant guarantees enforced here:
  * the tenant's own bundle versions, config, secrets and model
  * filesystem tools confined to <tenant>/work/<session>/
  * token and wall-clock budgets per agent from its bundle's [budget]
  * the ACC loop detector and manual `kill()` stop every agent of a run
  * usage (tokens, cost) recorded per model call; audit entry per turn
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from plnt.agent import ToolDef, filesystem_tools, run_agent
from plnt.agent import parent as parent_agent
from plnt.agent.parent import AgentPlan, ParentError, Specialist
from plnt.bundles.bundle import Bundle, BundleError
from plnt.bundles.sdk import ToolContext
from plnt.control.acc import ACCMonitor
from plnt.models import ModelError, ModelProfile, ModelProvider, get_provider
from plnt.tenancy import installs
from plnt.tenancy.db import TenantDB
from plnt.tenancy.tenants import Tenant, TenantError, TenantStore

PARENT_ID = "parent"
MAX_PARALLEL_AGENTS = int(os.environ.get("PLNT_MAX_CONCURRENCY", "3"))


class SessionError(ValueError):
    pass


@dataclass
class _RunState:
    run_id: str
    stop_reason: str | None = None
    tokens: int = 0
    thread: threading.Thread | None = field(default=None, repr=False)


@dataclass
class _AgentSpec:
    """Everything one micro-agent needs for one turn."""

    id: str
    role: str
    intent: str
    system: str
    tools: list[ToolDef]
    profile: ModelProfile
    max_steps: int
    tokens: int
    wall_seconds: int
    bundle: str | None = None
    version: str | None = None
    require_tool: str | None = None
    response_schema: dict[str, Any] | None = None
    depends_on: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def to_event(self) -> dict[str, Any]:
        return {
            "parent_id": PARENT_ID,
            "role": self.role,
            "bundle": self.bundle,
            "version": self.version,
            "intent": self.intent,
            "depends_on": list(self.depends_on),
            "tools": [t.name for t in self.tools],
            "require_tool": self.require_tool,
            "model": self.profile.to_event(),
            "budget": {"tokens": self.tokens, "wall_seconds": self.wall_seconds,
                       "max_steps": self.max_steps},
            "config": self.config,
        }


def dynamic_roles_allowed() -> bool:
    """May the parent invent roles beyond the installed bundles? Off by default:
    an invented role gets shell access to the session's working folder."""
    return os.environ.get("PLNT_PARENT_DYNAMIC_ROLES", "").lower() in ("1", "true", "yes")


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

    def start_session(self, tenant_id: str, bundle: str = "", user_id: str = "") -> str:
        """Open a conversation. With `bundle`, that one agent answers every
        message; without it, the parent picks agents per message."""
        tenant = self.store.get(tenant_id)
        if bundle:
            installs.active(tenant, bundle)  # raises if not installed / disabled
        elif not any(i.enabled for i in installs.list_installed(tenant)):
            raise BundleError(f"tenant {tenant_id!r} has no enabled agents to run")
        sid = self.db(tenant).create_session(bundle, user_id)
        tenant.audit("session.started", session_id=sid, bundle=bundle or None,
                     mode="agent" if bundle else "parent", user_id=user_id)
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

    def transcript(self, tenant_id: str, sid: str) -> dict[str, Any]:
        tenant = self.store.get(tenant_id)
        self._session(tenant, sid)
        return self.db(tenant).transcript(sid)

    # ------------------------------------------------------------ specs

    def _tools(
        self, tenant: Tenant, sid: str, bundle: Bundle, config: dict[str, Any]
    ) -> list[ToolDef]:
        workdir = tenant.workdir(sid)
        builtin = filesystem_tools(workdir, [workdir])
        out = [builtin[n] for n in bundle.builtin_tools]
        data_dir = tenant.home / "data" / bundle.slug
        data_dir.mkdir(parents=True, exist_ok=True)
        ctx = ToolContext(
            tenant_id=tenant.id,
            session_id=sid,
            bundle=bundle.slug,
            config=dict(config),
            _secrets=tenant.secret_values(),
            data_dir=data_dir,
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

    def _spec_for_install(
        self, tenant: Tenant, sid: str, slug: str, *, agent_id: str, intent: str,
        depends_on: list[str] | None = None,
    ) -> _AgentSpec:
        inst = installs.active(tenant, slug)
        bundle = inst.load()
        missing = bundle.missing_secrets(set(tenant.secret_names()))
        if missing:
            raise SessionError(f"tenant has not set required secrets {missing} for {slug}")
        rt, budget = bundle.manifest.runtime, bundle.manifest.budget
        return _AgentSpec(
            id=agent_id,
            role=slug,
            intent=intent,
            system=bundle.render_prompt(inst.config),
            tools=self._tools(tenant, sid, bundle, inst.config),
            profile=tenant.model_profile(rt.model_hint),
            max_steps=rt.max_steps,
            tokens=budget.tokens,
            wall_seconds=budget.wall_seconds,
            bundle=slug,
            version=inst.version,
            require_tool=rt.require_tool,
            response_schema=bundle.manifest.response_schema,
            depends_on=list(depends_on or []),
            config=dict(inst.config),
        )

    def _spec_for_role(
        self, tenant: Tenant, sid: str, plan: AgentPlan
    ) -> _AgentSpec:
        """An invented role: the parent's persona, search + execute in the
        session's working folder, default budget."""
        workdir = tenant.workdir(sid)
        builtin = filesystem_tools(workdir, [workdir])
        system = (
            f"You are {plan.role}, a single-purpose agent created by the parent for one "
            "task. You can search files and run commands inside your working folder "
            "only. Do the task, then answer with what you found or did, briefly."
        )
        return _AgentSpec(
            id=plan.id,
            role=plan.role,
            intent=plan.intent,
            system=system,
            tools=list(builtin.values()),
            profile=tenant.model_profile("small"),
            max_steps=int(os.environ.get("PLNT_AGENT_MAX_STEPS", "6")),
            tokens=int(os.environ.get("PLNT_AGENT_TOKENS", "12000")),
            wall_seconds=int(os.environ.get("PLNT_AGENT_WALL_SECONDS", "120")),
            depends_on=list(plan.depends_on),
        )

    # ------------------------------------------------------------ the turn

    def _turn(self, tenant: Tenant, sid: str, text: str, state: _RunState) -> None:
        db = self.db(tenant)
        session = db.session(sid) or {}
        run_id = state.run_id

        def log(kind: str, agent_id: str = "", **payload: Any) -> None:
            db.append(sid, kind, payload, run_id=run_id, agent_id=agent_id)

        history = db.history(sid)  # before this message is appended
        db.set_status(sid, "running")
        log("user_message", text=text)
        started = time.monotonic()
        outcome = "error"
        try:
            if session.get("bundle"):
                outcome = self._turn_agent(tenant, sid, db, text, history, state, log)
            else:
                outcome = self._turn_parent(tenant, sid, db, text, history, state, log)
        except ModelError as e:
            log("run_error", stopped="error", error=e.args[0] if e.args else str(e), hint=e.hint)
        except ParentError as e:
            log("run_error", stopped="error", error=str(e), hint=e.hint, raw=e.raw)
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

    def _turn_agent(self, tenant, sid, db, text, history, state, log) -> str:
        """Single-agent session: the bound bundle answers; no parent."""
        slug = db.session(sid)["bundle"]
        spec = self._spec_for_install(tenant, sid, slug, agent_id=slug, intent=text)
        log("run_started", mode="agent", bundle=spec.bundle, version=spec.version,
            tools=[t.name for t in spec.tools], model=spec.profile.to_event())
        res = self._run_micro(tenant, sid, db, state, spec, history, text, {}, log,
                              finish_event=False)
        if res["stopped"] == "final":
            log("assistant_message", agent_id=spec.id, text=res["answer"], source="agent",
                output=res["output"], agents=[spec.id])
            return "ok"
        log("run_error", stopped=res["stopped"], error=res["error"], hint=res["hint"])
        return res["stopped"]

    def _turn_parent(self, tenant, sid, db, text, history, state, log) -> str:
        """Parent session: decide, run the chosen agents, merge."""
        specialists: list[Specialist] = []
        for slug in sorted({i.slug for i in installs.list_installed(tenant) if i.enabled}):
            inst = installs.active(tenant, slug)
            b = inst.load()
            specialists.append(Specialist(
                slug=slug, version=inst.version, description=b.manifest.meta.description,
                tools=list(b.manifest.runtime.tools),
            ))
        profile = tenant.model_profile("small")
        provider = self.provider_factory(profile)
        dynamic = dynamic_roles_allowed()
        log("run_started", mode="parent", model=profile.to_event(),
            specialists=[s.slug for s in specialists], dynamic_roles=dynamic)

        pemit = self._emit_for(tenant, sid, db, state, log, PARENT_ID, PARENT_ID, profile)
        try:
            decision = parent_agent.decide(
                provider, text=text, history=history, specialists=specialists,
                business=tenant.name or tenant.id, dynamic_roles=dynamic, emit=pemit,
                timeout=profile.timeout,
            )
        except ParentError as e:
            if len(specialists) != 1:
                raise
            # One specialist installed and the model gave no usable plan: run it.
            log("parent_decision", agent_id=PARENT_ID, decision="agents",
                reason=f"fallback: {e}", reply="",
                agents=[{"id": specialists[0].slug, "role": specialists[0].slug,
                         "bundle": specialists[0].slug, "intent": text, "depends_on": []}])
            decision = parent_agent.Decision(kind="agents", reason=str(e), agents=[
                AgentPlan(id=specialists[0].slug, role=specialists[0].slug, intent=text,
                          bundle=specialists[0].slug)])
        else:
            log("parent_decision", agent_id=PARENT_ID, decision=decision.kind,
                reason=decision.reason, reply=decision.reply,
                agents=[a.to_event() for a in decision.agents])

        if decision.kind in ("chat", "clarify"):
            log("assistant_message", agent_id=PARENT_ID, text=decision.reply,
                source="parent" if decision.kind == "chat" else "clarify", agents=[])
            return "ok"

        specs: dict[str, _AgentSpec] = {}
        for plan in decision.agents:
            if plan.bundle:
                specs[plan.id] = self._spec_for_install(
                    tenant, sid, plan.bundle, agent_id=plan.id,
                    intent=plan.intent or text, depends_on=plan.depends_on)
            else:
                specs[plan.id] = self._spec_for_role(tenant, sid, plan)
        for spec in specs.values():
            log("agent_spawned", agent_id=spec.id, **spec.to_event())

        # Run in dependency order: everything ready runs in parallel.
        results: dict[str, dict[str, Any]] = {}
        remaining = dict(specs)
        while remaining and not state.stop_reason:
            ready = [s for s in remaining.values() if all(d in results for d in s.depends_on)]
            if not ready:
                log("run_error", stopped="error",
                    error="the plan's dependencies cannot be resolved", hint="")
                break
            workers = max(1, min(MAX_PARALLEL_AGENTS, len(ready)))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = {
                    pool.submit(
                        self._run_micro, tenant, sid, db, state, s, history, text,
                        {d: results[d] for d in s.depends_on}, log,
                    ): s
                    for s in ready
                }
                for fut, s in futs.items():
                    results[s.id] = fut.result()
                    del remaining[s.id]
        for s in remaining.values():
            log("agent_finished", agent_id=s.id, outcome="skipped", answer=None,
                error=state.stop_reason or "not run", tokens=0, wall_seconds=0)

        plans = {a.id: a for a in decision.agents}
        done = [(plans[aid], r) for aid, r in results.items()]
        ok = [(p, r) for p, r in done if r["stopped"] == "final"]
        if not ok:
            first = next(iter(results.values()), None)
            log("run_error", stopped=first["stopped"] if first else "error",
                error=first["error"] if first else "no agent ran",
                hint=first["hint"] if first else "")
            return first["stopped"] if first else "error"
        if len(done) == 1:
            plan, res = ok[0]
            log("assistant_message", agent_id=plan.id, text=res["answer"], source="agent",
                output=res["output"], agents=[plan.id])
            return "ok"
        reply = parent_agent.synthesize(
            provider, text=text, results=done, business=tenant.name or tenant.id,
            emit=pemit, timeout=profile.timeout,
        )
        log("assistant_message", agent_id=PARENT_ID, text=reply, source="synth",
            agents=[p.id for p, _ in done])
        return "ok"

    def _emit_for(self, tenant, sid, db, state, log, agent_id, usage_key, profile):
        """An emit() for one agent: logs with its id and books its usage."""
        run_id = state.run_id

        def emit(kind: str, **payload: Any) -> None:
            log(kind, agent_id=agent_id, **payload)
            if kind == "model_result":
                db.record_usage(
                    session_id=sid,
                    run_id=run_id,
                    bundle=usage_key,
                    provider=str(payload.get("provider") or profile.provider),
                    model=str(payload.get("model") or profile.model),
                    prompt_tokens=int(payload.get("prompt_tokens") or 0),
                    completion_tokens=int(payload.get("completion_tokens") or 0),
                    cost_usd=float(payload.get("cost_usd") or 0.0),
                )
                state.tokens += int(payload.get("tokens") or 0)

        return emit

    def _run_micro(
        self, tenant, sid, db, state, spec: _AgentSpec, history, text, upstream, log,
        finish_event: bool = True,
    ) -> dict[str, Any]:
        """Run one agent for this turn. Returns its result and, in parent mode,
        logs agent_finished with what it answered so the transcript is self-contained."""
        started = time.monotonic()
        acc = ACCMonitor(kill_fn=lambda _agent, why: self._stop(state, why))
        agent_tokens = {"n": 0}
        base_emit = self._emit_for(
            tenant, sid, db, state, log, spec.id, spec.bundle or f"role:{spec.role}", spec.profile
        )

        def emit(kind: str, **payload: Any) -> None:
            base_emit(kind, **payload)
            if kind == "model_result":
                agent_tokens["n"] += int(payload.get("tokens") or 0)
                if agent_tokens["n"] > spec.tokens:
                    self._stop(
                        state, f"token budget exceeded ({agent_tokens['n']} > {spec.tokens})"
                    )
            elif kind == "tool_call":
                acc.observe({"kind": "tool_call", "agent_id": spec.id, "payload": payload})

        user = text
        if spec.intent and spec.intent.strip() != text.strip():
            user = f"[The parent asked you to: {spec.intent}]\n\n{text}"
        if upstream:
            notes = "\n\n".join(
                f"[Result from {aid}]: {r.get('answer') or r.get('error') or '(nothing)'}"
                for aid, r in upstream.items()
            )
            user = f"{user}\n\n{notes}"
        provider = self.provider_factory(spec.profile)
        try:
            result = run_agent(
                system=spec.system,
                messages=[{"role": "system", "content": spec.system}, *history,
                          {"role": "user", "content": user}],
                tools=spec.tools,
                provider=provider,
                max_steps=spec.max_steps,
                response_schema=spec.response_schema,
                deadline=started + spec.wall_seconds,
                emit=emit,
                native_tools=spec.profile.native_tools,
                should_stop=lambda: state.stop_reason,
                require_tool=spec.require_tool,
            )
        except ModelError as e:
            res = {"answer": "", "output": None, "stopped": "error",
                   "error": e.args[0] if e.args else str(e), "hint": e.hint}
        else:
            res = {
                "answer": result.answer,
                "output": result.output if isinstance(result.output, dict) else None,
                "stopped": result.stopped,
                "error": result.error,
                "hint": result.error_hint,
            }
        res["tokens"] = agent_tokens["n"]
        res["wall_seconds"] = round(time.monotonic() - started, 3)
        if finish_event:
            log("agent_finished", agent_id=spec.id,
                outcome="ok" if res["stopped"] == "final" else res["stopped"],
                answer=res["answer"] if res["stopped"] == "final" else None,
                error=res["error"], hint=res["hint"], tokens=res["tokens"],
                wall_seconds=res["wall_seconds"])
        return res

    @staticmethod
    def _stop(state: _RunState, reason: str) -> bool:
        if state.stop_reason is None:
            state.stop_reason = reason
        return True
