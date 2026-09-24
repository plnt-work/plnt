"""Business-owner magic-link auth + session cookie.

Flow:
  1. Owner types email → POST /v1/auth/magic-link/request → server issues
     a token. In DEV the token is returned in the response body; a real
     mailer wraps this endpoint.
  2. Owner clicks the link → POST /v1/auth/magic-link/verify → we consume
     the token, materialise the owner, and set an httpOnly `plnt_session`
     cookie carrying an opaque session token.
  3. Subsequent requests read the cookie via `require_owner`.

The catalogue admin router accepts EITHER an admin bearer OR a linked
owner session — see `require_owner_or_admin` for the composite guard.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from pydantic import BaseModel, field_validator

from services.business_owners import Owner, owners_store


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


log = logging.getLogger("plnt_cloud.auth")

router = APIRouter(prefix="/v1/auth", tags=["auth"])

SESSION_COOKIE = "plnt_session"
_COOKIE_MAX_AGE = 7 * 24 * 3600


# ─────────────────────────────────────────────────────────── DTOs


class MagicLinkRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email")
        return v


class MagicLinkVerify(BaseModel):
    token: str


class LinkTenantRequest(BaseModel):
    tenant_id: str


# ─────────────────────────────────────────────────────────── helpers


def _owner_dict(o: Owner) -> dict[str, Any]:
    return {
        "owner_id": o.owner_id,
        "email": o.email,
        "tenant_ids": list(o.tenant_ids),
    }


def require_owner(request: Request) -> Owner:
    """Resolve the `plnt_session` cookie to an Owner or raise 401."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    owner = owners_store().resolve_session(token)
    if not owner:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired")
    return owner


# ─────────────────────────────────────────────────────────── endpoints


@router.post("/magic-link/request")
def request_magic_link(body: MagicLinkRequest) -> dict[str, Any]:
    token = owners_store().issue_magic_link(str(body.email))
    log.warning(
        "magic-link issued in DEV mode — token returned in response body. "
        "Suppress this in production by wiring a real mailer.",
    )
    return {"sent": True, "email": str(body.email), "token": token}


@router.post("/magic-link/verify")
def verify_magic_link(body: MagicLinkVerify, response: Response) -> dict[str, Any]:
    store = owners_store()
    owner = store.consume_magic_link(body.token)
    if not owner:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    session = store.issue_session(owner.owner_id)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session.session_token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"owner": _owner_dict(owner), "session_expires_at": session.expires_at}


@router.post("/logout")
def logout(response: Response, plnt_session: str | None = Cookie(default=None)) -> dict[str, bool]:
    if plnt_session:
        owners_store().revoke_session(plnt_session)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> dict[str, Any]:
    owner = require_owner(request)
    return {"owner": _owner_dict(owner)}


@router.post("/link-tenant")
def link_tenant(body: LinkTenantRequest, request: Request) -> dict[str, Any]:
    from tenancy.factory import for_tenant
    from surface.admin import _load_meta, _save_meta

    owner = require_owner(request)
    tid = body.tenant_id
    if not _load_meta(tid):
        for_tenant(tid)
        _save_meta(tid, {
            "tenant_id": tid,
            "display_name": tid,
            "created_at": time.time(),
        })
    owners_store().link_tenant(owner.owner_id, tid)
    refreshed = owners_store().get_owner(owner.owner_id)
    return {"owner": _owner_dict(refreshed)} if refreshed else {"owner": _owner_dict(owner)}
