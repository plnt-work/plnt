"""Business-owner facing catalogue CRUD.

Manages the per-tenant `services`, `professionals` and `opening_hours`
that back the mobile venue detail screens and the availability
computation. Guarded by `require_owner_or_admin` — either a valid admin
bearer OR a linked owner session on `plnt_session`.
"""
from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from services.business_owners import owners_store
from services.catalogue import (
    DayHours,
    catalogue_for,
    hours_to_dict,
    professional_to_dict,
    service_to_dict,
)
from surface.admin import _expected_token
from surface.auth import SESSION_COOKIE


# ─────────────────────────────────────────────────────────── guard


def require_owner_or_admin(request: Request, tid: str) -> None:
    """Accept either a valid admin bearer or a session cookie whose owner
    is linked to `tid`. Raises 401/403 otherwise."""
    expected = _expected_token()
    auth = request.headers.get("authorization", "")
    if expected and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token == expected:
            return
    if not expected and auth.startswith("Bearer "):
        return

    session_token = request.cookies.get(SESSION_COOKIE)
    if session_token:
        owner = owners_store().resolve_session(session_token)
        if owner:
            if tid in owner.tenant_ids:
                return
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"not linked to tenant {tid!r}")
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")


def _guard(tid: str, request: Request) -> None:
    require_owner_or_admin(request, tid)


# ─────────────────────────────────────────────────────────── DTOs


class ServiceCreate(BaseModel):
    id: str | None = None
    name: str
    duration_min: int
    price_cents: int
    description: str = ""
    pro_ids: list[str] = []


class ServicePatch(BaseModel):
    name: str | None = None
    duration_min: int | None = None
    price_cents: int | None = None
    description: str | None = None
    pro_ids: list[str] | None = None


class ProfessionalCreate(BaseModel):
    id: str | None = None
    name: str
    role: str = ""
    avatar_uri: str = ""


class ProfessionalPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    avatar_uri: str | None = None


class HoursEntry(BaseModel):
    weekday: int
    open_min: int
    close_min: int


class HoursUpdate(BaseModel):
    hours: list[HoursEntry]


# ─────────────────────────────────────────────────────────── router


router = APIRouter(prefix="/v1/admin/tenants/{tid}/catalogue", tags=["catalogue_admin"])


# ─── services ─────────────────────────────────────────────────


@router.get("/services")
def list_services(tid: str, request: Request) -> dict[str, list[dict[str, Any]]]:
    _guard(tid, request)
    store = catalogue_for(tid)
    return {"services": [service_to_dict(s) for s in store.list_services()]}


@router.post("/services", status_code=status.HTTP_201_CREATED)
def create_service(tid: str, body: ServiceCreate, request: Request) -> dict[str, Any]:
    _guard(tid, request)
    store = catalogue_for(tid)
    sid = body.id or f"svc-{secrets.token_hex(4)}"
    svc = store.upsert_service(
        id=sid,
        name=body.name,
        duration_min=body.duration_min,
        price_cents=body.price_cents,
        description=body.description,
        pro_ids=body.pro_ids,
    )
    return service_to_dict(svc)


@router.patch("/services/{sid}")
def update_service(tid: str, sid: str, body: ServicePatch, request: Request) -> dict[str, Any]:
    _guard(tid, request)
    store = catalogue_for(tid)
    existing = store.get_service(sid)
    if not existing:
        raise HTTPException(404, f"service {sid!r} not found")
    svc = store.upsert_service(
        id=sid,
        name=body.name if body.name is not None else existing.name,
        duration_min=body.duration_min if body.duration_min is not None else existing.duration_min,
        price_cents=body.price_cents if body.price_cents is not None else existing.price_cents,
        description=body.description if body.description is not None else existing.description,
        pro_ids=body.pro_ids if body.pro_ids is not None else existing.pro_ids,
    )
    return service_to_dict(svc)


@router.delete("/services/{sid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(tid: str, sid: str, request: Request) -> None:
    _guard(tid, request)
    store = catalogue_for(tid)
    if not store.delete_service(sid):
        raise HTTPException(404, f"service {sid!r} not found")


# ─── professionals ────────────────────────────────────────────


@router.get("/professionals")
def list_professionals(tid: str, request: Request) -> dict[str, list[dict[str, Any]]]:
    _guard(tid, request)
    store = catalogue_for(tid)
    return {"professionals": [professional_to_dict(p) for p in store.list_professionals()]}


@router.post("/professionals", status_code=status.HTTP_201_CREATED)
def create_professional(tid: str, body: ProfessionalCreate, request: Request) -> dict[str, Any]:
    _guard(tid, request)
    store = catalogue_for(tid)
    pid = body.id or f"pro-{secrets.token_hex(4)}"
    pro = store.upsert_professional(
        id=pid, name=body.name, role=body.role, avatar_uri=body.avatar_uri,
    )
    return professional_to_dict(pro)


@router.patch("/professionals/{pid}")
def update_professional(tid: str, pid: str, body: ProfessionalPatch, request: Request) -> dict[str, Any]:
    _guard(tid, request)
    store = catalogue_for(tid)
    existing = store.get_professional(pid)
    if not existing:
        raise HTTPException(404, f"professional {pid!r} not found")
    pro = store.upsert_professional(
        id=pid,
        name=body.name if body.name is not None else existing.name,
        role=body.role if body.role is not None else existing.role,
        avatar_uri=body.avatar_uri if body.avatar_uri is not None else existing.avatar_uri,
    )
    return professional_to_dict(pro)


@router.delete("/professionals/{pid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_professional(tid: str, pid: str, request: Request) -> None:
    _guard(tid, request)
    store = catalogue_for(tid)
    if not store.delete_professional(pid):
        raise HTTPException(404, f"professional {pid!r} not found")


# ─── opening hours ────────────────────────────────────────────


@router.get("/hours")
def list_hours(tid: str, request: Request) -> dict[str, list[dict[str, Any]]]:
    _guard(tid, request)
    store = catalogue_for(tid)
    return {"hours": [hours_to_dict(h) for h in store.list_hours()]}


@router.put("/hours")
def replace_hours(tid: str, body: HoursUpdate, request: Request) -> dict[str, list[dict[str, Any]]]:
    _guard(tid, request)
    store = catalogue_for(tid)
    store.set_hours([DayHours(h.weekday, h.open_min, h.close_min) for h in body.hours])
    return {"hours": [hours_to_dict(h) for h in store.list_hours()]}
