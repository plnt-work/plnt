"""plnt-cloud's agent loop — Gemini via OpenAI-compatible native function calling.

Replaces plnt's runner for plnt-cloud's domain skills. plnt's runner stays
the right primitive for personal-runtime skills that touch the filesystem
via search/execute; plnt-cloud's skills call domain tools (Places,
BookingsStore, notify adapters) and don't fit the RLM constraint baked into
`plnt.execution.spec.AgentSpec.tools` (which validates against
`{"search","execute"}`).

The loop:
  1. Render system prompt = skill.prompt + memory_context summary (when present).
  2. Render user message from the skill's structured inputs.
  3. Call Gemini (OpenAI chat-completions endpoint) with:
       - `tools`     = OpenAI specs for skill.tools
       - `response_format` = json_schema when skill declares one and no
         tools are configured (forces native structured output for
         single-shot skills like classify_intent / synthesize_response)
  4. Loop up to skill.max_steps:
       - Response has tool_calls → dispatch each, append `tool` messages
         carrying the result, continue
       - Response has content → parse JSON (when applicable) and return
  5. Always return a dict shaped {output, steps, transcript, error}.

This module is the single LLM-call surface for plnt-cloud Activities.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from memory.memori_adapter import MemoriAdapter
from microagents import tools as tool_registry
from microagents.loader import LoadedSkill
from tenancy.context import TenantContext


log = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────── result type


@dataclass
class LoopResult:
    """Return shape from `run_skill`. Mirrors the relevant subset of plnt's
    runner output so workflows/activities can adapt with minimal change.
    """

    output: dict[str, Any]
    steps: int = 0
    transcript: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "steps": self.steps,
            "transcript": self.transcript,
            "error": self.error,
        }


# ───────────────────────────────────────────────────────────── env / endpoint


def _endpoint() -> str:
    """Gemini's OpenAI-compatible chat-completions URL.

    `PLNT_CLOUD_URL` is the base (e.g. https://generativelanguage.googleapis.com/v1beta/openai).
    Append /chat/completions when the base already contains /v1 — otherwise
    append /v1/chat/completions.
    """
    base = (os.environ.get("PLNT_CLOUD_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError(
            "PLNT_CLOUD_URL is unset; source plnt-cloud/.env before launching the worker"
        )
    if "/v1" in base:
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _api_key() -> str:
    key = os.environ.get("PLNT_CLOUD_API_KEY") or ""
    if not key:
        raise RuntimeError(
            "PLNT_CLOUD_API_KEY is unset; source plnt-cloud/.env before launching the worker"
        )
    return key


def _model_for(hint: str) -> str:
    if hint == "deep":
        return os.environ.get("PLNT_CLOUD_DEEP_MODEL") or "gemini-2.5-pro"
    return os.environ.get("PLNT_CLOUD_SMALL_MODEL") or "gemini-2.5-flash"


# ───────────────────────────────────────────────────────────── prompt build


def _format_memory(memories: list[dict[str, Any]] | None) -> str:
    """Render the last few Memori entries as a single block prefixed to the
    system prompt. Matches the prior behavior of `_inject_memory_into_prompt`
    in workflows/activities.py — moved here so the loop owns one place.
    """
    if not memories:
        return ""
    lines = []
    for m in memories[-5:]:
        role = str(m.get("role") or m.get("turn_role") or "?").strip() or "?"
        content = str(m.get("content") or "").strip()
        if content:
            lines.append(f"  - [{role}] {content[:200]}")
    if not lines:
        return ""
    return "PRIOR CONVERSATION CONTEXT (most recent first):\n" + "\n".join(lines)


def _user_message(inputs: dict[str, Any]) -> str:
    """Render the skill's structured inputs as a JSON user prompt.

    Skills that want a specific intent string should put it under `intent`;
    everything else flows as a JSON object so the model sees typed fields.
    """
    # Strip reserved tenant keys and internal fields so the user prompt
    # stays focused on skill-specific data.
    reserved = {"tenant_id", "user_id", "session_id", "memory_context",
                "skill_prompt", "max_steps", "force_backend"}
    rendered = {k: v for k, v in inputs.items() if k not in reserved}
    if not rendered:
        return "(no inputs)"
    return json.dumps(rendered, default=str, ensure_ascii=False, indent=2)


def _build_initial_messages(
    skill: LoadedSkill,
    inputs: dict[str, Any],
    memories: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    system_parts = [skill.prompt.strip()]
    mem = _format_memory(memories)
    if mem:
        system_parts.append(mem)
    return [
        {"role": "system", "content": "\n\n".join(system_parts)},
        {"role": "user", "content": _user_message(inputs)},
    ]


# ───────────────────────────────────────────────────────────── HTTP call


def _post(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    response_format: dict[str, Any] | None,
    timeout: float,
) -> dict[str, Any]:
    """One chat-completions round trip. Surfaces non-2xx as RuntimeError so
    the caller's audit log captures the failure rather than masking it.
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        # tool_choice=auto lets the model decide; the alternative ("required")
        # forces a call even when the model has everything it needs from
        # the prompt — bad for skills like resolve_business where the model
        # may answer from world knowledge when Places is disabled.
        payload["tool_choice"] = "auto"
    if response_format:
        payload["response_format"] = response_format

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_api_key()}",
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(_endpoint(), json=payload, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(
            f"Gemini call failed: HTTP {r.status_code} {r.text[:500]}"
        )
    return r.json()


# ───────────────────────────────────────────────────────────── output parsing


def _strip_code_fence(text: str) -> str:
    """Unwrap a ```json … ``` (or bare ```) markdown fence.

    Gemini's OpenAI-compat surface fences JSON on tool-bearing skills, where
    we can't send responseSchema — so the raw content arrives fenced.
    """
    if not text.startswith("```"):
        return text
    body = text[3:]
    if body[:4].lower() == "json":
        body = body[4:]
    elif body[:1] == "\n":
        body = body[1:]
    end = body.rfind("```")
    return (body[:end] if end != -1 else body).strip()


def _parse_content(content: str | None, *, expect_json: bool) -> dict[str, Any]:
    """Turn the model's final message content into a dict.

    When the skill declared a response_schema we expect strict JSON and
    surface a parse failure as an error field. Otherwise wrap free text in
    {"answer": <text>}.
    """
    text = _strip_code_fence((content or "").strip())
    if not text:
        return {}
    if expect_json:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            return {"answer": parsed}
        except json.JSONDecodeError as e:
            log.warning("skill returned non-JSON despite response_schema: %s", e)
            return {"error": f"non-JSON response: {e}", "raw": text[:500]}
    # No schema declared — best-effort JSON detection.
    if text[0] in "{[":
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {"answer": parsed}
        except json.JSONDecodeError:
            pass
    return {"answer": text}


# ───────────────────────────────────────────────────────────── loop


def run_skill(
    skill: LoadedSkill,
    *,
    ctx: TenantContext,
    inputs: dict[str, Any],
    memori: MemoriAdapter | None = None,
) -> LoopResult:
    """Run one skill to completion via Gemini-native function calling.

    `memori` is optional. When supplied, recent entries for (user_id, role)
    are preloaded into the system prompt prefix; otherwise any
    `memory_context` already on `inputs` is used as-is.
    """
    # 1. Memory: prefer inputs["memory_context"] when caller preloaded;
    #    else recall fresh from Memori using the user message as the query.
    memories = inputs.get("memory_context")
    if (not memories) and memori is not None:
        query = str(inputs.get("intent") or inputs.get("text") or "")
        try:
            memories = memori.recall(user_id=ctx.user_id, role=skill.role, query=query, k=5)
        except Exception:  # noqa: BLE001 — recall is best-effort
            memories = []

    # 2. Initial messages.
    messages = _build_initial_messages(skill, inputs, memories)

    # 3. Tool + structured-output configuration from skill.toml.
    tool_specs = tool_registry.specs_for(skill.tools) if skill.tools else None
    response_format = None
    if skill.response_schema and not skill.tools:
        # json_schema (non-strict) for tools-less skills. The OpenAI-compat
        # layer forwards this to Gemini's responseSchema. We avoid OpenAI's
        # `strict: true` extension because Gemini's compat surface doesn't
        # implement it consistently; the prompt + parser cover the gap.
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": skill.role,
                "schema": skill.response_schema,
            },
        }

    model = _model_for(skill.model_hint)
    max_steps = max(1, int(skill.max_steps))
    transcript: list[dict[str, Any]] = []

    # 4. Loop.
    for step in range(1, max_steps + 1):
        try:
            data = _post(
                model=model,
                messages=messages,
                tools=tool_specs,
                response_format=response_format,
                timeout=float(skill.budget_wall_seconds),
            )
        except Exception as e:  # noqa: BLE001
            return LoopResult(
                output={},
                steps=step - 1,
                transcript=transcript,
                error=f"step {step}: {e}",
            )

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        tool_calls = msg.get("tool_calls") or []

        # 4a. Tool-call branch — dispatch each, append tool messages, loop.
        if tool_calls:
            # Echo the assistant turn that asked for the tools, so subsequent
            # tool messages have an anchor (OpenAI protocol requirement).
            messages.append({
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": tool_calls,
            })
            for call in tool_calls:
                fn = (call.get("function") or {})
                name = str(fn.get("name") or "")
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except json.JSONDecodeError as e:
                    args = {}
                    result: dict[str, Any] = {"error": f"bad tool args JSON: {e}"}
                else:
                    try:
                        result = tool_registry.dispatch(name, ctx, args)
                    except Exception as e:  # noqa: BLE001 — surface to model
                        result = {"error": f"tool {name!r} raised: {e}"}
                transcript.append({"step": step, "tool": name, "args": args, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id") or "",
                    "name": name,
                    "content": json.dumps(result, default=str, ensure_ascii=False),
                })
            continue

        # 4b. Final answer branch.
        content = msg.get("content")
        expect_json = bool(skill.response_schema) or bool(skill.tools)
        output = _parse_content(content, expect_json=expect_json)
        return LoopResult(output=output, steps=step, transcript=transcript, error=None)

    # 5. max_steps exceeded without a final.
    return LoopResult(
        output={},
        steps=max_steps,
        transcript=transcript,
        error=f"max_steps={max_steps} exceeded without a final answer",
    )
