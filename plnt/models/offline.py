"""Deterministic providers: no network, no model.

* `OfflineProvider` — selected ONLY by PLNT_FORCE=offline. Makes one
  `search` call derived from the request, then answers with a clearly
  labelled summary. Used by hermetic tests and no-model demos. Its output is
  always prefixed "[offline stub]" so it can never pass for a model answer.
* `ScriptedProvider` — replays a fixed list of ChatResults. For unit tests.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Any

from plnt.models.profiles import ModelProfile, offline_profile
from plnt.models.types import ChatResult, HealthReport, ToolCall

OFFLINE_PREFIX = "[offline stub]"


def _keyword(text: str) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text)
    return max(words, key=len) if words else "."


def _tool_names(tools: list[dict[str, Any]] | None) -> set[str]:
    return {(t.get("function") or {}).get("name", "") for t in (tools or [])}


class OfflineProvider:
    name = "offline"

    def __init__(self, profile: ModelProfile | None = None):
        self.profile = profile or offline_profile()
        self.model = self.profile.model

    def chat(self, messages, *, tools=None, response_schema=None, timeout=None) -> ChatResult:
        # Planner / triage / synthesizer calls pass no tools: return nothing so
        # their own documented fallbacks run.
        if not tools:
            return ChatResult(content="", provider=self.name, model=self.model)

        tool_results = [m for m in messages if m.get("role") == "tool"]
        user = next(
            (m.get("content") or "" for m in reversed(messages) if m.get("role") == "user"), ""
        )
        if not tool_results and "search" in _tool_names(tools):
            root = (os.environ.get("PLNT_SEARCH_ROOTS", "").split(":")[0] or ".").strip() or "."
            call = ToolCall(
                id="call_0",
                name="search",
                arguments={"pattern": _keyword(user.split("TASK:")[-1]), "root": root},
            )
            return ChatResult(tool_calls=[call], provider=self.name, model=self.model)
        summary = (
            f"{OFFLINE_PREFIX} no model configured (PLNT_FORCE=offline); "
            f"tool calls made: {len(tool_results)}"
        )
        return ChatResult(content=summary, provider=self.name, model=self.model)

    def health(self) -> HealthReport:
        return HealthReport(
            ok=True,
            provider=self.name,
            base_url="",
            model=self.model,
            reachable=True,
            detail="deterministic stub, no model",
        )

    def list_models(self) -> list[str]:
        return [self.model]


class ScriptedProvider:
    """Returns queued ChatResults in order; or calls `fn(messages, tools)`."""

    name = "scripted"

    def __init__(
        self, script: list[ChatResult] | Callable[..., ChatResult], model: str = "scripted"
    ):
        self._script = script
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages, *, tools=None, response_schema=None, timeout=None) -> ChatResult:
        self.calls.append(
            {
                "messages": [dict(m) for m in messages],
                "tools": tools,
                "response_schema": response_schema,
                "timeout": timeout,
            }
        )
        if callable(self._script):
            res = self._script(messages, tools)
        else:
            if not self._script:
                raise AssertionError("ScriptedProvider ran out of scripted responses")
            res = self._script.pop(0)
        res.provider = res.provider or self.name
        res.model = res.model or self.model
        return res

    def health(self) -> HealthReport:
        return HealthReport(
            ok=True, provider=self.name, base_url="", model=self.model, reachable=True
        )

    def list_models(self) -> list[str]:
        return [self.model]
