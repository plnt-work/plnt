"""Merchant onboarding — Google identity sign-in → business claim → tenant + first agent.

Journey A backend. OAuth is identity-only (`openid email profile`); business
claim is Places Text Search, NOT the Google Business Profile API.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from surface.admin import _list_tenant_ids, _load_meta, provision_tenant_record
from surface.auth_deps import (
    SESSION_COOKIE,
    SESSION_TTL,
    make_session_cookie,
    require_onboard_session,
    require_owned,
)


log = logging.getLogger("plnt_cloud.onboard")

router = APIRouter(prefix="/v1/onboard", tags=["onboard"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
OAUTH_SCOPES = "openid email profile"

STATE_TTL = 600

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$")
RESERVED_SLUGS = {"demo", "admin", "api", "www", "docs", "console"}
DEFAULT_AGENT_SLUG = "booking-restaurant"

# Server-side OAuth state → issue timestamp. Single-process TTL dict; a
# multi-instance deploy needs signed state instead.
_STATES: dict[str, float] = {}


# ─────────────────────────────────────────────────────────── config


def _public_url() -> str:
    return os.environ.get("PLNT_CLOUD_PUBLIC_URL", "http://localhost:8080").rstrip("/")


def _redirect_uri() -> str:
    return f"{_public_url()}/v1/onboard/google/callback"


def _frontend_origin() -> str:
    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
    return (origins[0] if origins else "http://localhost:5173").rstrip("/")


# ─────────────────────────────────────────────────────────── google oauth


def _exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """Auth-code → token exchange. Module-level so tests can monkeypatch."""
    data = {
        "code": code,
        "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=10.0) as client:
        r = client.post(GOOGLE_TOKEN_URL, data=data)
    r.raise_for_status()
    return r.json()


def _fetch_userinfo(access_token: str) -> dict[str, Any]:
    """OIDC userinfo (email, name). Module-level so tests can monkeypatch."""
    with httpx.Client(timeout=10.0) as client:
        r = client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    r.raise_for_status()
    return r.json()


def _issue_state() -> str:
    now = time.time()
    for k, issued in list(_STATES.items()):
        if now - issued > STATE_TTL:
            _STATES.pop(k, None)
    state = secrets.token_urlsafe(24)
    _STATES[state] = now
    return state


@router.get("/google/start")
def google_start() -> Any:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    if not client_id:
        return JSONResponse({"error": "oauth_not_configured"}, status_code=503)
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": OAUTH_SCOPES,
        "state": _issue_state(),
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=302)


@router.get("/google/callback")
def google_callback(code: str = "", state: str = "") -> Any:
    issued = _STATES.pop(state, None) if state else None
    if issued is None or time.time() - issued > STATE_TTL:
        raise HTTPException(400, "bad or expired oauth state")
    if not code:
        raise HTTPException(400, "missing code")
    try:
        tokens = _exchange_code(code, _redirect_uri())
        userinfo = _fetch_userinfo(str(tokens.get("access_token") or ""))
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"google oauth exchange failed: {exc}")
    email = str(userinfo.get("email") or "").strip().lower()
    if not email or "|" in email:
        raise HTTPException(502, "google userinfo returned no usable email")
    resp = RedirectResponse(f"{_frontend_origin()}/onboard?step=claim", status_code=302)
    resp.set_cookie(
        SESSION_COOKIE,
        make_session_cookie(email),
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
    )
    return resp


# ─────────────────────────────────────────────────────────── business search


_GENERIC_PLACE_TYPES = {"point_of_interest", "establishment"}


def _category(types: list[str]) -> str:
    for t in types:
        if t not in _GENERIC_PLACE_TYPES:
            return t
    return types[0] if types else ""


@router.get("/search")
def search_business(q: str, email: str = Depends(require_onboard_session)) -> dict[str, Any]:
    from services import places

    candidates = [
        {
            "place_id": r.place_id,
            "name": r.name,
            "address": r.address,
            "lat": r.latitude,
            "lng": r.longitude,
            "category": _category(r.types),
        }
        for r in places.search(q, max_results=5)[:5]
    ]
    return {"candidates": candidates}


# ─────────────────────────────────────────────────────────── slug claim


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:41].rstrip("-")


def _slug_taken(slug: str) -> bool:
    from tenancy.factory import cloud_home
    return slug in RESERVED_SLUGS or (cloud_home() / "tenants" / slug).exists()


class ClaimRequest(BaseModel):
    place_id: str
    name: str
    address: str = ""
    suggested_slug: str | None = None


@router.post("/claim")
def claim_business(
    body: ClaimRequest, email: str = Depends(require_onboard_session),
) -> dict[str, Any]:
    if body.suggested_slug:
        base = _slugify(body.suggested_slug)
        if base in RESERVED_SLUGS:
            raise HTTPException(400, f"slug {base!r} is reserved")
    else:
        base = _slugify(body.name)
    if not SLUG_RE.match(base):
        raise HTTPException(400, "cannot derive a valid slug — provide suggested_slug")
    slug, n = base, 2
    while _slug_taken(slug):
        suffix = f"-{n}"
        slug = base[: 41 - len(suffix)] + suffix
        n += 1
    return {"slug": slug, "available": True}


# ─────────────────────────────────────────────────────────── tenant creation


class CreateRequest(BaseModel):
    slug: str
    place_id: str
    name: str
    address: str
    lat: float | None = None
    lng: float | None = None


@router.post("/create", status_code=201)
def create_tenant(
    body: CreateRequest, email: str = Depends(require_onboard_session),
) -> dict[str, Any]:
    from tenancy.factory import cloud_home

    slug = body.slug
    if not SLUG_RE.match(slug):
        raise HTTPException(422, "invalid slug: must match ^[a-z0-9][a-z0-9-]{2,40}$")
    if slug in RESERVED_SLUGS:
        raise HTTPException(400, f"slug {slug!r} is reserved")
    if (cloud_home() / "tenants" / slug).exists():
        raise HTTPException(409, f"tenant {slug!r} already exists")

    _, api_key = provision_tenant_record(slug, display_name=body.name, extra={
        "owner_email": email,
        "business": {
            "place_id": body.place_id,
            "name": body.name,
            "address": body.address,
            "lat": body.lat,
            "lng": body.lng,
        },
    })
    return {"tenant_id": slug, "api_key": api_key}


# ─────────────────────────────────────────────────────────── agent install


class InstallRequest(BaseModel):
    tenant_id: str
    slug: str = DEFAULT_AGENT_SLUG
    config: dict[str, Any] | None = None


@router.post("/install", status_code=201)
def install_first_agent(
    body: InstallRequest, email: str = Depends(require_onboard_session),
) -> dict[str, Any]:
    require_owned(body.tenant_id, email)
    from surface.admin_v2 import AgentInstall, install_agent
    return install_agent(body.tenant_id, body.slug, AgentInstall(config=body.config))


# ─────────────────────────────────────────────────────────── me


@router.get("/me")
def me(email: str = Depends(require_onboard_session)) -> dict[str, Any]:
    tenants = []
    for tid in _list_tenant_ids():
        meta = _load_meta(tid) or {}
        if str(meta.get("owner_email") or "") != email:
            continue
        business = meta.get("business") if isinstance(meta.get("business"), dict) else {}
        tenants.append({
            "tenant_id": tid,
            "business_name": str(business.get("name") or meta.get("display_name") or tid),
        })
    return {"email": email, "tenants": tenants}
