"""Slice-5a onboarding tests — OAuth (mocked exchange), session cookie,
Places-backed search, slug claim, tenant create, first-agent install, /me."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

EMAIL = "aditi@example.com"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Isolated PLNT_CLOUD_HOME + a minimal app mounting only the onboard router."""
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    monkeypatch.setenv("PLNT_CLOUD_MEMORY_BACKEND", "stub")
    monkeypatch.setenv("PLNT_CLOUD_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid-123")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "cs-456")

    from memory import memori_adapter as ma
    from tenancy import factory as tf
    from workflows import bookings_store as bs
    from services import orders_store as os_
    from microagents import loader

    for mod in (ma, tf, bs, os_, loader):
        mod.clear_cache()

    from surface import onboard
    onboard._STATES.clear()
    app = FastAPI()
    app.include_router(onboard.router)
    yield TestClient(app), tmp_path

    onboard._STATES.clear()
    for mod in (ma, tf, bs, os_, loader):
        mod.clear_cache()


def _login(c, monkeypatch, email: str = EMAIL):
    """Drive start → callback with a mocked Google exchange; cookie lands in the jar."""
    from surface import onboard

    r = c.get("/v1/onboard/google/start", follow_redirects=False)
    assert r.status_code == 302
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    monkeypatch.setattr(onboard, "_exchange_code", lambda code, ru: {"access_token": "at-1"})
    monkeypatch.setattr(onboard, "_fetch_userinfo", lambda tok: {"email": email, "name": "Aditi"})
    r = c.get(f"/v1/onboard/google/callback?code=x&state={state}", follow_redirects=False)
    assert r.status_code == 302
    return r


def _create_tenant(c, slug: str = "bakasur", name: str = "Bakasur Pizza Kitchen"):
    return c.post("/v1/onboard/create", json={
        "slug": slug,
        "place_id": "pid-1",
        "name": name,
        "address": "Baner, Pune",
        "lat": 18.55,
        "lng": 73.78,
    })


# ─────────────────────────────────────────────────────────── oauth


def test_start_redirects_to_google(client):
    c, _ = client
    r = c.get("/v1/onboard/google/start", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    q = parse_qs(urlparse(loc).query)
    assert q["client_id"] == ["cid-123"]
    assert q["scope"] == ["openid email profile"]
    assert q["state"][0]
    assert q["redirect_uri"] == ["http://localhost:8080/v1/onboard/google/callback"]


def test_start_503_without_client_id(client, monkeypatch):
    c, _ = client
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID")
    r = c.get("/v1/onboard/google/start", follow_redirects=False)
    assert r.status_code == 503
    assert r.json() == {"error": "oauth_not_configured"}


def test_callback_sets_valid_cookie(client, monkeypatch):
    c, _ = client
    r = _login(c, monkeypatch)
    assert r.headers["location"] == "http://localhost:5173/onboard?step=claim"
    assert "plnt_onboard" in c.cookies
    r = c.get("/v1/onboard/me")
    assert r.status_code == 200
    assert r.json() == {"email": EMAIL, "tenants": []}


def test_callback_bad_state_400(client):
    c, _ = client
    r = c.get("/v1/onboard/google/callback?code=x&state=bogus", follow_redirects=False)
    assert r.status_code == 400


def test_session_required(client):
    c, _ = client
    for method, path in (
        ("get", "/v1/onboard/search?q=x"),
        ("get", "/v1/onboard/me"),
    ):
        assert getattr(c, method)(path).status_code == 401
    assert c.post("/v1/onboard/claim", json={"place_id": "p", "name": "n"}).status_code == 401


def test_tampered_cookie_rejected(client, monkeypatch):
    c, _ = client
    _login(c, monkeypatch)
    c.cookies.set("plnt_onboard", "evil@example.com|9999999999|deadbeef")
    assert c.get("/v1/onboard/me").status_code == 401


# ─────────────────────────────────────────────────────────── search


def test_search_returns_shaped_candidates(client, monkeypatch):
    c, _ = client
    _login(c, monkeypatch)

    from services.places import PlaceResult
    fake = [
        PlaceResult(
            place_id="pid-1", name="Bakasur Pizza Kitchen", address="Baner, Pune",
            latitude=18.55, longitude=73.78,
            types=["point_of_interest", "restaurant", "establishment"],
        ),
        PlaceResult(
            place_id="pid-2", name="Bakasur Cafe", address="Aundh, Pune",
            latitude=18.56, longitude=73.80, types=[],
        ),
    ]
    monkeypatch.setattr("services.places.search", lambda q, *, max_results=5: fake)

    r = c.get("/v1/onboard/search?q=bakasur")
    assert r.status_code == 200
    cands = r.json()["candidates"]
    assert len(cands) == 2
    assert cands[0] == {
        "place_id": "pid-1", "name": "Bakasur Pizza Kitchen", "address": "Baner, Pune",
        "lat": 18.55, "lng": 73.78, "category": "restaurant",
    }
    assert set(cands[1]) == {"place_id", "name", "address", "lat", "lng", "category"}


# ─────────────────────────────────────────────────────────── claim


def test_claim_generates_slug(client, monkeypatch):
    c, _ = client
    _login(c, monkeypatch)
    r = c.post("/v1/onboard/claim", json={
        "place_id": "pid-1", "name": "Bakasur Pizza Kitchen!", "address": "Pune",
    })
    assert r.status_code == 200
    assert r.json() == {"slug": "bakasur-pizza-kitchen", "available": True}


def test_claim_dedupes_taken_slug(client, monkeypatch):
    c, tmp_path = client
    _login(c, monkeypatch)
    (tmp_path / "tenants" / "bakasur-pizza-kitchen").mkdir(parents=True)
    r = c.post("/v1/onboard/claim", json={
        "place_id": "pid-1", "name": "Bakasur Pizza Kitchen", "address": "Pune",
    })
    assert r.json() == {"slug": "bakasur-pizza-kitchen-2", "available": True}


def test_claim_rejects_reserved_suggestion(client, monkeypatch):
    c, _ = client
    _login(c, monkeypatch)
    r = c.post("/v1/onboard/claim", json={
        "place_id": "pid-1", "name": "Admin Cafe", "suggested_slug": "admin",
    })
    assert r.status_code == 400


def test_claim_derived_reserved_gets_suffix(client, monkeypatch):
    c, _ = client
    _login(c, monkeypatch)
    r = c.post("/v1/onboard/claim", json={"place_id": "pid-1", "name": "Demo"})
    assert r.json() == {"slug": "demo-2", "available": True}


# ─────────────────────────────────────────────────────────── create


def test_create_writes_owner_and_business(client, monkeypatch):
    import json

    c, tmp_path = client
    _login(c, monkeypatch)
    r = _create_tenant(c)
    assert r.status_code == 201
    body = r.json()
    assert body["tenant_id"] == "bakasur"
    assert body["api_key"]

    meta = json.loads((tmp_path / "tenants" / "bakasur" / "tenant.json").read_text())
    assert meta["owner_email"] == EMAIL
    assert meta["business"] == {
        "place_id": "pid-1", "name": "Bakasur Pizza Kitchen",
        "address": "Baner, Pune", "lat": 18.55, "lng": 73.78,
    }
    assert meta["api_key_hash"] and "api_key" not in meta


def test_create_rejects_invalid_reserved_duplicate(client, monkeypatch):
    c, _ = client
    _login(c, monkeypatch)
    assert _create_tenant(c, slug="Bad Slug!").status_code == 422
    assert _create_tenant(c, slug="ab").status_code == 422
    assert _create_tenant(c, slug="admin").status_code == 400
    assert _create_tenant(c).status_code == 201
    assert _create_tenant(c).status_code == 409


# ─────────────────────────────────────────────────────────── install


def test_install_as_owner(client, monkeypatch):
    c, tmp_path = client
    _login(c, monkeypatch)
    _create_tenant(c)
    r = c.post("/v1/onboard/install", json={"tenant_id": "bakasur"})
    assert r.status_code == 201
    body = r.json()
    assert body["slug"] == "booking-restaurant"
    bundle = tmp_path / "tenants" / "bakasur" / "agents" / f"booking-restaurant@{body['version']}"
    assert (bundle / "skill.toml").exists()


def test_install_foreign_tenant_403(client, monkeypatch):
    import json

    c, tmp_path = client
    _login(c, monkeypatch)
    other = tmp_path / "tenants" / "not-mine"
    other.mkdir(parents=True)
    (other / "tenant.json").write_text(json.dumps({
        "tenant_id": "not-mine", "owner_email": "someone@else.com",
    }))
    r = c.post("/v1/onboard/install", json={"tenant_id": "not-mine"})
    assert r.status_code == 403
    assert c.post("/v1/onboard/install", json={"tenant_id": "ghost"}).status_code == 404


# ─────────────────────────────────────────────────────────── me


def test_me_lists_owned_tenants(client, monkeypatch):
    c, _ = client
    _login(c, monkeypatch)
    _create_tenant(c)
    _create_tenant(c, slug="bakasur-two", name="Bakasur Two")
    r = c.get("/v1/onboard/me")
    assert r.json() == {"email": EMAIL, "tenants": [
        {"tenant_id": "bakasur", "business_name": "Bakasur Pizza Kitchen"},
        {"tenant_id": "bakasur-two", "business_name": "Bakasur Two"},
    ]}
