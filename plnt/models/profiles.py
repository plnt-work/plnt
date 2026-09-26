"""ModelProfile — everything needed to call one model — and env resolution.

Resolution order for `resolve_profile()`:
  1. `PLNT_FORCE` (or the `force=` argument): local | cloud | offline
  2. local  — when the local endpoint accepts a TCP connection
  3. cloud  — when PLNT_CLOUD_URL + PLNT_CLOUD_API_KEY + PLNT_CLOUD_SMALL_MODEL are set
  4. otherwise raise `NoModelConfigured` with instructions

"offline" is never chosen implicitly. It is a deterministic stand-in for
hermetic tests and demos, selected only with PLNT_FORCE=offline.

Environment:
  PLNT_LOCAL_URL (alias PLNT_COMPUTE_URL)   default http://127.0.0.1:11434
  PLNT_LOCAL_PROVIDER                       ollama | openai  (default: guessed from URL)
  PLNT_PLANNER_MODEL / PLNT_DEEP_MODEL      local small / deep model names
  PLNT_CLOUD_URL, PLNT_CLOUD_API_KEY, PLNT_CLOUD_SMALL_MODEL, PLNT_CLOUD_DEEP_MODEL
  PLNT_NUM_CTX          context window requested from local models (default 8192)
  PLNT_TEMPERATURE      default 0.2
  PLNT_MAX_TOKENS       default 2048
  PLNT_MODEL_TIMEOUT    seconds per call (default 120)
  PLNT_NATIVE_TOOLS     auto | 1 | 0   (0 forces the JSON tool shim)
  PLNT_COST_IN_PER_M / PLNT_COST_OUT_PER_M   USD per 1M tokens, for cost metering
  PLNT_REQUIRED_PATH    local is only used when this directory exists (e.g. an external drive)
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from plnt.models.errors import NoModelConfigured

ProviderKind = Literal["ollama", "openai", "offline"]
Force = Literal["auto", "local", "cloud", "offline"]
Hint = Literal["small", "deep", "auto"]


@dataclass(frozen=True)
class ModelProfile:
    provider: ProviderKind
    base_url: str
    model: str
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 2048
    num_ctx: int = 8192
    timeout: float = 120.0
    native_tools: Literal["auto", "on", "off"] = "auto"
    cost_in_per_m: float = 0.0
    cost_out_per_m: float = 0.0
    # Which slot this came from: "local" | "cloud" | "offline" | "explicit".
    source: str = "explicit"
    reason: str = ""

    def with_timeout(self, seconds: float) -> ModelProfile:
        return replace(self, timeout=max(1.0, float(seconds)))

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens * self.cost_in_per_m + completion_tokens * self.cost_out_per_m
        ) / 1_000_000

    def to_event(self) -> dict:
        """Audit-safe view. Never includes the API key."""
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "source": self.source,
            "reason": self.reason,
        }


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name) or default)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


def _native_tools() -> Literal["auto", "on", "off"]:
    v = _env("PLNT_NATIVE_TOOLS", "auto").lower()
    if v in ("1", "on", "true", "yes"):
        return "on"
    if v in ("0", "off", "false", "no"):
        return "off"
    return "auto"


def guess_local_provider(url: str) -> ProviderKind:
    explicit = _env("PLNT_LOCAL_PROVIDER").lower()
    if explicit in ("ollama", "openai"):
        return explicit  # type: ignore[return-value]
    # Ollama's native API lives at the server root; OpenAI-compatible servers
    # (llama.cpp, vLLM, LM Studio) are configured with a /v1 base URL.
    return "openai" if "/v1" in urlparse(url).path else "ollama"


def tcp_reachable(url: str, timeout: float = 0.5) -> bool:
    try:
        u = urlparse(url)
        host = u.hostname or "127.0.0.1"
        port = u.port or (443 if u.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def _required_path_ok() -> bool:
    req = _env("PLNT_REQUIRED_PATH")
    if not req:
        return True
    try:
        return Path(req).is_dir()
    except OSError:
        return False


def local_profile(hint: Hint = "auto") -> ModelProfile:
    url = _env("PLNT_LOCAL_URL") or _env("PLNT_COMPUTE_URL") or "http://127.0.0.1:11434"
    small = _env("PLNT_PLANNER_MODEL", "llama3.2:3b")
    deep = _env("PLNT_DEEP_MODEL", "llama3.1:8b")
    return ModelProfile(
        provider=guess_local_provider(url),
        base_url=url,
        model=deep if hint == "deep" else small,
        api_key=_env("PLNT_LOCAL_API_KEY"),
        temperature=_env_float("PLNT_TEMPERATURE", 0.2),
        max_tokens=_env_int("PLNT_MAX_TOKENS", 2048),
        num_ctx=_env_int("PLNT_NUM_CTX", 8192),
        timeout=_env_float("PLNT_MODEL_TIMEOUT", 120.0),
        native_tools=_native_tools(),
        cost_in_per_m=_env_float("PLNT_COST_IN_PER_M", 0.0),
        cost_out_per_m=_env_float("PLNT_COST_OUT_PER_M", 0.0),
        source="local",
    )


def cloud_profile(hint: Hint = "auto") -> ModelProfile | None:
    url = _env("PLNT_CLOUD_URL")
    key = _env("PLNT_CLOUD_API_KEY")
    small = _env("PLNT_CLOUD_SMALL_MODEL")
    if not (url and key and small):
        return None
    deep = _env("PLNT_CLOUD_DEEP_MODEL") or small
    return ModelProfile(
        provider="openai",
        base_url=url,
        model=deep if hint == "deep" else small,
        api_key=key,
        temperature=_env_float("PLNT_TEMPERATURE", 0.2),
        max_tokens=_env_int("PLNT_MAX_TOKENS", 2048),
        timeout=_env_float("PLNT_MODEL_TIMEOUT", 120.0),
        native_tools=_native_tools(),
        cost_in_per_m=_env_float("PLNT_COST_IN_PER_M", 0.0),
        cost_out_per_m=_env_float("PLNT_COST_OUT_PER_M", 0.0),
        source="cloud",
    )


def offline_profile() -> ModelProfile:
    return ModelProfile(
        provider="offline", base_url="", model="offline-echo", source="offline", reason="forced"
    )


def resolve_profile(hint: Hint = "auto", force: Force | None = None) -> ModelProfile:
    """Pick the model for one call. See module docstring for the order."""
    force = force or (_env("PLNT_FORCE", "auto").lower() or "auto")  # type: ignore[assignment]
    if force == "offline":
        return offline_profile()
    if force == "local":
        return replace(local_profile(hint), reason="forced")
    if force == "cloud":
        cp = cloud_profile(hint)
        if cp is None:
            raise NoModelConfigured(
                "PLNT_FORCE=cloud but the cloud model is not configured",
                hint="set PLNT_CLOUD_URL, PLNT_CLOUD_API_KEY and PLNT_CLOUD_SMALL_MODEL",
            )
        return replace(cp, reason="forced")

    lp = local_profile(hint)
    if _required_path_ok() and tcp_reachable(lp.base_url):
        return replace(lp, reason="local endpoint reachable")
    cp = cloud_profile(hint)
    if cp is not None:
        why = "required path missing" if not _required_path_ok() else "local endpoint unreachable"
        return replace(cp, reason=f"{why}; using cloud")
    raise NoModelConfigured(
        f"no model available: local endpoint {lp.base_url} is unreachable and no cloud model "
        "is configured",
        hint=(
            "start a local server (e.g. `ollama serve` then `ollama pull "
            f"{lp.model}`), or set PLNT_CLOUD_URL / PLNT_CLOUD_API_KEY / "
            "PLNT_CLOUD_SMALL_MODEL, or PLNT_FORCE=offline for a deterministic stub"
        ),
    )
