"""House-rules provider — schedule-driven adapter for merchants without a
third-party booking backend. Reads a JSON schedule from tenant integrations
and generates slot candidates locally.

Schedule schema (restaurant mode):
    {
      "open_hours": {"mon": [["11:00","22:00"]], "tue": [["11:00","22:00"]], ...},
      "closed_dates": ["2026-08-15", ...],
      "turn_minutes": 90,
      "party_size_range": [1, 8]
    }

Salon mode — when `services` and `stylists` are both present, availability
is per-stylist, stepped by the requested service's duration, and each slot
is `{"time": iso, "stylist": name}`:
    {
      "services": [{"name": "Haircut", "duration_min": 45}, ...],
      "stylists": [{"name": "Priya", "hours": {"mon": [["10:00","18:00"]], ...}}, ...],
      "closed_dates": [...]
    }
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from providers.base import ProviderAdapter, ProviderCandidate, ProviderResult


_DOW = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class HouseRulesAdapter(ProviderAdapter):
    name = "house_rules"

    def __init__(self, schedule: dict[str, Any] | None = None) -> None:
        self._schedule = schedule or {}

    def is_configured(self) -> bool:
        return bool(self._schedule.get("open_hours") or self._salon_mode())

    def _salon_mode(self) -> bool:
        return bool(self._schedule.get("services") and self._schedule.get("stylists"))

    def search(self, *, query: str, near: str = "", limit: int = 5) -> list[ProviderCandidate]:
        # House-rules doesn't discover — the merchant IS the candidate.
        # Caller supplies name/place via the provider_id path.
        return [ProviderCandidate(
            provider=self.name, provider_id=query or "house", name=query or "",
        )]

    def availability(
        self, *, provider_id: str, date_iso: str, party_size: int = 2,
        service_name: str = "",
    ) -> list[Any]:
        if date_iso in set(self._schedule.get("closed_dates") or []):
            return []
        try:
            d = date.fromisoformat(date_iso)
        except ValueError:
            return []
        if self._salon_mode():
            return self._salon_slots(d, service_name)
        lo, hi = self._schedule.get("party_size_range") or [1, 99]
        if not (int(lo) <= party_size <= int(hi)):
            return []
        windows = (self._schedule.get("open_hours") or {}).get(_DOW[d.weekday()]) or []
        turn = int(self._schedule.get("turn_minutes") or 60)
        return self._window_slots(d, windows, turn)

    def _window_slots(
        self, d: date, windows: list[Any], step_min: int, *, must_fit: bool = False,
    ) -> list[str]:
        """ISO slot starts stepped through each [start, end] window.
        `must_fit` requires the full step to end before the window closes."""
        step = timedelta(minutes=step_min)
        out: list[str] = []
        for w in windows:
            if not (isinstance(w, (list, tuple)) and len(w) == 2):
                continue
            try:
                start_t = time.fromisoformat(str(w[0]))
                end_t = time.fromisoformat(str(w[1]))
            except ValueError:
                continue
            cur = datetime.combine(d, start_t)
            end = datetime.combine(d, end_t)
            while cur < end and (not must_fit or cur + step <= end):
                out.append(cur.isoformat())
                cur += step
        return out

    def _salon_slots(self, d: date, service_name: str) -> list[dict[str, str]]:
        """Per-stylist {time, stylist} slots stepped by the service duration."""
        durations = {
            str(s.get("name") or "").lower(): int(s.get("duration_min") or 0)
            for s in self._schedule.get("services") or []
        }
        duration = durations.get(service_name.lower())
        if not duration:
            return []
        out: list[dict[str, str]] = []
        for stylist in self._schedule.get("stylists") or []:
            name = str(stylist.get("name") or "")
            windows = (stylist.get("hours") or {}).get(_DOW[d.weekday()]) or []
            for t in self._window_slots(d, windows, duration, must_fit=True):
                out.append({"time": t, "stylist": name})
        return out

    def book(
        self, *, provider_id: str, slot: str, user_contact: str,
        party_size: int = 2, idempotency_key: str = "",
    ) -> ProviderResult:
        return ProviderResult(
            kind="house_confirmed", provider=self.name,
            provider_ref=idempotency_key or slot,
            metadata={
                "slot": slot, "party_size": party_size,
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def cancel(self, *, provider_ref: str, reason: str = "") -> ProviderResult:
        return ProviderResult(
            kind="house_confirmed", provider=self.name,
            provider_ref=provider_ref, note="cancelled",
        )
