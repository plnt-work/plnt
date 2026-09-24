"""Admin API — tenant provisioning + per-tenant metrics.

Auth: simple bearer token via `PLNT_CLOUD_ADMIN_TOKEN` env. Set it before
starting uvicorn; clients pass `Authorization: Bearer <token>`. In production
swap for proper RBAC against the control-plane DB.

Endpoints:
  POST /v1/admin/tenants             — provision a tenant
  GET  /v1/admin/tenants             — list tenants
  GET  /v1/admin/tenants/{tid}       — one tenant + counts
  GET  /v1/admin/tenants/{tid}/metrics  — aggregated counters
  POST /v1/admin/tenants/{tid}/integrations — write tenant config (TOML kv)
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────── auth


def _expected_token() -> str:
    """Lazy read so tests can monkeypatch the env after import."""
    return os.environ.get("PLNT_CLOUD_ADMIN_TOKEN", "")


def require_admin(authorization: str = Header(default="")) -> None:
    """Bearer-token gate. Returns 401 on any mismatch."""
    expected = _expected_token()
    if not expected:
        # Unconfigured deployments are dev-only — admit but warn via header.
        return
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")


# ─────────────────────────────────────────────────────────── DTOs


class TenantCreate(BaseModel):
    tenant_id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    display_name: str = ""


class TenantSummary(BaseModel):
    tenant_id: str
    display_name: str
    created_at: float
    home: str
    # Returned ONLY on the initial create response; subsequent reads omit
    # the plaintext key (we only have the hash). Treat like a password.
    api_key: str | None = None


class SessionSummary(BaseModel):
    session_id: str
    first_ts: float
    last_ts: float
    user_id: str
    message_count: int
    roles: list[str]                  # distinct roles invoked in this session


class TenantMetrics(BaseModel):
    tenant_id: str
    conversation_count: int           # distinct session ids in audit log
    micro_agent_calls: dict[str, int] # role → count
    memory_turns: int                 # rows in memori.db.turns
    bookings: dict[str, int]          # status → count
    last_activity_ts: float | None    # max ts across audit events
    recent_sessions: list[SessionSummary]   # last 5 by activity


class IntegrationsUpdate(BaseModel):
    skill_role: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    values: dict[str, Any]


# ─────────────────────────────────────────────────────────── helpers


def _tenant_meta_path(tid: str) -> Path:
    from tenancy.factory import cloud_home
    return cloud_home() / "tenants" / tid / "tenant.json"


def _load_meta(tid: str) -> dict[str, Any] | None:
    p = _tenant_meta_path(tid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def _save_meta(tid: str, meta: dict[str, Any]) -> None:
    p = _tenant_meta_path(tid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, indent=2))


def _list_tenant_ids() -> list[str]:
    from tenancy.factory import cloud_home
    tenants_dir = cloud_home() / "tenants"
    if not tenants_dir.exists():
        return []
    return sorted(p.name for p in tenants_dir.iterdir() if p.is_dir())


def provision_tenant_record(
    tenant_id: str, display_name: str = "", extra: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Create the tenant home + tenant.json with a hashed api_key.
    Returns (meta, plaintext_key); plaintext_key is None when the tenant
    already existed (we only store the hash)."""
    from tenancy.factory import for_tenant, clear_cache as factory_clear
    factory_clear()
    for_tenant(tenant_id)  # creates the home dir
    existing = _load_meta(tenant_id)
    if existing:
        return existing, None
    plaintext_key = secrets.token_urlsafe(32)
    meta = {
        "tenant_id": tenant_id,
        "display_name": display_name or tenant_id,
        "created_at": time.time(),
        "api_key_hash": _hash_key(plaintext_key),
        **(extra or {}),
    }
    _save_meta(tenant_id, meta)
    return meta, plaintext_key


def _aggregate_metrics(tid: str) -> TenantMetrics:
    """Read straight from the per-tenant on-disk artifacts. Cheap and tenant-scoped."""
    from tenancy.factory import for_tenant
    from tenancy.audit import read_events
    from workflows.bookings_store import bookings_for

    bundle = for_tenant(tid)
    home = bundle.home

    # 1. Audit log → conversation count + role histogram + last_ts + per-session
    # aggregation for the recent_sessions feed.
    per_session: dict[str, dict[str, Any]] = {}
    micro_calls: dict[str, int] = {}
    last_ts: float | None = None
    for evt in read_events(tid):
        sid = evt.get("session_id")
        role = evt.get("role")
        ts = evt.get("ts")
        user_id = evt.get("user_id")
        if isinstance(ts, (int, float)):
            last_ts = ts if last_ts is None else max(last_ts, ts)
        if role:
            micro_calls[str(role)] = micro_calls.get(str(role), 0) + 1
        if sid:
            s = per_session.setdefault(str(sid), {
                "session_id": str(sid),
                "first_ts": ts if isinstance(ts, (int, float)) else 0.0,
                "last_ts": ts if isinstance(ts, (int, float)) else 0.0,
                "user_id": str(user_id or ""),
                "message_count": 0,
                "roles": set(),
            })
            if isinstance(ts, (int, float)):
                s["first_ts"] = min(float(s["first_ts"] or ts), float(ts))
                s["last_ts"] = max(float(s["last_ts"] or ts), float(ts))
            s["message_count"] = int(s["message_count"]) + 1
            if role:
                s["roles"].add(str(role))
            if user_id and not s["user_id"]:
                s["user_id"] = str(user_id)

    recent = sorted(
        per_session.values(),
        key=lambda s: float(s.get("last_ts") or 0),
        reverse=True,
    )[:5]
    recent_summaries = [
        SessionSummary(
            session_id=str(s["session_id"]),
            first_ts=float(s["first_ts"] or 0),
            last_ts=float(s["last_ts"] or 0),
            user_id=str(s["user_id"] or ""),
            message_count=int(s["message_count"]),
            roles=sorted(s["roles"]),
        )
        for s in recent
    ]

    # 2. Memory turns (Memori SQLite — stub or real)
    memory_turns = 0
    memori_db = home / "memori.db"
    if memori_db.exists():
        import sqlite3
        try:
            with sqlite3.connect(str(memori_db)) as cx:
                row = cx.execute("SELECT COUNT(*) FROM turns").fetchone()
                memory_turns = int(row[0]) if row else 0
        except sqlite3.DatabaseError:
            memory_turns = 0

    # 3. Bookings by status
    bookings = bookings_for(tid).count_by_status()

    return TenantMetrics(
        tenant_id=tid,
        conversation_count=len(per_session),
        micro_agent_calls=micro_calls,
        memory_turns=memory_turns,
        bookings=bookings,
        last_activity_ts=last_ts,
        recent_sessions=recent_summaries,
    )


# ─────────────────────────────────────────────────────────── router


router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


@router.post("/tenants", response_model=TenantSummary, status_code=status.HTTP_201_CREATED)
def provision_tenant(req: TenantCreate) -> TenantSummary:
    """Provision a tenant. Returns the API key in plaintext ONCE — store it.
    Re-provisioning an existing tenant_id does NOT return a key (we don't
    have the plaintext; use /tenants/{tid}/rotate-key to issue a new one).
    """
    from tenancy.factory import for_tenant
    meta, plaintext_key = provision_tenant_record(req.tenant_id, req.display_name)
    bundle = for_tenant(req.tenant_id)
    return TenantSummary(
        tenant_id=req.tenant_id,
        display_name=str(meta.get("display_name") or req.tenant_id),
        created_at=float(meta.get("created_at") or 0),
        home=str(bundle.home),
        api_key=plaintext_key,
    )


@router.post("/tenants/{tid}/rotate-key", response_model=TenantSummary)
def rotate_key(tid: str) -> TenantSummary:
    """Generate a fresh API key for an existing tenant. Old key stops working immediately."""
    meta = _load_meta(tid)
    if not meta:
        raise HTTPException(404, f"tenant {tid!r} not found")
    plaintext_key = secrets.token_urlsafe(32)
    meta["api_key_hash"] = _hash_key(plaintext_key)
    _save_meta(tid, meta)
    from tenancy.factory import for_tenant
    bundle = for_tenant(tid)
    return TenantSummary(
        tenant_id=tid,
        display_name=str(meta.get("display_name") or tid),
        created_at=float(meta.get("created_at") or 0),
        home=str(bundle.home),
        api_key=plaintext_key,
    )


def verify_tenant_key(tenant_id: str, presented_key: str) -> bool:
    """Check a presented API key against the stored hash. Constant-time compare.

    Default is OPEN in dev (PLNT_CLOUD_REQUIRE_AUTH unset/false). Set
    PLNT_CLOUD_REQUIRE_AUTH=1 to enforce — useful for production deploys
    and the demo of the auth flow. When open, any presented key (or none)
    is accepted; auto-provisions the tenant dir if it doesn't exist yet so
    the chat doesn't fail on first contact.
    """
    require = os.environ.get("PLNT_CLOUD_REQUIRE_AUTH", "").lower() in ("1", "true", "yes")
    # Production must enforce auth regardless of the toggle above.
    if os.environ.get("PLNT_ENV", "").lower() == "production":
        require = True
    if not require:
        # Auto-create the tenant on first contact so the WS handler can
        # immediately get a tenant bundle.
        meta = _load_meta(tenant_id)
        if not meta:
            from tenancy.factory import for_tenant
            for_tenant(tenant_id)  # creates the home dir
            _save_meta(tenant_id, {
                "tenant_id": tenant_id,
                "display_name": tenant_id,
                "created_at": time.time(),
            })
        return True
    meta = _load_meta(tenant_id)
    if not meta:
        return False
    expected = str(meta.get("api_key_hash") or "")
    if not expected:
        return True  # legacy tenant created before keys existed
    return secrets.compare_digest(_hash_key(presented_key), expected)


@router.get("/tenants", response_model=list[TenantSummary])
def list_tenants() -> list[TenantSummary]:
    from tenancy.factory import for_tenant
    out: list[TenantSummary] = []
    for tid in _list_tenant_ids():
        meta = _load_meta(tid) or {"tenant_id": tid, "display_name": tid, "created_at": 0.0}
        bundle = for_tenant(tid)
        out.append(TenantSummary(
            tenant_id=tid,
            display_name=str(meta.get("display_name") or tid),
            created_at=float(meta.get("created_at") or 0),
            home=str(bundle.home),
        ))
    return out


@router.get("/tenants/{tid}", response_model=TenantSummary)
def get_tenant(tid: str) -> TenantSummary:
    meta = _load_meta(tid)
    if not meta:
        raise HTTPException(404, f"tenant {tid!r} not found")
    from tenancy.factory import for_tenant
    bundle = for_tenant(tid)
    return TenantSummary(
        tenant_id=tid,
        display_name=str(meta.get("display_name") or tid),
        created_at=float(meta.get("created_at") or 0),
        home=str(bundle.home),
    )


@router.get("/tenants/{tid}/metrics", response_model=TenantMetrics)
def get_metrics(tid: str) -> TenantMetrics:
    # Accept any tenant whose home dir exists — covers both admin-provisioned
    # tenants (have tenant.json) and dev-time tenants auto-created by
    # for_tenant() during tests/smokes.
    from tenancy.factory import cloud_home
    if not (cloud_home() / "tenants" / tid).is_dir():
        raise HTTPException(404, f"tenant {tid!r} not found")
    return _aggregate_metrics(tid)


@router.get("/services/places")
def places_status() -> dict[str, Any]:
    """Surface whether the Places API is enabled so the admin UI can warn
    operators when `resolve_business` is running on LLM knowledge alone."""
    from services import places as places_svc
    return {
        "enabled": places_svc.is_enabled(),
        "cache": places_svc.cache_stats(),
        "hint": places_svc.availability_summary(),
    }


@router.delete("/tenants/{tid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(tid: str) -> None:
    """Permanently delete a tenant — wipes home dir + clears cached bundles.

    No undo. Used to clean up test artifacts. Production swaps for a
    soft-delete (mark deleted, scrub on a schedule) — the destructive form
    is fine for the demo.
    """
    import shutil
    from tenancy.factory import cloud_home, clear_cache as factory_clear
    from memory.memori_adapter import clear_cache as memori_clear
    from workflows.bookings_store import clear_cache as bookings_clear
    from tenancy import audit as audit_mod

    home = cloud_home() / "tenants" / tid
    if not home.is_dir():
        raise HTTPException(404, f"tenant {tid!r} not found")
    shutil.rmtree(home, ignore_errors=True)
    factory_clear(); memori_clear(); bookings_clear()
    # Drop any in-process audit file lock for the deleted tenant.
    audit_mod._FILE_LOCKS.pop(tid, None)


@router.post("/tenants/{tid}/integrations", status_code=status.HTTP_204_NO_CONTENT)
def update_integrations(tid: str, body: IntegrationsUpdate) -> None:
    """Write per-skill tenant config (API keys, adapter selections, prompts).

    Backed by plnt's IntegrationsStore (one TOML per tenant). Values flow into
    AgentSpec.inputs on every spawn via IntegrationsStore.merge_into_spec.
    """
    if not _load_meta(tid):
        raise HTTPException(404, f"tenant {tid!r} not found")
    from tenancy.factory import for_tenant
    bundle = for_tenant(tid)
    bundle.integrations.set(body.skill_role, body.values)
