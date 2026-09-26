"""Slice-9 salon tests — house-rules salon mode, catalog install, loader.

Salon schedules (services + stylists) yield per-stylist {time, stylist}
slots stepped by the service duration; restaurant schedules are untouched.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ADMIN_TOKEN = "test-admin-token"
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
TID = "t1"

# 2026-08-14 and 2026-08-21 are Fridays.
SALON_SCHEDULE = {
    "services": [
        {"name": "Haircut", "duration_min": 45},
        {"name": "Color", "duration_min": 90},
    ],
    "stylists": [
        {"name": "Priya", "hours": {"fri": [["10:00", "13:00"]]}},
        {"name": "Marco", "hours": {"fri": [["11:00", "12:30"]]}},
    ],
    "closed_dates": ["2026-08-21"],
}


# ─────────────────────────────────────────────────────────── house-rules salon mode


def test_salon_slots_per_stylist_stepped_by_duration():
    from providers.house_rules import HouseRulesAdapter

    adapter = HouseRulesAdapter(schedule=SALON_SCHEDULE)
    assert adapter.is_configured()

    slots = adapter.availability(
        provider_id="house", date_iso="2026-08-14", service_name="Haircut",
    )
    assert slots == [
        {"time": "2026-08-14T10:00:00", "stylist": "Priya"},
        {"time": "2026-08-14T10:45:00", "stylist": "Priya"},
        {"time": "2026-08-14T11:30:00", "stylist": "Priya"},
        {"time": "2026-08-14T12:15:00", "stylist": "Priya"},
        {"time": "2026-08-14T11:00:00", "stylist": "Marco"},
        {"time": "2026-08-14T11:45:00", "stylist": "Marco"},
    ]

    # 90-minute service steps wider and must fit before close.
    color = adapter.availability(
        provider_id="house", date_iso="2026-08-14", service_name="Color",
    )
    assert color == [
        {"time": "2026-08-14T10:00:00", "stylist": "Priya"},
        {"time": "2026-08-14T11:30:00", "stylist": "Priya"},
        {"time": "2026-08-14T11:00:00", "stylist": "Marco"},
    ]


def test_salon_closed_date_and_unknown_service_empty():
    from providers.house_rules import HouseRulesAdapter

    adapter = HouseRulesAdapter(schedule=SALON_SCHEDULE)
    assert adapter.availability(
        provider_id="house", date_iso="2026-08-21", service_name="Haircut",
    ) == []
    assert adapter.availability(
        provider_id="house", date_iso="2026-08-14", service_name="Facial",
    ) == []
    assert adapter.availability(provider_id="house", date_iso="2026-08-14") == []


def test_restaurant_schedule_unchanged():
    from providers.house_rules import HouseRulesAdapter

    schedule = {
        "open_hours": {"fri": [["18:00", "21:00"]]},
        "closed_dates": ["2026-08-15"],
        "turn_minutes": 60,
        "party_size_range": [1, 8],
    }
    adapter = HouseRulesAdapter(schedule=schedule)
    slots = adapter.availability(provider_id="house", date_iso="2026-08-14", party_size=2)
    assert slots == ["2026-08-14T18:00:00", "2026-08-14T19:00:00", "2026-08-14T20:00:00"]
    assert adapter.availability(provider_id="house", date_iso="2026-08-15", party_size=2) == []
    assert adapter.availability(provider_id="house", date_iso="2026-08-14", party_size=99) == []


# ─────────────────────────────────────────────────────────── marketplace install


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Isolated PLNT_CLOUD_HOME + a minimal app mounting only admin v2."""
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    monkeypatch.setenv("PLNT_CLOUD_MEMORY_BACKEND", "stub")
    monkeypatch.setenv("PLNT_CLOUD_ADMIN_TOKEN", ADMIN_TOKEN)

    from memory import memori_adapter as ma
    from tenancy import factory as tf
    from workflows import bookings_store as bs
    from services import orders_store as os_
    from microagents import loader

    for mod in (ma, tf, bs, os_, loader):
        mod.clear_cache()

    from surface.admin_v2 import router, marketplace_router
    app = FastAPI()
    app.include_router(router)
    app.include_router(marketplace_router)
    yield TestClient(app), tmp_path

    for mod in (ma, tf, bs, os_, loader):
        mod.clear_cache()


def test_install_booking_salon(client):
    c, tmp_path = client
    r = c.post(f"/v1/admin/tenants/{TID}/agents/booking-salon", headers=AUTH)
    assert r.status_code == 201
    row = r.json()
    assert row["slug"] == "booking-salon"
    assert row["version"] == "0.9.0"
    assert row["enabled"] is True
    assert row["config"]["confirm_before_mutation"] is True

    bundle = tmp_path / "tenants" / TID / "agents" / "booking-salon@0.9.0"
    assert (bundle / "skill.toml").exists()
    assert (bundle / "prompt.md").exists()
    assert (bundle / "config.json").exists()


def test_installed_salon_bundle_loads(client):
    c, _ = client
    r = c.post(f"/v1/admin/tenants/{TID}/agents/booking-salon", headers=AUTH)
    assert r.status_code == 201

    from microagents.loader import load_skill

    skill = load_skill("booking-salon", tenant_id=TID)
    assert skill.manifest["meta"]["version"] == "0.9.0"
    assert skill.tools == []
    assert skill.max_steps == 1
    assert skill.response_schema is not None
    assert skill.prompt.rstrip().endswith(
        'Respond with exactly `FINAL: <json>` and nothing else.'
    )
