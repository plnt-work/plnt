"""OpenAI-compatible chat completions provider.

Covers OpenAI, Gemini's OpenAI endpoint, vLLM, llama.cpp `server`, LM Studio,
Groq, Together — anything serving `POST {base}/chat/completions`. Uses native
`tools` / `tool_calls`; structured output via `response_format`.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from plnt.models.errors import (
    ModelBadResponse,
    ModelNotPulled,
    ModelTimeout,
    ModelUnavailable,
    ToolsUnsupported,
)
from plnt.models.profiles import ModelProfile
from plnt.models.types import ChatResult, HealthReport, ToolCall, Usage


def v1_base(url: str) -> str:
    """Normalise a base URL to the `.../v1`-style prefix endpoints hang off."""
    base = url.rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    if "/v1" not in base:
        base = base + "/v1"
    return base


def strip_code_fence(text: str) -> str:
    """Unwrap a ```json … ``` fence some models put around JSON output."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    body = text[3:]
    if body[:4].lower() == "json":
        body = body[4:]
    end = body.rfind("```")
    return (body[:end] if end != -1 else body).strip()


def parse_arguments(raw: Any) -> tuple[dict[str, Any], str | None]:
    """Tool-call arguments arrive as a JSON string (OpenAI) or object (Ollama)."""
    if isinstance(raw, dict):
        return raw, None
    if raw in (None, ""):
        return {}, None
    try:
        v = json.loads(strip_code_fence(str(raw)))
    except json.JSONDecodeError as e:
        return {}, f"arguments are not valid JSON: {e}"
    if not isinstance(v, dict):
        return {}, f"arguments must be a JSON object, got {type(v).__name__}"
    return v, None


_TOOLS_UNSUPPORTED_MARKERS = (
    "does not support tools",
    "tools are not supported",
    "tool use is not supported",
    "tool_choice is not supported",
    "function calling is not supported",
)


class OpenAICompatProvider:
    name = "openai"

    def __init__(self, profile: ModelProfile, *, transport: httpx.BaseTransport | None = None):
        self.profile = profile
        self.model = profile.model
        self._transport = transport

    # ------------------------------------------------------------------ http

    def _client(self, timeout: float) -> httpx.Client:
        return httpx.Client(timeout=timeout, transport=self._transport)

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.profile.api_key:
            h["Authorization"] = f"Bearer {self.profile.api_key}"
        return h

    def _err_kw(self) -> dict[str, str]:
        return {"provider": self.name, "model": self.model}

    # ------------------------------------------------------------------ chat

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
        timeout: float | None = None,
        tool_choice: str | None = None,
    ) -> ChatResult:
        p = self.profile
        payload: dict[str, Any] = {
            "model": p.model,
            "messages": messages,
            "stream": False,
            "temperature": p.temperature,
            "max_tokens": p.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = (
                {"type": "function", "function": {"name": tool_choice}} if tool_choice else "auto"
            )
        elif response_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": response_schema},
            }

        url = v1_base(p.base_url) + "/chat/completions"
        t = float(timeout or p.timeout)
        started = time.monotonic()
        try:
            with self._client(t) as c:
                r = c.post(url, json=payload, headers=self._headers())
        except httpx.TimeoutException as e:
            raise ModelTimeout(
                f"{url} did not answer within {t:.0f}s",
                hint="use a smaller model, raise PLNT_MODEL_TIMEOUT, or give the agent more "
                "wall budget",
                **self._err_kw(),
            ) from e
        except httpx.HTTPError as e:
            raise ModelUnavailable(
                f"cannot reach {url}: {e}",
                hint="check the server is running and the base URL is right",
                **self._err_kw(),
            ) from e
        latency_ms = int((time.monotonic() - started) * 1000)

        if r.status_code != 200:
            body = r.text[:500]
            low = body.lower()
            if tools and any(m in low for m in _TOOLS_UNSUPPORTED_MARKERS):
                raise ToolsUnsupported(f"{p.model} rejected native tools: {body}", **self._err_kw())
            if r.status_code == 404 and "model" in low:
                raise ModelNotPulled(
                    f"model {p.model!r} not found at {p.base_url}: {body}",
                    hint="check the model name (`plnt models list`)",
                    **self._err_kw(),
                )
            if r.status_code in (401, 403):
                raise ModelBadResponse(
                    f"HTTP {r.status_code} from {url}: {body}",
                    status=r.status_code,
                    hint="check the API key",
                    **self._err_kw(),
                )
            raise ModelBadResponse(
                f"HTTP {r.status_code} from {url}: {body}", status=r.status_code, **self._err_kw()
            )

        try:
            data = r.json()
            msg = data["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise ModelBadResponse(
                f"not a chat completion: {r.text[:300]}", status=r.status_code, **self._err_kw()
            ) from e

        calls: list[ToolCall] = []
        for i, tc in enumerate(msg.get("tool_calls") or []):
            fn = tc.get("function") or {}
            args, err = parse_arguments(fn.get("arguments"))
            calls.append(
                ToolCall(
                    id=tc.get("id") or f"call_{i}",
                    name=str(fn.get("name") or ""),
                    arguments=args,
                    parse_error=err,
                )
            )

        u = data.get("usage") or {}
        usage = Usage(int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0))
        return ChatResult(
            content=msg.get("content") or "",
            tool_calls=calls,
            usage=usage,
            latency_ms=latency_ms,
            provider=self.name,
            model=p.model,
            cost_usd=p.cost(usage.prompt_tokens, usage.completion_tokens),
        )

    # ---------------------------------------------------------------- health

    def list_models(self) -> list[str]:
        url = v1_base(self.profile.base_url) + "/models"
        try:
            with self._client(5.0) as c:
                r = c.get(url, headers=self._headers())
        except httpx.HTTPError as e:
            raise ModelUnavailable(f"cannot reach {url}: {e}", **self._err_kw()) from e
        if r.status_code != 200:
            raise ModelBadResponse(
                f"HTTP {r.status_code} from {url}", status=r.status_code, **self._err_kw()
            )
        try:
            return [str(m.get("id")) for m in r.json().get("data", []) if m.get("id")]
        except (ValueError, AttributeError) as e:
            raise ModelBadResponse(
                f"unexpected /models body: {r.text[:200]}", **self._err_kw()
            ) from e

    def health(self) -> HealthReport:
        p = self.profile
        rep = HealthReport(ok=False, provider=self.name, base_url=p.base_url, model=p.model)
        try:
            models = self.list_models()
        except ModelUnavailable as e:
            rep.detail = str(e)
            rep.hint = "start the server or fix the base URL"
            return rep
        except ModelBadResponse as e:
            # Reachable, but /models is not served (some proxies) or auth failed.
            rep.reachable = True
            rep.detail = str(e)
            rep.hint = "check the API key" if e.status in (401, 403) else ""
            rep.ok = e.status not in (401, 403)
            return rep
        rep.reachable = True
        rep.available_models = models
        if models:
            rep.model_present = _model_listed(p.model, models)
            if not rep.model_present:
                rep.hint = f"{p.model!r} is not served here; available: {', '.join(models[:8])}"
        rep.ok = rep.model_present is not False
        return rep


def _model_listed(model: str, models: list[str]) -> bool:
    # Gemini lists "models/gemini-2.5-flash"; accept a suffix match.
    return any(m == model or m.endswith("/" + model) for m in models)
