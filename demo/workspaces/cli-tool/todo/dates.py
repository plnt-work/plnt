"""Date helpers."""

from __future__ import annotations

from datetime import date


def parse_due(text: str) -> date:
    """Parse an ISO date or the words `today` / `tomorrow`."""
    t = text.strip().lower()
    if t == "today":
        return date.today()
    if t == "tomorrow":
        return date.today().replace(day=date.today().day + 1)
    return date.fromisoformat(t)


def is_overdue(due: str | None, today: date | None = None) -> bool:
    if not due:
        return False
    today = today or date.today()
    return date.fromisoformat(due) < today
