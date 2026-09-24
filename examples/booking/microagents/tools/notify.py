"""notify_send — merchant notification fan-out.

Always writes the per-tenant feed (tenancy/notifications.py) — a feed
write failure raises, so the saga compensates. Email (Resend) and Expo
push are best-effort layered on top.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from tenancy import notifications
from tenancy.context import TenantContext

from microagents.tools import Tool, register


log = logging.getLogger("plnt_cloud.notify")

_RESEND_ENDPOINT = "https://api.resend.com/emails"

_KIND_TITLES = {
    "booking_confirmed": "Booking confirmed",
    "booking_compensated": "Booking cancelled (compensated)",
}

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "booking_id": {"type": "string", "description": "Booking id to attach to the notification."},
        "kind": {
            "type": "string",
            "description": "Notification kind (booking_confirmed|booking_compensated).",
        },
        "channel": {
            "type": "string",
            "description": "Preferred channel hint (sms|email|push). Adapter may override.",
        },
        "title": {"type": "string", "description": "Notification title (overrides default)."},
        "message": {"type": "string", "description": "Pre-rendered message body, when known."},
        "status_label": {"type": "string", "description": "Status verb, defaults to 'confirmed'."},
        "business_name": {"type": "string", "description": "Business the booking is at."},
        "slot": {"type": "string", "description": "ISO slot of the booking."},
        "party_size": {"type": "integer", "description": "Party size, when known."},
        "user_contact": {"type": "string", "description": "End-user contact for the booking."},
    },
    "required": ["booking_id"],
}


def _tenant_email(tenant_id: str) -> str:
    """notify_email override, else slice-5a's owner_email, from tenant.json."""
    import json
    from tenancy.factory import cloud_home
    path = cloud_home() / "tenants" / tenant_id / "tenant.json"
    if not path.exists():
        return ""
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(meta.get("notify_email") or meta.get("owner_email") or "")


def _send_resend_email(tenant_id: str, subject: str, body: str) -> bool:
    key = os.environ.get("PLNT_CLOUD_RESEND_KEY") or ""
    if not key:
        return False
    to = _tenant_email(tenant_id)
    if not to:
        return False
    sender = os.environ.get("PLNT_CLOUD_NOTIFY_FROM") or "bookings@plnt.work"
    resp = httpx.post(
        _RESEND_ENDPOINT,
        headers={"Authorization": f"Bearer {key}"},
        json={"from": sender, "to": [to], "subject": subject, "text": body},
        timeout=10.0,
    )
    resp.raise_for_status()
    return True


def _send_push(ctx: TenantContext, booking_id: str, kind: str, title: str, body: str) -> dict[str, Any]:
    from services.push_tokens import push_tokens_for
    from services.expo_push import send_expo_push

    token = push_tokens_for(ctx.tenant_id).get(ctx.user_id)
    if not token:
        return {"push_sent": False, "push_channel": "no-token"}
    push_result = send_expo_push(
        tokens=[token.expo_token],
        title=title,
        body=body,
        data={"booking_id": booking_id, "kind": kind},
    )
    return {
        "push_sent": bool(push_result.get("sent")),
        "push_channel": str(push_result.get("channel") or "expo"),
    }


def _notify_send(
    ctx: TenantContext,
    *,
    booking_id: str,
    kind: str = "booking_confirmed",
    channel: str = "push",
    title: str = "",
    message: str = "",
    status_label: str = "confirmed",
    business_name: str = "",
    slot: str = "",
    party_size: int | None = None,
    user_contact: str = "",
) -> dict[str, Any]:
    resolved_title = title or _KIND_TITLES.get(kind) or f"Booking {status_label or 'confirmed'}"
    at = f" at {business_name}" if business_name else ""
    when = f" for {slot}" if slot else ""
    resolved_body = message or f"Booking {booking_id}{at}{when} is {status_label or 'confirmed'}."

    # Feed write is the one mandatory channel: it raises on failure (saga
    # compensates), and its dedup gate keeps activity retries from
    # double-sending the best-effort email/push below.
    entry, created = notifications.append(
        ctx.tenant_id,
        kind=kind,
        title=resolved_title,
        body=resolved_body,
        data={
            "booking_id": booking_id,
            "business_name": business_name,
            "slot": slot,
            "party_size": party_size,
            "user_contact": user_contact or ctx.user_id,
        },
    )
    result: dict[str, Any] = {
        "sent": True,
        "channel": "feed",
        "booking_id": booking_id,
        "tenant_id": ctx.tenant_id,
        "notification_id": entry["id"],
        "deduped": not created,
        "email_sent": False,
    }
    if not created:
        return result

    try:
        result["email_sent"] = _send_resend_email(ctx.tenant_id, resolved_title, resolved_body)
    except Exception as e:
        log.warning("resend email failed for booking %s: %s", booking_id, e)

    try:
        result.update(_send_push(ctx, booking_id, kind, resolved_title, resolved_body))
    except Exception as e:
        log.warning("expo push failed for booking %s: %s", booking_id, e)

    return result


register(Tool(
    name="notify_send",
    description=(
        "Send a booking notification to the merchant. Always records an "
        "entry in the tenant's dashboard feed; additionally emails via "
        "Resend and pushes via Expo when configured. Idempotent per "
        "(booking_id, kind)."
    ),
    schema=_SCHEMA,
    fn=_notify_send,
))
