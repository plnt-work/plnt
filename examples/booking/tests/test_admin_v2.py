"""Slice-3 admin v2 endpoint tests — seeded tenant against a tmp PLNT_CLOUD_HOME.

Covers the contract in web/src/lib/api/admin-v2.ts: bookings (merged
ledgers + filters), sessions/transcript derived from audit events,
marketplace catalog, and the filesystem install/patch/uninstall flow
whose semantics the slice-2 loader consumes.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ADMIN_TOKEN = "test-admin-token"
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
TID = "t1"


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


def _seed_bookings():
    from workflows.bookings_store import bookings_for
    from services.orders_store import orders_for

    store = bookings_for(TID)
    store.upsert_confirmed(
        idempotency_key="k1", booking_id="bkg_1", business_id="biz-1",
        slot="2026-08-08T19:00:00", user_contact="user-a",
    )
    store.upsert_confirmed(
        idempotency_key="k2", booking_id="bkg_2", business_id="biz-1",
        slot="2026-08-09T20:00:00", user_contact="user-b",
    )
    store.cancel("bkg_2", "test")
    orders_for(TID).create_order(
        tenant_id=TID, user_id="user-a", place_id="biz-2", venue_name="Venue",
        date="2026-08-09", slot="10:00", pro_id="pro-1",
        services=[{"id": "s1", "name": "cut", "duration_min": 30, "price_cents": 500}],
        idempotency_key="ok1",
    )


def _seed_audit():
    from tenancy.audit import write_event

    for role in ("classify_intent", "resolve_business", "synthesize_response"):
        write_event(tenant_id=TID, session_id="s1", user_id="user-a", role=role)
    for role in ("classify_intent", "synthesize_response"):
        write_event(tenant_id=TID, session_id="s2", user_id="user-b", role=role)


# ─────────────────────────────────────────────────────────── auth


def test_bad_token_rejected(client):
    c, _ = client
    r = c.get(f"/v1/admin/tenants/{TID}/bookings", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


# ─────────────────────────────────────────────────────────── bookings


def test_bookings_list_and_filters(client):
    c, _ = client
    _seed_bookings()

    r = c.get(f"/v1/admin/tenants/{TID}/bookings", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["bookings"]) == 3
    for b in body["bookings"]:
        assert set(b) == {
            "booking_id", "user_id", "business_id", "slot",
            "status", "idempotency_key", "created_at",
        }

    r = c.get(f"/v1/admin/tenants/{TID}/bookings?status=cancelled", headers=AUTH)
    body = r.json()
    assert body["total"] == 1
    assert body["bookings"][0]["booking_id"] == "bkg_2"

    r = c.get(f"/v1/admin/tenants/{TID}/bookings?user_id=user-a", headers=AUTH)
    body = r.json()
    assert body["total"] == 2
    assert {b["user_id"] for b in body["bookings"]} == {"user-a"}

    r = c.get(f"/v1/admin/tenants/{TID}/bookings?limit=1", headers=AUTH)
    body = r.json()
    assert body["total"] == 3 and len(body["bookings"]) == 1


# ─────────────────────────────────────────────────────────── sessions + transcript


def test_sessions_derived_from_audit(client):
    c, _ = client
    _seed_audit()

    r = c.get(f"/v1/admin/tenants/{TID}/sessions", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    by_sid = {s["session_id"]: s for s in body["sessions"]}
    assert by_sid["s1"]["message_count"] == 3
    assert by_sid["s1"]["user_id"] == "user-a"
    assert by_sid["s1"]["status"] == "active"  # just written
    assert by_sid["s1"]["started_at"] <= by_sid["s1"]["last_message_at"]

    r = c.get(f"/v1/admin/tenants/{TID}/sessions?user_id=user-b", headers=AUTH)
    body = r.json()
    assert body["total"] == 1
    assert body["sessions"][0]["session_id"] == "s2"


def test_transcript_for_session(client):
    c, _ = client
    _seed_audit()

    r = c.get(f"/v1/admin/tenants/{TID}/sessions/s1/transcript", headers=AUTH)
    assert r.status_code == 200
    entries = r.json()["transcript"]
    assert [e["seq"] for e in entries] == [1, 2, 3]
    assert [e["role"] for e in entries] == [
        "classify_intent", "resolve_business", "synthesize_response",
    ]
    for e in entries:
        assert isinstance(e["content"], dict)
        assert isinstance(e["at"], float)


# ─────────────────────────────────────────────────────────── users


def test_users_aggregate_audit_and_bookings(client):
    c, _ = client
    _seed_bookings()
    _seed_audit()

    r = c.get(f"/v1/admin/tenants/{TID}/users", headers=AUTH)
    users = {u["user_id"]: u for u in r.json()["users"]}
    assert users["user-a"]["sessions"] == 1
    assert users["user-a"]["bookings"] == 2  # ledger + order
    assert users["user-b"]["bookings"] == 1

    r = c.get(f"/v1/admin/tenants/{TID}/users/user-a", headers=AUTH)
    detail = r.json()
    assert detail["user_id"] == "user-a"
    assert len(detail["bookings"]) == 2
    assert len(detail["sessions"]) == 1


# ─────────────────────────────────────────────────────────── marketplace


def test_marketplace_catalog(client):
    c, _ = client
    r = c.get("/v1/marketplace/agents", headers=AUTH)
    assert r.status_code == 200
    agents = r.json()["agents"]
    assert len(agents) == 5
    slugs = {a["slug"] for a in agents}
    assert slugs == {
        "booking-restaurant", "booking-salon", "intake-clinic",
        "enquiry-generic", "review-responder",
    }

    r = c.get("/v1/marketplace/agents?vertical=restaurant", headers=AUTH)
    slugs = {a["slug"] for a in r.json()["agents"]}
    # vertical match + "any" agents; salon/clinic excluded.
    assert "booking-restaurant" in slugs
    assert "enquiry-generic" in slugs
    assert "booking-salon" not in slugs and "intake-clinic" not in slugs


# ─────────────────────────────────────────────────────────── install flow


def test_install_creates_bundle_and_reload(client):
    c, tmp_path = client
    r = c.post(f"/v1/admin/tenants/{TID}/agents/booking-restaurant", headers=AUTH)
    assert r.status_code == 201
    row = r.json()
    assert row["slug"] == "booking-restaurant"
    assert row["version"] == "0.9.1"
    assert row["enabled"] is True
    assert row["config"]["party_size_default"] == 2

    agents_dir = tmp_path / "tenants" / TID / "agents"
    bundle = agents_dir / "booking-restaurant@0.9.1"
    assert (bundle / "skill.toml").exists()
    assert (bundle / "prompt.md").exists()
    assert (bundle / "config.json").exists()
    assert (agents_dir / ".reload").exists()

    r = c.get(f"/v1/admin/tenants/{TID}/agents", headers=AUTH)
    rows = r.json()["agents"]
    assert len(rows) == 1
    assert rows[0]["slug"] == "booking-restaurant"
    assert rows[0]["enabled"] is True
    assert rows[0]["conversation_count"] == 0
    assert rows[0]["last_used_at"] is None


def test_patch_toggles_disabled_marker(client):
    c, tmp_path = client
    c.post(f"/v1/admin/tenants/{TID}/agents/booking-restaurant", headers=AUTH)
    bundle = tmp_path / "tenants" / TID / "agents" / "booking-restaurant@0.9.1"

    r = c.patch(
        f"/v1/admin/tenants/{TID}/agents/booking-restaurant",
        headers=AUTH, json={"enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert (bundle / "disabled").exists()

    r = c.get(f"/v1/admin/tenants/{TID}/agents", headers=AUTH)
    assert r.json()["agents"][0]["enabled"] is False

    r = c.patch(
        f"/v1/admin/tenants/{TID}/agents/booking-restaurant",
        headers=AUTH, json={"enabled": True, "config": {"tone": "warm"}},
    )
    assert r.json()["enabled"] is True
    assert not (bundle / "disabled").exists()
    assert r.json()["config"]["tone"] == "warm"
    assert r.json()["config"]["party_size_default"] == 2  # merge, not replace


def test_uninstall_moves_to_trash(client):
    c, tmp_path = client
    c.post(f"/v1/admin/tenants/{TID}/agents/booking-restaurant", headers=AUTH)

    r = c.delete(f"/v1/admin/tenants/{TID}/agents/booking-restaurant", headers=AUTH)
    assert r.status_code == 204
    agents_dir = tmp_path / "tenants" / TID / "agents"
    assert not (agents_dir / "booking-restaurant@0.9.1").exists()
    assert (agents_dir / ".trash" / "booking-restaurant@0.9.1").is_dir()

    r = c.get(f"/v1/admin/tenants/{TID}/agents", headers=AUTH)
    assert r.json()["agents"] == []

    r = c.delete(f"/v1/admin/tenants/{TID}/agents/booking-restaurant", headers=AUTH)
    assert r.status_code == 404


def test_install_unavailable_slug_409(client):
    c, _ = client
    r = c.post(f"/v1/admin/tenants/{TID}/agents/intake-clinic", headers=AUTH)
    assert r.status_code == 409


def test_install_unknown_slug_404(client):
    c, _ = client
    r = c.post(f"/v1/admin/tenants/{TID}/agents/does-not-exist", headers=AUTH)
    assert r.status_code == 404


def test_patch_uninstalled_404(client):
    c, _ = client
    r = c.patch(
        f"/v1/admin/tenants/{TID}/agents/booking-restaurant",
        headers=AUTH, json={"enabled": False},
    )
    assert r.status_code == 404
