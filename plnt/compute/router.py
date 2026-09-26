"""LLMRouter — single-shot text completions for the planner, triage and synthesizer.

Tool-using agents go through `plnt.agent.run_agent`; this router only serves
callers that want one plain completion (`raw=True`). It resolves the model
with `plnt.models.resolve_profile` on every call, so local/cloud switching is
per call.

Failures raise `plnt.models.ModelError` (with a `hint`). The callers each
have a documented, logged fallback (default spec, "simple_task", concatenated
answers); nothing here fabricates model output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from plnt.models import get_provider, resolve_profile


@dataclass
class Decision:
    kind: Literal["tool_call", "final"]
    tool_name: str | None = None
    tool_args: dict | None = None
    text: str = ""
    tokens: int = 0
    latency_ms: int = 0
    backend: str = "unknown"  # "local" | "cloud" | "offline" — audit field


class LLMRouter:
    def __init__(self, force: Literal["auto", "local", "cloud", "offline"] | None = None):
        self.force = force

    def step(
        self,
        *,
        system: str,
        user: str,
        transcript: list[dict] | None = None,
        tools: list[str] | None = None,
        model_hint: str = "auto",
        raw: bool = True,
    ) -> Decision:
        if not raw:
            raise NotImplementedError(
                "LLMRouter only serves raw completions; use plnt.agent.run_agent for tool use"
            )
        profile = resolve_profile(model_hint, self.force)  # type: ignore[arg-type]
        provider = get_provider(profile)
        res = provider.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}]
        )
        return Decision(
            kind="final",
            text=res.content,
            tokens=res.usage.total_tokens,
            latency_ms=res.latency_ms,
            backend=profile.source,
        )
