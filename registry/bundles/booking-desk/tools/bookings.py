"""Availability from the merchant's own schedule, and a per-tenant bookings ledger.

Everything is computed from this tenant's install config; bookings live in
SQLite under ctx.data_dir, which no other tenant can reach.
"""

from __future__ import annotations

import re
import secrets
import sqlite3
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from plnt import ToolContext, tool

_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_WINDOW = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")


def _tz(ctx: ToolContext) -> ZoneInfo:
    try:
        return ZoneInfo(str(ctx.config.get("timezone") or "UTC"))
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _now(ctx: ToolContext) -> datetime:
    return datetime.now(_tz(ctx)).replace(tzinfo=None)


def _resolve_date(raw: str, ctx: ToolContext) -> date:
    s = raw.strip().lower()
    today = _now(ctx).date()
    if s in ("today", "tonight"):
        return today
    if s == "tomorrow":
        return today + timedelta(days=1)
    if s in _DAY_NAMES:
        ahead = (_DAY_NAMES[s] - today.weekday()) % 7
        return today + timedelta(days=ahead)
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise ValueError(
            f"unrecognised date {raw!r}; use YYYY-MM-DD, today, tomorrow or a weekday"
        ) from None


def _db(ctx: ToolContext) -> sqlite3.Connection:
    assert ctx.data_dir is not None, "booking-desk needs a tenant data directory"
    c = sqlite3.connect(ctx.data_dir / "bookings.db", timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE IF NOT EXISTS bookings (ref TEXT PRIMARY KEY, day TEXT, slot TEXT, "
        "party INTEGER, name TEXT, contact TEXT, status TEXT, created_at TEXT)"
    )
    return c


def _slots(day: date, ctx: ToolContext) -> list[str]:
    cfg = ctx.config
    if day.isoformat() in (cfg.get("closed_dates") or []):
        return []
    step = timedelta(minutes=int(cfg.get("slot_minutes") or 30))
    out: list[str] = []
    for h1, m1, h2, m2 in _WINDOW.findall(str(cfg.get(f"hours_{_DAYS[day.weekday()]}") or "")):
        cur = datetime.combine(day, time(int(h1), int(m1)))
        end = datetime.combine(day, time(int(h2), int(m2)))
        while cur < end:
            out.append(cur.strftime("%H:%M"))
            cur += step
    return out


def _open_slots(day: date, party_size: int, ctx: ToolContext) -> list[str]:
    if party_size < 1 or party_size > int(ctx.config.get("max_party_size") or 8):
        return []
    now = _now(ctx)
    cap = int(ctx.config.get("tables_per_slot") or 4)
    with _db(ctx) as c:
        taken = dict(
            c.execute(
                "SELECT slot, COUNT(*) FROM bookings WHERE day = ? AND status = 'confirmed' "
                "GROUP BY slot",
                (day.isoformat(),),
            ).fetchall()
        )
    return [
        s
        for s in _slots(day, ctx)
        if taken.get(s, 0) < cap and datetime.combine(day, time.fromisoformat(s)) > now
    ]


@tool
def check_availability(date: str, party_size: int, ctx: ToolContext) -> dict:
    """List bookable start times for a date and party size.

    `date` may be YYYY-MM-DD, "today", "tomorrow" or a weekday name.
    """
    day = _resolve_date(date, ctx)
    max_party = int(ctx.config.get("max_party_size") or 8)
    if party_size > max_party:
        return {
            "date": day.isoformat(),
            "weekday": day.strftime("%A"),
            "slots": [],
            "note": f"the largest party we can book online is {max_party}",
        }
    slots = _open_slots(day, party_size, ctx)
    result = {"date": day.isoformat(), "weekday": day.strftime("%A"), "slots": slots}
    if not _slots(day, ctx):
        result["note"] = "closed on this day"
    elif not slots:
        result["note"] = "fully booked or no remaining times"
    return result


@tool
def book_table(
    date: str, time: str, party_size: int, name: str, contact: str, ctx: ToolContext
) -> dict:
    """Book a table. Only call after the customer confirmed all details."""
    day = _resolve_date(date, ctx)
    slot = time.strip()[:5]
    if not name.strip() or not contact.strip():
        return {"error": "name and contact are required"}
    unavailable = {
        "error": f"{slot} on {day.isoformat()} is not available for {party_size}; "
        "call check_availability and offer one of its times"
    }
    max_party = int(ctx.config.get("max_party_size") or 8)
    in_schedule = slot in _slots(day, ctx) and 1 <= party_size <= max_party
    if not in_schedule or datetime.combine(day, datetime.strptime(slot, "%H:%M").time()) <= _now(
        ctx
    ):
        return unavailable
    c = _db(ctx)
    try:
        # One write transaction for check-then-insert, so two customers can't
        # both take the last table in a slot.
        c.execute("BEGIN IMMEDIATE")
        existing = c.execute(
            "SELECT ref FROM bookings WHERE day = ? AND slot = ? AND contact = ? "
            "AND status = 'confirmed'",
            (day.isoformat(), slot, contact.strip()),
        ).fetchone()
        if existing:
            c.rollback()
            # A retry of the same booking returns the same reference.
            return {
                "reference": existing["ref"],
                "status": "already booked",
                "date": day.isoformat(),
                "time": slot,
            }
        (taken,) = c.execute(
            "SELECT COUNT(*) FROM bookings WHERE day = ? AND slot = ? AND status = 'confirmed'",
            (day.isoformat(), slot),
        ).fetchone()
        if taken >= int(ctx.config.get("tables_per_slot") or 4):
            c.rollback()
            return unavailable
        ref = "BK-" + secrets.token_hex(3).upper()
        c.execute(
            "INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?)",
            (
                ref,
                day.isoformat(),
                slot,
                party_size,
                name.strip(),
                contact.strip(),
                "confirmed",
                _now(ctx).isoformat(timespec="seconds"),
            ),
        )
        c.commit()
    finally:
        c.close()
    return {
        "reference": ref,
        "status": "confirmed",
        "date": day.isoformat(),
        "weekday": day.strftime("%A"),
        "time": slot,
        "party_size": party_size,
        "restaurant": ctx.config.get("business_name"),
    }


@tool
def cancel_booking(reference: str, contact: str, ctx: ToolContext) -> dict:
    """Cancel a booking. The contact must match the one used to book."""
    with _db(ctx) as c:
        row = c.execute(
            "SELECT * FROM bookings WHERE ref = ?", (reference.strip().upper(),)
        ).fetchone()
        if row is None or row["contact"] != contact.strip():
            return {"error": "no booking found with that reference and contact"}
        if row["status"] == "cancelled":
            return {"reference": row["ref"], "status": "already cancelled"}
        c.execute("UPDATE bookings SET status = 'cancelled' WHERE ref = ?", (row["ref"],))
    return {"reference": row["ref"], "status": "cancelled", "date": row["day"], "time": row["slot"]}
