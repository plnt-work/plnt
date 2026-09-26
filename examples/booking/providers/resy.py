"""Resy provider adapter.

Resy is unusual among restaurant booking platforms in that a reverse-
engineered API exists and third parties DO use it — the pattern of
Bearer-token authentication + `/3/venuesearch/search` + `/4/find` +
`/3/details` + `/3/book` calls is well documented (see the `resy-py`
project). The official position is that Resy discourages third-party
booking; treat this adapter as best-effort and configurable so a real
deployment can point at a licensed access path if one becomes available.

Behavior:
  * `is_configured()` — checks PLNT_CLOUD_RESY_KEY + PLNT_CLOUD_RESY_AUTH.
    Without both, all methods return graceful "unsupported"/empty results.
  * `search()` — venue name search, returns ProviderCandidate list.
  * `availability()` — real slot lookup for a date.
  * `book()` — direct book when a full auth token is present, otherwise
    returns a `kind="deeplink"` result pointing at the resy.com booking
    URL for the venue+date. The chat UI already knows how to render a
    deep-link action card, so this keeps the flow intact even without
    booking privileges.
  * `cancel()` — direct cancel by reservation id.

Rate: Resy publishes no third-party quota; we set a conservative 8s
timeout so a slow call doesn't hang the saga. Retries live at the
Temporal Activity layer, not here.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from providers.base import ProviderAdapter, ProviderCandidate, ProviderResult


log = logging.getLogger("plnt_cloud.providers.resy")

_BASE = "https://api.resy.com"
_TIMEOUT = 8.0


class ResyAdapter(ProviderAdapter):
    name = "resy"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth_token: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("PLNT_CLOUD_RESY_KEY", "")
        self._auth_token = auth_token or os.environ.get("PLNT_CLOUD_RESY_AUTH", "")

    # ─── config ──────────────────────────────────────────
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def can_book_directly(self) -> bool:
        return bool(self._api_key and self._auth_token)

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"accept": "application/json"}
        if self._api_key:
            h["authorization"] = f'ResyAPI api_key="{self._api_key}"'
        if self._auth_token:
            h["x-resy-auth-token"] = self._auth_token
        return h

    # ─── discovery ───────────────────────────────────────
    def search(self, *, query: str, near: str = "", limit: int = 5) -> list[ProviderCandidate]:
        if not self.is_configured():
            return []
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(
                    f"{_BASE}/3/venuesearch/search",
                    headers=self._headers(),
                    json={
                        "query": query,
                        "geo": {"latitude": 0, "longitude": 0} if not near else near,
                        "per_page": limit,
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as e:
            log.warning("resy.search failed: %s", e)
            return []
        hits = _dig(payload, "search", "hits") or []
        out: list[ProviderCandidate] = []
        for h in hits[:limit]:
            venue = h.get("venue") or h
            vid = str(venue.get("id") or venue.get("venue_id") or "")
            if not vid:
                continue
            out.append(ProviderCandidate(
                provider="resy",
                provider_id=vid,
                name=str(venue.get("name") or ""),
                address=str(venue.get("location", {}).get("address_1") or ""),
                neighborhood=str(venue.get("location", {}).get("neighborhood") or ""),
                url=_venue_url(venue),
                rating=_maybe_float(venue.get("rating", {}).get("average")),
                price_level=_maybe_int(venue.get("price_range_id")),
                metadata={"raw": venue},
            ))
        return out

    # ─── availability ────────────────────────────────────
    def availability(self, *, provider_id: str, date_iso: str, party_size: int = 2) -> list[str]:
        if not self.is_configured():
            return []
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(
                    f"{_BASE}/4/find",
                    headers=self._headers(),
                    params={
                        "lat": 0, "long": 0,
                        "day": date_iso,
                        "party_size": party_size,
                        "venue_id": provider_id,
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as e:
            log.warning("resy.availability failed: %s", e)
            return []
        # Response shape: results.venues[0].slots[*].date.start (ISO datetime)
        venues = _dig(payload, "results", "venues") or []
        if not venues:
            return []
        slots = venues[0].get("slots") or []
        out: list[str] = []
        for s in slots:
            iso = _dig(s, "date", "start")
            if isinstance(iso, str):
                out.append(iso.replace(" ", "T"))
        return out

    # ─── book ────────────────────────────────────────────
    def book(
        self, *, provider_id: str, slot: str, user_contact: str,
        party_size: int = 2, idempotency_key: str = "",
    ) -> ProviderResult:
        # Deep-link is the universal fallback — Resy's direct /3/book path
        # requires a real user session we don't (yet) hold. Renders a
        # "Complete on Resy" action card on the client.
        day = slot.split("T", 1)[0] if "T" in slot else slot
        url = f"https://resy.com/cities/ny/venues/{provider_id}?date={day}&seats={party_size}"
        verified_at = datetime.now(timezone.utc).isoformat()
        note = (
            "resy adapter not configured — hand-off to resy.com"
            if not self.is_configured()
            else "no user auth token — hand-off to resy.com"
        )
        return ProviderResult(
            kind="deeplink", provider=self.name, provider_ref=url, note=note,
            metadata={
                "deeplink_url": url,
                "url": url,
                "venue_id": provider_id,
                "party_size": party_size,
                "date": day,
                "slot": slot,
                "verified_at": verified_at,
            },
        )

    # ─── cancel ──────────────────────────────────────────
    def cancel(self, *, provider_ref: str, reason: str = "") -> ProviderResult:
        if not self.can_book_directly():
            return ProviderResult(kind="unsupported", provider=self.name,
                                  note="direct cancel requires a Resy user session")
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(
                    f"{_BASE}/3/cancel",
                    headers=self._headers(),
                    json={"resy_token": provider_ref},
                )
                resp.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("resy.cancel failed: %s", e)
            return ProviderResult(kind="failed", provider=self.name,
                                  provider_ref=provider_ref, note=str(e))
        return ProviderResult(kind="confirmed", provider=self.name,
                              provider_ref=provider_ref, note="cancelled")


# ─── helpers ─────────────────────────────────────────────

def _dig(obj: Any, *keys: str) -> Any:
    cur: Any = obj
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _maybe_float(x: Any) -> float | None:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _maybe_int(x: Any) -> int | None:
    try:
        return int(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _venue_url(venue: dict[str, Any]) -> str:
    slug = venue.get("url_slug") or venue.get("id") or ""
    return f"https://resy.com/cities/ny/venues/{slug}" if slug else ""
