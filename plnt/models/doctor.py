"""`plnt models doctor` — check that a model will actually work for agents.

Checks, in order (later checks are skipped when an earlier one fails):
  1. reachable     — the endpoint answers
  2. model present — the model is pulled / served
  3. tool calling  — the model calls a tool when asked (native, else via the JSON shim)
  4. JSON output   — the model returns valid JSON for a schema
  5. context       — (Ollama) model context length vs the num_ctx plnt requests
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from plnt.models import ModelError, ModelProfile, ModelProvider, chat, get_provider
from plnt.models.openai_compat import strip_code_fence


@dataclass
class Check:
    name: str
    ok: bool | None  # None = skipped / not applicable
    detail: str = ""
    hint: str = ""


@dataclass
class DoctorReport:
    profile: ModelProfile
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok is not False for c in self.checks)


_PROBE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]
_PROBE_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "integer"}},
    "required": ["answer"],
}


def _probe_tools(provider: ModelProvider, timeout: float) -> Check:
    msgs = [
        {"role": "system", "content": "You are a helpful assistant. Use tools when they help."},
        {"role": "user", "content": "What is the weather in Paris right now? Use the tool."},
    ]
    try:
        res = chat(provider, msgs, tools=_PROBE_TOOL, timeout=timeout)
    except ModelError as e:
        return Check("tool calling", False, str(e), e.hint)
    if res.tool_calls and res.tool_calls[0].name == "get_weather":
        how = "via JSON shim (model lacks native tools)" if res.shimmed else "native"
        city = res.tool_calls[0].arguments.get("city", "?")
        return Check("tool calling", True, f"{how}; called get_weather(city={city!r})")
    return Check(
        "tool calling",
        False,
        f"model answered without calling the tool: {res.content[:120]!r}",
        "this model is weak at tool use; try qwen2.5:7b, llama3.1:8b or a hosted model",
    )


def _probe_json(provider: ModelProvider, timeout: float) -> Check:
    msgs = [{"role": "user", "content": 'What is 17 + 25? Reply as JSON: {"answer": <number>}.'}]
    try:
        res = provider.chat(msgs, response_schema=_PROBE_SCHEMA, timeout=timeout)
    except ModelError as e:
        return Check("JSON output", False, str(e), e.hint)
    try:
        obj = json.loads(strip_code_fence(res.content))
    except json.JSONDecodeError:
        return Check(
            "JSON output",
            False,
            f"not JSON: {res.content[:120]!r}",
            "structured output unsupported; bundles with response schemas may fail",
        )
    ok = isinstance(obj, dict) and obj.get("answer") == 42
    return Check("JSON output", ok, f"got {obj}", "" if ok else "valid JSON but wrong answer")


def _ollama_context(profile: ModelProfile, transport: httpx.BaseTransport | None) -> Check:
    try:
        with httpx.Client(timeout=5.0, transport=transport) as c:
            r = c.post(profile.base_url.rstrip("/") + "/api/show", json={"model": profile.model})
        info: dict[str, Any] = r.json().get("model_info") or {}
    except (httpx.HTTPError, ValueError):
        return Check("context window", None, "could not read /api/show")
    ctx = next((int(v) for k, v in info.items() if k.endswith(".context_length")), 0)
    if not ctx:
        return Check("context window", None, "model does not report its context length")
    if ctx < profile.num_ctx:
        return Check(
            "context window",
            False,
            f"model supports {ctx} tokens but plnt requests num_ctx={profile.num_ctx}",
            f"set PLNT_NUM_CTX={ctx}",
        )
    return Check("context window", True, f"requesting {profile.num_ctx} of {ctx} tokens")


def diagnose(
    profile: ModelProfile,
    *,
    probe: bool = True,
    timeout: float = 120.0,
    transport: httpx.BaseTransport | None = None,
) -> DoctorReport:
    rep = DoctorReport(profile=profile)
    provider = get_provider(profile)
    if transport is not None and hasattr(provider, "_transport"):
        provider._transport = transport  # type: ignore[attr-defined]

    h = provider.health()
    rep.checks.append(
        Check("reachable", h.reachable, h.detail or profile.base_url, "" if h.reachable else h.hint)
    )
    if not h.reachable:
        return rep
    if h.model_present is None:
        rep.checks.append(Check("model present", None, "endpoint does not list models"))
    else:
        rep.checks.append(
            Check(
                "model present",
                h.model_present,
                profile.model if h.model_present else f"{profile.model} not found",
                h.hint,
            )
        )
        if not h.model_present:
            return rep
    if profile.provider == "ollama":
        rep.checks.append(_ollama_context(profile, transport))
    if probe and profile.provider != "offline":
        rep.checks.append(_probe_tools(provider, timeout))
        rep.checks.append(_probe_json(provider, timeout))
    return rep
