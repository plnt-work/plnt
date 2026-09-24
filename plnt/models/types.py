"""Provider-neutral request/response types.

Messages use the OpenAI chat shape (`role`, `content`, `tool_calls`,
`tool_call_id`) because every supported backend either speaks it natively or
is converted from it at the provider edge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    # Set when the model produced arguments that were not a JSON object.
    parse_error: str | None = None

    def to_openai(self) -> dict[str, Any]:
        import json

        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": json.dumps(self.arguments)},
        }


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.prompt_tokens + other.prompt_tokens,
            self.completion_tokens + other.completion_tokens,
        )


@dataclass
class ChatResult:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    provider: str = ""
    model: str = ""
    cost_usd: float = 0.0
    # True when tool calls were produced by the JSON shim rather than natively.
    shimmed: bool = False

    def assistant_message(self) -> dict[str, Any]:
        """The assistant turn to append to the transcript before tool results."""
        msg: dict[str, Any] = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [tc.to_openai() for tc in self.tool_calls]
        return msg


@dataclass
class HealthReport:
    ok: bool
    provider: str
    base_url: str
    model: str
    reachable: bool = False
    model_present: bool | None = None  # None = endpoint can't tell us
    available_models: list[str] = field(default_factory=list)
    detail: str = ""
    hint: str = ""


class ModelProvider(Protocol):
    """What the agent loop needs from a model backend."""

    name: str
    model: str

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> ChatResult: ...

    def health(self) -> HealthReport: ...

    def list_models(self) -> list[str]: ...
