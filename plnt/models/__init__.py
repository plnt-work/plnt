"""plnt.models — one interface over local and hosted models.

    from plnt.models import resolve_profile, get_provider, chat

    profile = resolve_profile("small")         # env-driven: local → cloud → error
    provider = get_provider(profile)
    result = chat(provider, messages, tools=tool_specs)

`chat()` uses native tool calling and transparently falls back to the JSON
shim when a model rejects tools (or when PLNT_NATIVE_TOOLS=0). Errors always
raise a `ModelError` subclass carrying a user-actionable `hint`.
"""

from __future__ import annotations

from typing import Any

from plnt.models.errors import (
    ModelBadResponse,
    ModelError,
    ModelNotPulled,
    ModelTimeout,
    ModelUnavailable,
    NoModelConfigured,
    ToolsUnsupported,
)
from plnt.models.offline import OFFLINE_PREFIX, OfflineProvider, ScriptedProvider
from plnt.models.ollama import OllamaProvider
from plnt.models.openai_compat import OpenAICompatProvider
from plnt.models.profiles import ModelProfile, resolve_profile
from plnt.models.shim import chat_via_shim
from plnt.models.types import ChatResult, HealthReport, ModelProvider, ToolCall, Usage

__all__ = [
    "ChatResult",
    "HealthReport",
    "ModelBadResponse",
    "ModelError",
    "ModelNotPulled",
    "ModelProfile",
    "ModelProvider",
    "ModelTimeout",
    "ModelUnavailable",
    "NoModelConfigured",
    "OFFLINE_PREFIX",
    "OfflineProvider",
    "OllamaProvider",
    "OpenAICompatProvider",
    "ScriptedProvider",
    "ToolCall",
    "ToolsUnsupported",
    "Usage",
    "chat",
    "get_provider",
    "resolve_profile",
]


def get_provider(profile: ModelProfile) -> ModelProvider:
    if profile.provider == "ollama":
        return OllamaProvider(profile)
    if profile.provider == "openai":
        return OpenAICompatProvider(profile)
    if profile.provider == "offline":
        return OfflineProvider(profile)
    raise ValueError(f"unknown provider {profile.provider!r}")


def chat(
    provider: ModelProvider,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    response_schema: dict[str, Any] | None = None,
    timeout: float | None = None,
    native_tools: str | None = None,
) -> ChatResult:
    """One model turn, native tools first, JSON shim as fallback."""
    if not tools:
        return provider.chat(messages, response_schema=response_schema, timeout=timeout)
    mode = native_tools or getattr(getattr(provider, "profile", None), "native_tools", "auto")
    if mode == "off":
        return chat_via_shim(provider, messages, tools, timeout=timeout)
    try:
        return provider.chat(messages, tools=tools, timeout=timeout)
    except ToolsUnsupported:
        if mode == "on":
            raise
        return chat_via_shim(provider, messages, tools, timeout=timeout)
