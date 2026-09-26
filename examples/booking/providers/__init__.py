"""Provider adapters — third-party booking platforms (Resy, OpenTable, etc.).

Each provider is a subclass of `ProviderAdapter`. The registry lets the
saga discover an adapter by name and delegate discovery / availability /
booking to it. Providers are expected to be safe to instantiate even
without credentials — they surface `is_configured()` to gate live calls,
and callers fall back to the local ledger when no adapter is configured.
"""
from providers.base import ProviderAdapter, ProviderCandidate, ProviderResult
from providers.resy import ResyAdapter
from providers.registry import get_provider, list_providers, register_provider

__all__ = [
    "ProviderAdapter",
    "ProviderCandidate",
    "ProviderResult",
    "ResyAdapter",
    "get_provider",
    "list_providers",
    "register_provider",
]
