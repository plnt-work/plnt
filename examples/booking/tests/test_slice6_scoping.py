"""Slice-6 tenant-scoping tests — `require_tenant_access` grants merchants
(via the `plnt_onboard` cookie) access to their own tenant's admin_v2 +
docs endpoints; admin bearer keeps working everywhere; foreigners get 403."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ADMIN_TOKEN = "test-admin-token"
AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
EMAIL = "aditi@example.com"
TID = "bakasur"


def _clear_caches() -> None:
    from memory import memori_adapter as ma
    from microagents import loader
    from services import orders_store as os_
    from tenancy import factory as tf
    from workflows import bookings_store as bs

    for mod in (ma, tf, bs, os_, loader):
        mod.clear_cache()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolated home + app mounting onboard, admin_v2, marketplace, docs."""
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    monkeypatch.setenv("PLNT_CLOUD_MEMORY_BACKEND", "stub")
    monkeypatch.setenv("PLNT_CLOUD_ADMIN_TOKEN", ADMIN_TOKEN)
    monkeypatch.setenv("PLNT_CLOUD_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid-123")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "cs-456")
    _clear_caches()

    from surface import onboard
    from surface.admin_v2 import marketplace_router, router as admin_v2_router
    from surface.docs_upload import router as docs_router

    onboard._STATES.clear()
    app = FastAPI()
    app.include_router(onboard.router)
    app.include_router(admin_v2_router)
    app.include_router(marketplace_router)
    app.include_router(docs_router)
    yield app, tmp_path

    onboard._STATES.clear()
    _clear_caches()


def _login(c: TestClient, monkeypatch, email: str = EMAIL) -> None:
    from surface import onboard

    r = c.get("/v1/onboard/google/start", follow_redirects=False)
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    monkeypatch.setattr(onboard, "_exchange_code", lambda code, ru: {"access_token": "at-1"})
    monkeypatch.setattr(onboard, "_fetch_userinfo", lambda tok: {"email": email, "name": "A"})
    r = c.get(f"/v1/onboard/google/callback?code=x&state={state}", follow_redirects=False)
    assert r.status_code == 302 and "plnt_onboard" in c.cookies


def _create_tenant(c: TestClient, slug: str = TID) -> None:
    r = c.post("/v1/onboard/create", json={
        "slug": slug, "place_id": "pid-1", "name": "Bakasur Pizza Kitchen",
        "address": "Baner, Pune",
    })
    assert r.status_code == 201


def _seed_foreign(tmp_path) -> None:
    other = tmp_path / "tenants" / "not-mine"
    other.mkdir(parents=True)
    (other / "tenant.json").write_text(json.dumps({
        "tenant_id": "not-mine", "owner_email": "someone@else.com",
    }))


@pytest.fixture()
def merchant(env, monkeypatch):
    """Signed-in owner of TID + a foreign tenant on disk."""
    app, tmp_path = env
    c = TestClient(app)
    _login(c, monkeypatch)
    _create_tenant(c)
    _seed_foreign(tmp_path)
    return c, app, tmp_path


# ─────────────────────────────────────────────────────────── merchant cookie


def test_merchant_cookie_own_tenant_ok(merchant):
    c, _, _ = merchant
    for path in (
        f"/v1/admin/tenants/{TID}/bookings",
        f"/v1/admin/tenants/{TID}/sessions",
        f"/v1/admin/tenants/{TID}/sessions/s1/transcript",
        f"/v1/admin/tenants/{TID}/users",
        f"/v1/admin/tenants/{TID}/agents",
        f"/v1/admin/tenants/{TID}/notifications",
        f"/v1/admin/tenants/{TID}/docs",
    ):
        assert c.get(path).status_code == 200, path


def test_merchant_agent_lifecycle_via_cookie(merchant):
    c, _, _ = merchant
    r = c.post(f"/v1/admin/tenants/{TID}/agents/booking-restaurant")
    assert r.status_code == 201
    r = c.patch(f"/v1/admin/tenants/{TID}/agents/booking-restaurant", json={"enabled": False})
    assert r.status_code == 200 and r.json()["enabled"] is False
    r = c.delete(f"/v1/admin/tenants/{TID}/agents/booking-restaurant")
    assert r.status_code == 204


def test_merchant_docs_upload_via_cookie(merchant):
    c, _, _ = merchant
    r = c.post(
        f"/v1/admin/tenants/{TID}/docs",
        files={"file": ("menu.txt", b"Margherita, pepperoni, quattro formaggi.", "text/plain")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "menu.txt" and body["chunks"] >= 1


def test_merchant_marketplace_via_cookie(merchant):
    c, _, _ = merchant
    r = c.get("/v1/marketplace/agents")
    assert r.status_code == 200
    assert any(a["slug"] == "booking-restaurant" for a in r.json()["agents"])


def test_merchant_foreign_tenant_403(merchant):
    c, _, _ = merchant
    assert c.get("/v1/admin/tenants/not-mine/bookings").status_code == 403
    assert c.post(
        "/v1/admin/tenants/not-mine/docs",
        files={"file": ("menu.txt", b"x", "text/plain")},
    ).status_code == 403
    assert c.post("/v1/admin/tenants/not-mine/agents/booking-restaurant").status_code == 403


def test_merchant_missing_tenant_404(merchant):
    c, _, _ = merchant
    assert c.get("/v1/admin/tenants/ghost/bookings").status_code == 404


# ─────────────────────────────────────────────────────────── no auth / bad auth


def test_no_auth_401(merchant):
    _, app, _ = merchant
    bare = TestClient(app)
    assert bare.get(f"/v1/admin/tenants/{TID}/bookings").status_code == 401
    assert bare.get("/v1/marketplace/agents").status_code == 401
    assert bare.post(
        f"/v1/admin/tenants/{TID}/docs",
        files={"file": ("menu.txt", b"x", "text/plain")},
    ).status_code == 401


def test_tampered_cookie_401(merchant):
    _, app, _ = merchant
    bare = TestClient(app)
    bare.cookies.set("plnt_onboard", "evil@else.com|9999999999|deadbeef")
    assert bare.get(f"/v1/admin/tenants/{TID}/bookings").status_code == 401


def test_bad_bearer_401_even_with_cookie(merchant):
    c, _, _ = merchant
    r = c.get(f"/v1/admin/tenants/{TID}/bookings", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


# ─────────────────────────────────────────────────────────── admin bearer


def test_admin_token_works_everywhere(merchant):
    _, app, _ = merchant
    bare = TestClient(app)
    for path in (
        f"/v1/admin/tenants/{TID}/bookings",
        "/v1/admin/tenants/not-mine/bookings",
        f"/v1/admin/tenants/{TID}/agents",
        "/v1/marketplace/agents",
        f"/v1/admin/tenants/{TID}/docs",
    ):
        assert bare.get(path, headers=AUTH).status_code == 200, path
    r = bare.post(
        f"/v1/admin/tenants/{TID}/docs",
        files={"file": ("menu.txt", b"Vegan cheese on selected pies.", "text/plain")},
        headers=AUTH,
    )
    assert r.status_code == 201


def test_unconfigured_token_stays_dev_open(merchant, monkeypatch):
    _, app, _ = merchant
    monkeypatch.delenv("PLNT_CLOUD_ADMIN_TOKEN")
    bare = TestClient(app)
    assert bare.get(f"/v1/admin/tenants/{TID}/bookings").status_code == 200
    assert bare.get("/v1/marketplace/agents").status_code == 200
