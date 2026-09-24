"""Consumer booking endpoints — POST /v1/bookings + reads.

Matches the mobile BookingSummary / CreateBookingRequest schemas exactly.
Multi-service orders are created via the sibling `orders_store`.

Endpoints:
  POST /v1/bookings
  GET  /v1/users/{user_id}/bookings
  GET  /v1/bookings/{booking_id}
"""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.catalogue import catalogue_for


log = logging.getLogger("plnt_cloud.bookings_v2")

router = APIRouter(tags=["bookings"])


class CreateBookingRequest(BaseModel):
    place_id: str
    venue_name: str
    user_id: str
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    slot: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    pro_id: str
    service_ids: list[str] = Field(default_factory=list)


def _service_dict(sid: str, catalogue) -> dict[str, Any]:
    s = catalogue.get_service(sid)
    if not s:
        raise HTTPException(400, f"unknown service_id {sid!r}")
    return {
        "id": s.id,
        "name": s.name,
        "duration_min": s.duration_min,
        "price_cents": s.price_cents,
        "description": s.description,
    }


def _order_to_summary(order) -> dict[str, Any]:
    created_iso = _dt.datetime.utcfromtimestamp(order.created_at).isoformat() + "Z"
    return {
        "booking_id": order.order_id,
        "place_id": order.place_id,
        "venue_name": order.venue_name,
        "date": order.date,
        "slot": order.slot,
        "pro_id": order.pro_id,
        "services": list(order.services),
        "total_cents": order.total_cents,
        "status": order.status,
        "created_at": created_iso,
    }


def _fire_push(tenant_id: str, user_id: str, order) -> None:
    from services.push_tokens import push_tokens_for
    from services.expo_push import send_expo_push

    token = push_tokens_for(tenant_id).get(user_id)
    if not token:
        return
    try:
        send_expo_push(
            tokens=[token.expo_token],
            title="Booking confirmed",
            body=f"{order.venue_name} on {order.date} at {order.slot}",
            data={"booking_id": order.order_id, "kind": "booking_confirmed"},
        )
    except Exception as e:  # noqa: BLE001 — best-effort push
        log.warning("push notification failed: %s", e)


@router.post("/v1/bookings")
def create_booking(
    body: CreateBookingRequest,
    tenant_id: str = Query(default="demo"),
) -> dict[str, Any]:
    from services.orders_store import orders_for

    catalogue = catalogue_for(tenant_id)
    services = [_service_dict(sid, catalogue) for sid in body.service_ids]
    idempotency_key = (
        f"{body.user_id}:{body.place_id}:{body.date}:{body.slot}:"
        f"{','.join(sorted(body.service_ids))}:{body.pro_id}"
    )
    order = orders_for(tenant_id).create_order(
        tenant_id=tenant_id,
        user_id=body.user_id,
        place_id=body.place_id,
        venue_name=body.venue_name,
        date=body.date,
        slot=body.slot,
        pro_id=body.pro_id,
        services=services,
        idempotency_key=idempotency_key,
    )
    _fire_push(tenant_id, body.user_id, order)
    return {"booking": _order_to_summary(order)}


@router.get("/v1/users/{user_id}/bookings")
def user_bookings(user_id: str, tenant_id: str = Query(default="demo")) -> dict[str, list[dict[str, Any]]]:
    from services.orders_store import orders_for

    today = _dt.date.today().isoformat()
    orders = orders_for(tenant_id).list_for_user(user_id)
    upcoming: list[dict[str, Any]] = []
    past: list[dict[str, Any]] = []
    for o in orders:
        summary = _order_to_summary(o)
        if o.date >= today:
            upcoming.append(summary)
        else:
            past.append(summary)
    return {"upcoming": upcoming, "past": past}


@router.get("/v1/bookings/{booking_id}")
def get_booking(booking_id: str, tenant_id: str = Query(default="demo")) -> dict[str, Any]:
    from services.orders_store import orders_for

    order = orders_for(tenant_id).get_order(booking_id)
    if not order:
        raise HTTPException(404, f"booking {booking_id!r} not found")
    return _order_to_summary(order)
