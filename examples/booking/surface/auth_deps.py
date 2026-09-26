"""Shared auth dependencies — merchant session cookie + tenant-scoped access.

The `plnt_onboard` cookie primitives were extracted from surface/onboard.py
so admin_v2 and docs_upload can grant merchants access to their own tenant.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Any

from fastapi import HTTPException, Header, Request

from surface.admin import _expected_token, _load_meta


log = logging.getLogger("plnt_cloud.auth_deps")

SESSION_COOKIE = "plnt_onboard"
SESSION_TTL = 7 * 24 * 3600

_EPHEMERAL_SECRET: str | None = None


def _session_secret() -> bytes:
    global _EPHEMERAL_SECRET
    configured = os.environ.get("PLNT_CLOUD_SESSION_SECRET", "")
    if configured:
        return configured.encode()
    if _EPHEMERAL_SECRET is None:
        _EPHEMERAL_SECRET = secrets.token_hex(32)
        log.warning(
            "PLNT_CLOUD_SESSION_SECRET unset — using an ephemeral secret; "
            "onboarding sessions will not survive a restart"
        )
    return _EPHEMERAL_SECRET.encode()


def _sign(payload: str) -> str:
    return hmac.new(_session_secret(), payload.encode(), hashlib.sha256).hexdigest()


def make_session_cookie(email: str, *, ttl: int = SESSION_TTL) -> str:
    payload = f"{email}|{int(time.time()) + ttl}"
    return f"{payload}|{_sign(payload)}"


def verify_session_cookie(value: str) -> str | None:
    """HMAC + expiry check. Returns the merchant email, or None if invalid."""
    parts = value.split("|")
    if len(parts) != 3:
        return None
    email, expiry_raw, sig = parts
    if not hmac.compare_digest(_sign(f"{email}|{expiry_raw}"), sig):
        return None
    try:
        expiry = int(expiry_raw)
    except ValueError:
        return None
    if expiry < time.time():
        return None
    return email


def require_onboard_session(request: Request) -> str:
    """FastAPI dependency — returns the signed-in merchant email or 401s."""
    raw = request.cookies.get(SESSION_COOKIE, "")
    email = verify_session_cookie(raw) if raw else None
    if not email:
        raise HTTPException(401, "onboarding session required")
    return email


def require_owned(tenant_id: str, email: str) -> dict[str, Any]:
    """404 if the tenant doesn't exist, 403 if `email` isn't its owner."""
    meta = _load_meta(tenant_id)
    if not meta:
        raise HTTPException(404, f"tenant {tenant_id!r} not found")
    if str(meta.get("owner_email") or "") != email:
        raise HTTPException(403, "you do not own this tenant")
    return meta


def _admin_bearer_ok(authorization: str) -> bool | None:
    """True = valid admin token, False = bad token, None = no bearer sent."""
    expected = _expected_token()
    if not authorization.startswith("Bearer "):
        return None
    return authorization.split(" ", 1)[1].strip() == expected


def require_tenant_access(
    tid: str, request: Request, authorization: str = Header(default=""),
) -> None:
    """Per-tenant gate: admin bearer OR the owning merchant's session cookie."""
    if not _expected_token():
        return  # unconfigured deployments are dev-open, same as require_admin
    bearer = _admin_bearer_ok(authorization)
    if bearer is True:
        return
    if bearer is False:
        raise HTTPException(401, "invalid token")
    email = verify_session_cookie(request.cookies.get(SESSION_COOKIE, ""))
    if not email:
        raise HTTPException(401, "admin token or merchant session required")
    require_owned(tid, email)


def require_admin_or_merchant(
    request: Request, authorization: str = Header(default=""),
) -> None:
    """Admin bearer OR any signed-in merchant — no tenant scoping."""
    if not _expected_token():
        return
    bearer = _admin_bearer_ok(authorization)
    if bearer is True:
        return
    if bearer is False:
        raise HTTPException(401, "invalid token")
    if not verify_session_cookie(request.cookies.get(SESSION_COOKIE, "")):
        raise HTTPException(401, "admin token or merchant session required")
