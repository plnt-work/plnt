"""Tool registry — the dispatch table the agent loop consults.

A `Tool` is a pure Python callable that takes a TenantContext and keyword
arguments matching its JSON schema, and returns a dict result. The agent
loop sends each tool's JSON schema to Gemini via the OpenAI-compatible
`tools` parameter; when the model emits a `tool_call`, the loop looks up
the named tool here, dispatches it, and feeds the result back to the model.

This is the replacement for plnt's hardcoded `search`/`execute` pair. Plnt's
runner is for personal-runtime skills that touch the filesystem; plnt-cloud's
skills call domain tools (Places, BookingsStore, notify adapters).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from tenancy.context import TenantContext


@dataclass(frozen=True)
class Tool:
    """One callable plus the JSON schema Gemini sees.

    `schema` is the `parameters` block of an OpenAI-style function definition
    (a JSON Schema object describing the call's keyword arguments).
    """

    name: str
    description: str
    schema: dict[str, Any]
    fn: Callable[..., dict[str, Any]]

    def openai_spec(self) -> dict[str, Any]:
        """The shape required by the OpenAI-compatible `tools` array."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema,
            },
        }


_REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> Tool:
    """Add a Tool to the global registry. Raises on duplicate names."""
    if tool.name in _REGISTRY:
        raise ValueError(f"tool {tool.name!r} already registered")
    _REGISTRY[tool.name] = tool
    return tool


def get(name: str) -> Tool:
    """Look up a tool. Raises KeyError when the name is unknown — surfacing
    a missing tool is better than silently dropping the model's tool call.
    """
    if name not in _REGISTRY:
        raise KeyError(f"tool {name!r} not registered (have: {sorted(_REGISTRY)})")
    return _REGISTRY[name]


def specs_for(names: list[str]) -> list[dict[str, Any]]:
    """OpenAI-style tool definitions for the named subset, in the requested order."""
    return [get(n).openai_spec() for n in names]


def dispatch(name: str, ctx: TenantContext, args: dict[str, Any]) -> dict[str, Any]:
    """Invoke a registered tool. Caller catches and converts to tool_result."""
    return get(name).fn(ctx, **args)


def all_names() -> list[str]:
    return sorted(_REGISTRY)


# Importing the modules registers their tools as a side effect.
# Order matters only to keep this import list stable for diffs.
from microagents.tools import places as _places  # noqa: E402,F401
from microagents.tools import bookings as _bookings  # noqa: E402,F401
from microagents.tools import notify as _notify  # noqa: E402,F401
