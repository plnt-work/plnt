"""Consumer venue endpoints — mobile-facing.

These routes back the Fresha-style venue detail screens. No auth: the
mobile client is anonymous. The `tenant_id` query param picks the tenant
whose catalogue backs the venue (in MVP the venue → tenant mapping is
implicit — one catalogue per tenant, all place_ids point at it).

Endpoints:
  GET /v1/venues/{place_id}/services
  GET /v1/venues/{place_id}/team
  GET /v1/venues/{place_id}/reviews
  GET /v1/venues/{place_id}/availability
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from services.catalogue import (
    catalogue_for,
    compute_available_slots,
    service_to_dict,
    professional_to_dict,
)


router = APIRouter(prefix="/v1/venues", tags=["venues"])


@router.get("/{place_id}/services")
def get_services(place_id: str, tenant_id: str = Query(default="demo")) -> dict[str, list[dict[str, Any]]]:
    store = catalogue_for(tenant_id)
    return {"services": [service_to_dict(s) for s in store.list_services()]}


@router.get("/{place_id}/team")
def get_team(place_id: str, tenant_id: str = Query(default="demo")) -> dict[str, list[dict[str, Any]]]:
    store = catalogue_for(tenant_id)
    return {"team": [professional_to_dict(p) for p in store.list_professionals()]}


@router.get("/{place_id}/reviews")
def get_reviews(place_id: str, tenant_id: str = Query(default="demo")) -> dict[str, list[dict[str, Any]]]:
    return {"reviews": []}


@router.get("/{place_id}/availability")
def get_availability(
    place_id: str,
    date: str = Query(...),
    service_id: list[str] = Query(default_factory=list),
    pro_id: str = Query(default=""),
    tenant_id: str = Query(default="demo"),
) -> dict[str, Any]:
    from services.orders_store import orders_for

    store = catalogue_for(tenant_id)

    booked: set[str] = set()
    orders_store = orders_for(tenant_id)
    for order in orders_store.list_all(status="confirmed", user_id=None, since=None, limit=None)[0]:
        if order.date == date and (not pro_id or order.pro_id == pro_id):
            booked.add(order.slot)

    slots = compute_available_slots(
        store,
        date_iso=date,
        service_ids=service_id,
        pro_id=pro_id,
        booked_slots=booked,
    )
    return {"date": date, "slots": slots}
