from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from plnt.bundles import load_bundle
from plnt.bundles.sdk import ToolContext
from plnt.executors import LocalExecutor
from plnt.models import ChatResult, ScriptedProvider, ToolCall
from plnt.tenancy import TenantStore, installs

BUNDLE = Path(__file__).parents[1] / "registry" / "bundles" / "booking-desk"
FRIDAY = "2030-01-04"  # a Friday, safely in the future


@pytest.fixture
def desk():
    return load_bundle(BUNDLE)


def _ctx(desk, tmp_path, **cfg):
    config = desk.validate_config(
        {
            "business_name": "Luigi's",
            "handoff_contact": "+39 06 555",
            "timezone": "Europe/Rome",
            "hours_fri": "12:00-13:00, 19:00-20:00",
            "tables_per_slot": 1,
            "max_party_size": 6,
            **cfg,
        }
    )
    return ToolContext("luigis", "s1", "booking-desk", config=config, data_dir=tmp_path)


def call(desk, tool_name, ctx, **args):
    return desk.tools[tool_name].call(args, ctx)


def test_slots_come_from_the_schedule(desk, tmp_path):
    ctx = _ctx(desk, tmp_path)
    r = call(desk, "check_availability", ctx, date=FRIDAY, party_size=2)
    assert r["weekday"] == "Friday"
    assert r["slots"] == ["12:00", "12:30", "19:00", "19:30"]
    closed = call(desk, "check_availability", ctx, date="2030-01-05", party_size=2)
    assert closed["slots"] == [] and closed["note"] == "closed on this day"


def test_party_size_and_closed_dates(desk, tmp_path):
    ctx = _ctx(desk, tmp_path, closed_dates=[FRIDAY])
    assert call(desk, "check_availability", ctx, date=FRIDAY, party_size=2)["slots"] == []
    big = call(desk, "check_availability", _ctx(desk, tmp_path), date=FRIDAY, party_size=9)
    assert big["slots"] == [] and "largest party" in big["note"]


def test_booking_fills_capacity_and_is_idempotent(desk, tmp_path):
    ctx = _ctx(desk, tmp_path)
    b = call(
        desk,
        "book_table",
        ctx,
        date=FRIDAY,
        time="19:00",
        party_size=2,
        name="Ada",
        contact="ada@example.com",
    )
    assert b["status"] == "confirmed" and b["reference"].startswith("BK-")
    again = call(
        desk,
        "book_table",
        ctx,
        date=FRIDAY,
        time="19:00",
        party_size=2,
        name="Ada",
        contact="ada@example.com",
    )
    assert again == {
        "reference": b["reference"],
        "status": "already booked",
        "date": FRIDAY,
        "time": "19:00",
    }
    # tables_per_slot = 1: 19:00 is gone for everyone else
    assert "19:00" not in call(desk, "check_availability", ctx, date=FRIDAY, party_size=2)["slots"]
    other = call(
        desk,
        "book_table",
        ctx,
        date=FRIDAY,
        time="19:00",
        party_size=2,
        name="Bo",
        contact="bo@example.com",
    )
    assert "not available" in other["error"]


def test_cannot_book_a_time_that_does_not_exist(desk, tmp_path):
    ctx = _ctx(desk, tmp_path)
    r = call(
        desk, "book_table", ctx, date=FRIDAY, time="16:00", party_size=2, name="Ada", contact="a@x"
    )
    assert "not available" in r["error"]


def test_cancel_requires_matching_contact(desk, tmp_path):
    ctx = _ctx(desk, tmp_path)
    ref = call(
        desk, "book_table", ctx, date=FRIDAY, time="12:00", party_size=2, name="Ada", contact="a@x"
    )["reference"]
    assert "error" in call(desk, "cancel_booking", ctx, reference=ref, contact="someone@else")
    assert (
        call(desk, "cancel_booking", ctx, reference=ref.lower(), contact="a@x")["status"]
        == "cancelled"
    )
    assert "12:00" in call(desk, "check_availability", ctx, date=FRIDAY, party_size=2)["slots"]


def test_relative_dates_and_past_times(desk, tmp_path):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    every_day = {
        f"hours_{d}": "00:00-23:59" for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    }
    ctx = _ctx(desk, tmp_path, slot_minutes=60, **every_day)
    today = datetime.now(ZoneInfo("Europe/Rome")).date()
    r = call(desk, "check_availability", ctx, date="today", party_size=2)
    assert r["date"] == today.isoformat()
    now_hour = datetime.now(ZoneInfo("Europe/Rome")).hour
    assert all(int(s[:2]) > now_hour for s in r["slots"])  # past hours excluded
    assert (
        call(desk, "check_availability", ctx, date="tomorrow", party_size=2)["date"]
        == (today + timedelta(days=1)).isoformat()
    )
    fri = call(desk, "check_availability", ctx, date="Friday", party_size=2)
    assert date.fromisoformat(fri["date"]).weekday() == 4
    with pytest.raises(ValueError):
        call(desk, "check_availability", ctx, date="someday", party_size=2)


def test_ledgers_are_per_tenant_through_the_executor(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    store = TenantStore(tmp_path / "tenants")

    def script(messages, tools):
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        if not tool_msgs:
            return ChatResult(
                tool_calls=[ToolCall("a", "check_availability", {"date": FRIDAY, "party_size": 2})]
            )
        if len(tool_msgs) == 1:
            return ChatResult(
                tool_calls=[
                    ToolCall(
                        "b",
                        "book_table",
                        {
                            "date": FRIDAY,
                            "time": "19:00",
                            "party_size": 2,
                            "name": "Ada",
                            "contact": "ada@example.com",
                        },
                    )
                ]
            )
        return ChatResult(content=f"Booked: {tool_msgs[-1]['content']}")

    ex = LocalExecutor(store, provider_factory=lambda p: ScriptedProvider(script))
    for tid in ("luigis", "marios"):
        t, _ = store.create(tid)
        installs.install(
            t,
            load_bundle(BUNDLE),
            {
                "business_name": tid,
                "handoff_contact": "x",
                "hours_fri": "19:00-20:00",
                "tables_per_slot": 1,
            },
        )
        sid = ex.start_session(tid, "booking-desk")
        ex.send(tid, sid, "table for 2 friday 7pm, Ada, ada@example.com", wait=True)
        answer = [e for e in ex.events_since(tid, sid) if e["kind"] == "assistant_message"]
        # Each tenant's 19:00 slot is its own: both bookings succeed.
        assert answer and '"status": "confirmed"' in answer[0]["payload"]["text"], tid
        assert (t.home / "data" / "booking-desk" / "bookings.db").is_file()


def test_concurrent_bookings_cannot_overbook(desk, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    ctx = _ctx(desk, tmp_path)  # tables_per_slot = 1

    def attempt(i: int) -> dict:
        return call(
            desk,
            "book_table",
            ctx,
            date=FRIDAY,
            time="12:30",
            party_size=2,
            name=f"guest{i}",
            contact=f"g{i}@example.com",
        )

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(attempt, range(8)))
    confirmed = [r for r in results if r.get("status") == "confirmed"]
    assert len(confirmed) == 1, results
    assert all("not available" in r["error"] for r in results if r not in confirmed)
