"""The parent: the planner that runs before any agent in a conversation.

One model call decides what a message needs:

  chat      answer directly (greetings, thanks, "what can you do?")
  clarify   ask one pointed question before doing anything
  agents    run one or more agents: the tenant's installed bundles
            ("specialists"), or, when the tenant allows it, roles the parent
            invents for the task

When more than one agent ran, a second call merges their results into one
reply. The executor records both calls as `parent` events, so a console can
show what the parent decided and why.

The parent never answers a question a specialist exists for: that is the
specialist's job, with its tools and guardrails.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from plnt.models import ModelProvider

MAX_AGENTS = 4
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.M)


class ParentError(ValueError):
    """The parent could not produce a usable decision."""

    def __init__(self, msg: str, raw: str = "", hint: str = ""):
        super().__init__(msg)
        self.raw = raw
        self.hint = hint


@dataclass(frozen=True)
class Specialist:
    """An installed bundle, as the parent sees it."""

    slug: str
    version: str
    description: str
    tools: list[str]


@dataclass
class AgentPlan:
    id: str
    role: str
    intent: str
    bundle: str | None = None  # a specialist slug, or None for an invented role
    depends_on: list[str] = field(default_factory=list)

    def to_event(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "bundle": self.bundle,
            "intent": self.intent,
            "depends_on": list(self.depends_on),
        }


@dataclass
class Decision:
    kind: str  # chat | clarify | agents
    reason: str = ""
    reply: str = ""
    agents: list[AgentPlan] = field(default_factory=list)


DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["chat", "clarify", "agents"]},
        "reason": {"type": "string"},
        "reply": {"type": "string"},
        "agents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "role": {"type": "string"},
                    "bundle": {"type": ["string", "null"]},
                    "intent": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "role", "intent"],
            },
        },
    },
    "required": ["kind", "reason"],
}


def decision_prompt(
    business: str, specialists: list[Specialist], dynamic_roles: bool
) -> str:
    lines = [
        f"You are the parent agent for {business}. You do not answer customers "
        "yourself, except for small talk. You decide which agents handle each "
        "message; the agents do the work with their own tools.",
        "",
        "Installed agents (specialists):",
    ]
    for s in specialists:
        tools = ", ".join(s.tools) or "no tools"
        lines.append(f'- "{s.slug}" (v{s.version}): {s.description} Tools: {tools}.')
    if not specialists:
        lines.append("- none")
    lines += [
        "",
        "Decide ONE of:",
        '- "chat": the message needs no work (greeting, thanks, asking what you can '
        'do). Put a short friendly reply in "reply". For "what can you do", describe '
        "what the installed agents handle.",
        '- "clarify": no agent can even start without something only the customer '
        'can supply. Put one pointed question in "reply". Do not clarify details an '
        "agent can ask for itself.",
        f'- "agents": run 1 to {MAX_AGENTS} agents. Use a specialist for anything it '
        'covers; set "bundle" to its slug and "role" to the same slug. Give each agent '
        "a focused \"intent\" in the customer's words. Agents without dependencies run "
        'in parallel; set "depends_on" (ids) when one needs another\'s result.',
    ]
    if dynamic_roles:
        lines += [
            "",
            "If no specialist covers part of the request, you may invent a "
            'single-purpose role: {"id": "kebab-id", "role": "kebab-name", "bundle": '
            'null, "intent": "..."}. An invented role can only read and run commands '
            "inside this conversation's working folder.",
        ]
    else:
        lines += [
            "",
            "Only installed specialists may run. If none fits the request, answer "
            'with "chat" and say what the installed agents can help with.',
        ]
    lines += [
        "",
        "Respond with one JSON object and nothing else:",
        '{"kind": "chat" | "clarify" | "agents", "reason": "<one sentence>", '
        '"reply": "<for chat/clarify>", "agents": [{"id": "...", "role": "...", '
        '"bundle": "<slug or null>", "intent": "...", "depends_on": []}]}',
    ]
    return "\n".join(lines)


def _parse_json(text: str) -> dict[str, Any] | None:
    text = _FENCE_RE.sub("", (text or "").strip()).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _kebab(s: str, fallback: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9-]+", "-", str(s).strip().lower()).strip("-")[:40]
    return s if _ID_RE.match(s) else fallback


def parse_decision(
    text: str, specialists: list[Specialist], dynamic_roles: bool
) -> Decision:
    data = _parse_json(text)
    if not data:
        raise ParentError(
            "the parent returned no decision",
            raw=text[:500],
            hint="the model did not return JSON; use a stronger model "
            "(check with `plnt models doctor`)",
        )
    kind = str(data.get("kind", "")).strip()
    reason = str(data.get("reason", "")).strip()
    reply = str(data.get("reply", "")).strip()
    if kind not in ("chat", "clarify", "agents"):
        kind = "agents" if data.get("agents") else "chat"
    if kind in ("chat", "clarify"):
        if not reply:
            raise ParentError(
                f"the parent chose {kind!r} but gave no reply", raw=text[:500]
            )
        return Decision(kind=kind, reason=reason, reply=reply)

    by_slug = {s.slug: s for s in specialists}
    agents: list[AgentPlan] = []
    seen: set[str] = set()
    for i, raw in enumerate(data.get("agents") or []):
        if not isinstance(raw, dict) or len(agents) >= MAX_AGENTS:
            continue
        bundle = raw.get("bundle")
        bundle = str(bundle).strip() if bundle else None
        role = _kebab(raw.get("role") or bundle or f"agent-{i + 1}", f"agent-{i + 1}")
        if bundle is None and role in by_slug:
            bundle = role  # the model named a specialist without setting bundle
        if bundle is not None and bundle not in by_slug:
            # An unknown slug: treat it as an invented role if allowed, else drop it.
            bundle = None
        if bundle is None and not dynamic_roles:
            continue
        aid = _kebab(raw.get("id") or role, role)
        if aid in seen:
            aid = f"{aid}-{i + 1}"
        seen.add(aid)
        deps = raw.get("depends_on") or []
        deps = [str(d) for d in deps if isinstance(d, str)] if isinstance(deps, list) else []
        intent = str(raw.get("intent", "")).strip()
        agents.append(AgentPlan(id=aid, role=role, intent=intent, bundle=bundle, depends_on=deps))
    if not agents:
        raise ParentError(
            "the parent planned no runnable agent",
            raw=text[:500],
            hint="the plan named no installed specialist"
            + ("" if dynamic_roles else " (invented roles are off for this tenant)"),
        )
    ids = {a.id for a in agents}
    for a in agents:
        a.depends_on = [d for d in a.depends_on if d in ids and d != a.id]
    return Decision(kind="agents", reason=reason, agents=agents)


def _history_block(history: list[dict[str, Any]], limit: int = 6) -> str:
    turns = [m for m in history if m.get("role") in ("user", "assistant")][-limit * 2 :]
    if not turns:
        return ""
    out = ["Conversation so far (oldest first):"]
    for m in turns:
        who = "Customer" if m["role"] == "user" else "Reply"
        out.append(f"  {who}: {str(m.get('content', ''))[:600]}")
    return "\n".join(out) + "\n\n"


def decide(
    provider: ModelProvider,
    *,
    text: str,
    history: list[dict[str, Any]],
    specialists: list[Specialist],
    business: str = "this business",
    dynamic_roles: bool = False,
    emit=None,
    timeout: float | None = None,
) -> Decision:
    """One model call: chat, clarify, or a plan of agents."""
    system = decision_prompt(business, specialists, dynamic_roles)
    user = _history_block(history) + f"Customer: {text}"
    if emit:
        emit("model_call", step=1, provider=provider.name, model=provider.model,
             purpose="decide")
    out = provider.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_schema=DECISION_SCHEMA,
        timeout=timeout,
    )
    if emit:
        emit("model_result", step=1, decision_kind="final", purpose="decide", **_usage(out))
    return parse_decision(out.content or "", specialists, dynamic_roles)


def synthesize(
    provider: ModelProvider,
    *,
    text: str,
    results: list[tuple[AgentPlan, dict[str, Any]]],
    business: str = "this business",
    emit=None,
    timeout: float | None = None,
) -> str:
    """Merge several agents' results into one reply. Falls back to joining them."""
    parts = []
    for plan, res in results:
        if res.get("answer"):
            parts.append(f"[{plan.role}] {res['answer']}")
        elif res.get("error"):
            parts.append(f"[{plan.role}] failed: {res['error']}")
    fallback = "\n\n".join(parts) or "(no agent produced an answer)"
    system = (
        f"You write the single reply a customer of {business} sees. Several agents "
        "handled parts of their message; merge their results into one short, direct "
        "reply in the same language as the customer. Keep every concrete fact, "
        "reference number and time exactly as the agents gave them. Never add facts "
        "of your own. If an agent failed, say what could not be done."
    )
    user = f"Customer's message: {text}\n\nAgent results:\n" + json.dumps(
        [
            {
                "agent": p.role,
                "intent": p.intent,
                "answer": r.get("answer"),
                "error": r.get("error"),
            }
            for p, r in results
        ],
        indent=2,
        default=str,
    )[:8000]
    if emit:
        emit("model_call", step=2, provider=provider.name, model=provider.model,
             purpose="synthesize")
    out = provider.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        timeout=timeout,
    )
    if emit:
        emit("model_result", step=2, decision_kind="final", purpose="synthesize",
             **_usage(out))
    return (out.content or "").strip() or fallback


def _usage(out: Any) -> dict[str, Any]:
    u = getattr(out, "usage", None)
    return {
        "tokens": getattr(u, "total_tokens", 0),
        "prompt_tokens": getattr(u, "prompt_tokens", 0),
        "completion_tokens": getattr(u, "completion_tokens", 0),
        "cost_usd": round(float(getattr(out, "cost_usd", 0.0) or 0.0), 6),
        "latency_ms": getattr(out, "latency_ms", 0),
        "provider": getattr(out, "provider", ""),
        "model": getattr(out, "model", ""),
    }
