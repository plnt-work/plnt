"""ProviderAdapter — abstract base for third-party booking platforms.

Concrete adapters (Resy, OpenTable, Zomato, etc.) implement:
  * search()    — discovery: find matching businesses on the platform
  * availability() — return real slots for a business on a date
  * book()      — create a reservation, return provider_ref + status
  * cancel()    — cancel a reservation by provider_ref

The saga uses these behind a common interface. Where the provider does
not expose a direct booking API (OpenTable, DoorDash), `book()` returns
`kind="deeplink"` with a URL that the client uses to hand off. Where a
direct API exists (Resy — unofficially), `book()` returns
`kind="confirmed"` with a `provider_ref`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderCandidate:
    """One discovery hit from a provider's search."""
    provider: str          # "resy" | "opentable" | ...
    provider_id: str       # provider's opaque id (e.g. resy venue id)
    name: str
    address: str = ""
    neighborhood: str = ""
    url: str = ""
    rating: float | None = None
    price_level: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResult:
    """Return shape for book() / cancel().

    kind:
      * "confirmed" — direct booking succeeded, provider_ref set
      * "deeplink"  — no direct API, provider_ref is a URL the client opens
      * "failed"    — provider rejected the request; `note` explains why
      * "unsupported" — provider adapter can't fulfil this request
    """
    kind: str
    provider: str
    provider_ref: str = ""
    note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderAdapter:
    """Abstract adapter. Subclasses override the three lifecycle methods."""

    name: str = "base"

    def is_configured(self) -> bool:
        """Whether this adapter has enough credentials/config to do live calls.

        Adapters that require an API key check env vars here. Callers use
        this to decide whether to skip the adapter entirely and stay on
        the local ledger.
        """
        return False

    # ── discovery ──
    def search(self, *, query: str, near: str = "", limit: int = 5) -> list[ProviderCandidate]:
        raise NotImplementedError

    # ── availability ──
    def availability(
        self,
        *,
        provider_id: str,
        date_iso: str,
        party_size: int = 2,
    ) -> list[str]:
        """Return a list of ISO 8601 slot datetimes."""
        raise NotImplementedError

    # ── booking ──
    def book(
        self,
        *,
        provider_id: str,
        slot: str,
        user_contact: str,
        party_size: int = 2,
        idempotency_key: str = "",
    ) -> ProviderResult:
        raise NotImplementedError

    def cancel(self, *, provider_ref: str, reason: str = "") -> ProviderResult:
        raise NotImplementedError
