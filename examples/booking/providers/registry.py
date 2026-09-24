"""Provider registry — lazy singletons keyed by adapter name."""
from __future__ import annotations

from typing import Dict

from providers.base import ProviderAdapter


_REGISTRY: Dict[str, ProviderAdapter] = {}


def register_provider(adapter: ProviderAdapter) -> None:
    _REGISTRY[adapter.name] = adapter


def get_provider(name: str) -> ProviderAdapter | None:
    _ensure_defaults()
    return _REGISTRY.get(name)


def list_providers() -> list[str]:
    _ensure_defaults()
    return sorted(_REGISTRY.keys())


def _ensure_defaults() -> None:
    if _REGISTRY:
        return
    # Import here to avoid a top-level circular import (providers/__init__
    # re-exports from this module).
    from providers.resy import ResyAdapter
    from providers.house_rules import HouseRulesAdapter
    register_provider(ResyAdapter())
    register_provider(HouseRulesAdapter())
