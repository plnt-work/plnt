"""Ollama native provider (`/api/chat`).

Why native and not Ollama's `/v1` shim: only `/api/chat` honours
`options.num_ctx`. Ollama's default context is small (2–4k tokens), so agent
prompts with tool schemas and transcripts get silently truncated through
`/v1` — the most common reason local agents "forget" their instructions.
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
from plnt.models.openai_compat import parse_arguments
from plnt.models.profiles import ModelProfile
from plnt.models.types import ChatResult, HealthReport, ToolCall, Usage


def to_ollama_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-shaped messages to Ollama's shape.

    Differences: tool-call arguments are objects, not JSON strings; tool
    results carry `tool_name` instead of `tool_call_id`.
    """
    id_to_name: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            calls = []
            for tc in m["tool_calls"]:
                fn = tc.get("function") or {}
                args, _ = parse_arguments(fn.get("arguments"))
                id_to_name[tc.get("id", "")] = fn.get("name", "")
                calls.append({"function": {"name": fn.get("name", ""), "arguments": args}})
            out.append(
                {"role": "assistant", "content": m.get("content") or "", "tool_calls": calls}
            )
        elif role == "tool":
            name = m.get("name") or id_to_name.get(m.get("tool_call_id", ""), "")
            out.append({"role": "tool", "content": m.get("content") or "", "tool_name": name})
        else:
            out.append({"role": role, "content": m.get("content") or ""})
    return out


def _same_model(want: str, have: str) -> bool:
    # Ollama treats an untagged name as ":latest" ("llama3.2" == "llama3.2:latest").
    def norm(n: str) -> str:
        return n if ":" in n else n + ":latest"

    return norm(want) == norm(have)


class OllamaProvider:
    name = "ollama"

    def __init__(self, profile: ModelProfile, *, transport: httpx.BaseTransport | None = None):
        self.profile = profile
        self.model = profile.model
        self._transport = transport

    def _base(self) -> str:
        return self.profile.base_url.rstrip("/")

    def _client(self, timeout: float) -> httpx.Client:
        return httpx.Client(timeout=timeout, transport=self._transport)

    def _err_kw(self) -> dict[str, str]:
        return {"provider": self.name, "model": self.model}

    def _not_pulled(self, detail: str = "") -> ModelNotPulled:
        return ModelNotPulled(
            f"model {self.model!r} is not pulled on {self._base()}"
            + (f": {detail}" if detail else ""),
            hint=f"run `ollama pull {self.model}`",
            **self._err_kw(),
        )

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
            "messages": to_ollama_messages(messages),
            "stream": False,
            "options": {
                "num_ctx": p.num_ctx,
                "temperature": p.temperature,
                "num_predict": p.max_tokens,
            },
        }
        if tools:
            # Ollama has no tool_choice; a required tool is enforced by the
            # agent loop (re-prompt, then refuse) instead.
            payload["tools"] = tools
        elif response_schema:
            payload["format"] = response_schema

        url = self._base() + "/api/chat"
        t = float(timeout or p.timeout)
        started = time.monotonic()
        try:
            with self._client(t) as c:
                r = c.post(url, json=payload)
        except httpx.TimeoutException as e:
            raise ModelTimeout(
                f"{p.model} on {self._base()} did not answer within {t:.0f}s",
                hint="first calls load the model into memory; try again, use a smaller model, "
                "or raise PLNT_MODEL_TIMEOUT",
                **self._err_kw(),
            ) from e
        except httpx.HTTPError as e:
            raise ModelUnavailable(
                f"cannot reach Ollama at {self._base()}: {e}",
                hint="start it with `ollama serve` (or fix PLNT_LOCAL_URL)",
                **self._err_kw(),
            ) from e
        latency_ms = int((time.monotonic() - started) * 1000)

        if r.status_code != 200:
            body = r.text[:500]
            low = body.lower()
            if r.status_code == 404 or ("not found" in low and "model" in low):
                raise self._not_pulled(body)
            if tools and "does not support tools" in low:
                raise ToolsUnsupported(f"{p.model} does not support native tools", **self._err_kw())
            raise ModelBadResponse(
                f"HTTP {r.status_code} from {url}: {body}", status=r.status_code, **self._err_kw()
            )

        try:
            data = r.json()
            msg = data["message"]
        except (ValueError, KeyError, TypeError) as e:
            raise ModelBadResponse(
                f"not an Ollama chat response: {r.text[:300]}", **self._err_kw()
            ) from e

        calls: list[ToolCall] = []
        for i, tc in enumerate(msg.get("tool_calls") or []):
            fn = tc.get("function") or {}
            args, err = parse_arguments(fn.get("arguments"))
            calls.append(
                ToolCall(
                    id=f"call_{i}", name=str(fn.get("name") or ""), arguments=args, parse_error=err
                )
            )

        usage = Usage(int(data.get("prompt_eval_count") or 0), int(data.get("eval_count") or 0))
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
        url = self._base() + "/api/tags"
        try:
            with self._client(5.0) as c:
                r = c.get(url)
        except httpx.HTTPError as e:
            raise ModelUnavailable(
                f"cannot reach Ollama at {self._base()}: {e}",
                hint="start it with `ollama serve` (or fix PLNT_LOCAL_URL)",
                **self._err_kw(),
            ) from e
        if r.status_code != 200:
            raise ModelBadResponse(
                f"HTTP {r.status_code} from {url}", status=r.status_code, **self._err_kw()
            )
        try:
            return [str(m.get("name") or m.get("model")) for m in r.json().get("models", [])]
        except (ValueError, AttributeError) as e:
            raise ModelBadResponse(
                f"unexpected /api/tags body: {r.text[:200]}", **self._err_kw()
            ) from e

    def health(self) -> HealthReport:
        p = self.profile
        rep = HealthReport(ok=False, provider=self.name, base_url=p.base_url, model=p.model)
        try:
            models = self.list_models()
        except (ModelUnavailable, ModelBadResponse) as e:
            rep.detail = str(e)
            rep.hint = e.hint or "start it with `ollama serve`"
            return rep
        rep.reachable = True
        rep.available_models = models
        rep.model_present = any(_same_model(p.model, m) for m in models)
        if not rep.model_present:
            rep.hint = f"run `ollama pull {p.model}`"
        rep.ok = rep.model_present
        return rep


def show_capabilities(
    base_url: str, model: str, transport: httpx.BaseTransport | None = None
) -> list[str]:
    """Ollama ≥0.6 reports model capabilities (e.g. ["completion","tools"]).

    Returns [] when the server is older or the call fails — callers treat
    that as "unknown", not "unsupported".
    """
    try:
        with httpx.Client(timeout=5.0, transport=transport) as c:
            r = c.post(base_url.rstrip("/") + "/api/show", json={"model": model})
        if r.status_code != 200:
            return []
        caps = r.json().get("capabilities") or []
        return [str(x) for x in caps]
    except (httpx.HTTPError, ValueError, json.JSONDecodeError):
        return []
