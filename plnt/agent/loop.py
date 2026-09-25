"""The agent loop: model ⇄ tools until a final answer, a budget, or an error.

    result = run_agent(system=..., user=..., tools=[...], provider=provider,
                       max_steps=6, deadline=time.monotonic() + 180, emit=emit)

Guarantees:
  * The transcript follows the tool-calling protocol exactly: assistant turn
    with `tool_calls`, then one `tool` message per call. No fake user turns.
  * Every model call's timeout is capped by the remaining wall budget.
  * Model failures stop the loop and are returned as `error` + `error_hint`
    (never replaced by an invented answer).
  * Events: model_call, model_result (with `tokens` for the budget governor),
    tool_call, tool_result, model_error, killed.
  * `require_tool` names a tool that must be called before any answer:
    forced via tool_choice where the backend supports it, otherwise the model
    is re-asked once and then the answer is refused (`guardrail` events).
  * `should_stop()` is polled before every model call and tool call; a
    non-empty reason stops the run (kill switch, budgets, manual kill).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from plnt.agent.tools import ToolDef
from plnt.models import ChatResult, ModelError, ModelProvider, Usage, chat
from plnt.models.openai_compat import strip_code_fence

Emit = Callable[..., None]
TOOL_RESULT_MAX_CHARS = 8000


@dataclass
class AgentResult:
    output: Any = None
    steps: int = 0
    transcript: list[dict[str, Any]] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    cost_usd: float = 0.0
    stopped: Literal["final", "max_steps", "error", "wall_budget", "killed"] = "final"
    error: str | None = None
    error_hint: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)

    @property
    def answer(self) -> str:
        if self.output is None:
            return ""
        return self.output if isinstance(self.output, str) else json.dumps(self.output)


def _noop(kind: str, **payload: Any) -> None:
    return None


def _encode(result: Any) -> str:
    s = json.dumps(result, default=str, ensure_ascii=False)
    if len(s) > TOOL_RESULT_MAX_CHARS:
        s = s[:TOOL_RESULT_MAX_CHARS] + f"… [truncated, {len(s)} chars total]"
    return s


def _parse_output(content: str, response_schema: dict[str, Any] | None) -> tuple[Any, str | None]:
    text = (content or "").strip()
    if not response_schema:
        return text, None
    try:
        return json.loads(strip_code_fence(text)), None
    except json.JSONDecodeError as e:
        return text, f"model output is not valid JSON for the response schema: {e}"


def run_agent(
    *,
    system: str,
    user: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    tools: list[ToolDef] | None = None,
    provider: ModelProvider,
    max_steps: int = 6,
    response_schema: dict[str, Any] | None = None,
    deadline: float | None = None,
    emit: Emit | None = None,
    native_tools: str | None = None,
    should_stop: Callable[[], str | None] | None = None,
    require_tool: str | None = None,
) -> AgentResult:
    emit = emit or _noop
    by_name = {t.name: t for t in (tools or [])}
    specs = [t.spec() for t in by_name.values()] or None
    msgs: list[dict[str, Any]] = (
        messages
        if messages is not None
        else [
            {"role": "system", "content": system},
            {"role": "user", "content": user or ""},
        ]
    )
    res = AgentResult(messages=msgs)
    base_timeout = float(getattr(getattr(provider, "profile", None), "timeout", 120.0))
    if require_tool and require_tool not in by_name:
        raise ValueError(f"require_tool {require_tool!r} is not one of the tools {sorted(by_name)}")
    required_done = require_tool is None
    reminded = False

    def _killed() -> bool:
        reason = should_stop() if should_stop else None
        if reason:
            res.stopped = "killed"
            res.error = f"run stopped: {reason}"
            emit("killed", step=res.steps, reason=reason)
        return bool(reason)

    for step in range(1, max(1, max_steps) + 1):
        res.steps = step
        if _killed():
            return res
        timeout = base_timeout
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining < 1.0:
                res.stopped = "wall_budget"
                res.error = "wall-clock budget exhausted before the agent finished"
                res.error_hint = "raise the bundle's wall_seconds or use a faster model"
                return res
            timeout = min(timeout, remaining)

        emit("model_call", step=step, provider=provider.name, model=provider.model)
        try:
            out: ChatResult = chat(
                provider,
                msgs,
                tools=specs,
                response_schema=None if specs else response_schema,
                timeout=timeout,
                native_tools=native_tools,
                tool_choice=None if required_done else require_tool,
            )
        except ModelError as e:
            emit("model_error", step=step, **e.to_event())
            res.stopped = "error"
            res.error = e.args[0] if e.args else str(e)  # hint is kept separately
            res.error_hint = e.hint
            return res

        res.usage = res.usage + out.usage
        res.cost_usd += out.cost_usd
        emit(
            "model_result",
            step=step,
            decision_kind="tool_call" if out.tool_calls else "final",
            tokens=out.usage.total_tokens,
            prompt_tokens=out.usage.prompt_tokens,
            completion_tokens=out.usage.completion_tokens,
            cost_usd=round(out.cost_usd, 6),
            latency_ms=out.latency_ms,
            provider=out.provider,
            model=out.model,
            shimmed=out.shimmed,
        )

        if not out.tool_calls and not required_done:
            # Guardrail: the bundle requires a tool (e.g. a lookup) before any
            # answer. Re-ask once; if the model still skips it, refuse rather
            # than pass on an unverified answer.
            emit("guardrail", step=step, rule="require_tool", tool=require_tool,
                 action="refused" if reminded else "reprompt", skipped_answer=out.content[:500])
            if reminded:
                res.stopped = "error"
                res.error = (f"the model answered without calling the required tool "
                             f"{require_tool!r}; its answer was withheld")
                res.error_hint = ("this model does not follow tool instructions reliably; use a "
                                  "stronger model (check with `plnt models doctor`)")
                return res
            reminded = True
            msgs.append({"role": "assistant", "content": out.content})
            msgs.append({"role": "user", "content": (
                f"You have not called `{require_tool}` yet. You must call it before answering; "
                "do not answer from memory. Call it now.")})
            continue

        if not out.tool_calls:
            output, err = _parse_output(out.content, response_schema)
            res.output = output
            if err:
                res.error = err
            msgs.append({"role": "assistant", "content": out.content})
            return res

        msgs.append(out.assistant_message())
        for call in out.tool_calls:
            if _killed():
                return res
            emit("tool_call", step=step, tool=call.name, args=call.arguments)
            if call.name == require_tool:
                required_done = True
            tool = by_name.get(call.name)
            if call.parse_error:
                result: Any = {"error": call.parse_error}
            elif tool is None:
                result = {"error": f"unknown tool {call.name!r}; available: {sorted(by_name)}"}
            else:
                try:
                    result = tool.fn(call.arguments)
                except Exception as e:  # noqa: BLE001 — tool errors go back to the model
                    result = {"error": f"{type(e).__name__}: {e}"}
            ok = not (isinstance(result, dict) and "error" in result)
            emit("tool_result", step=step, tool=call.name, ok=ok)
            res.transcript.append(
                {"step": step, "tool": call.name, "args": call.arguments, "result": result}
            )
            msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": _encode(result),
                }
            )

    res.stopped = "max_steps"
    res.error = f"max_steps={max_steps} reached without a final answer"
    res.error_hint = "raise max_steps for this bundle, or simplify the task"
    return res
