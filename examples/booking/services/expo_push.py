"""Expo push notifications client.

Thin wrapper over Expo's push HTTP API. One function: `send_expo_push`,
posts a message array to https://exp.host/--/api/v2/push/send.

Reference: https://docs.expo.dev/push-notifications/sending-notifications/

We do NOT retry, batch, or reconcile receipts here — the notify saga
step already runs inside a Temporal Activity with retry/timeout policy,
and receipt reconciliation is deferred until we have a real ops story.

When PLNT_CLOUD_PUSH_ENABLED is unset the function returns a "disabled"
result without touching the network — so dev workflows don't require an
outbound Expo call.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx


log = logging.getLogger("plnt_cloud.expo_push")

_EXPO_ENDPOINT = "https://exp.host/--/api/v2/push/send"


def is_enabled() -> bool:
    return os.environ.get("PLNT_CLOUD_PUSH_ENABLED", "").lower() in ("1", "true", "yes")


def send_expo_push(
    *,
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    priority: str = "high",
    timeout_s: float = 8.0,
) -> dict[str, Any]:
    """Send one push to N tokens. Returns a dict summary.

    Returns:
        {
          "sent": bool,
          "channel": "expo" | "disabled" | "none",
          "count": <int>,
          "tickets": [...],       # raw expo response data field, if present
          "error": <str> or None,
        }
    """
    tokens = [t for t in tokens if t and t.startswith("ExponentPushToken")]
    if not tokens:
        return {"sent": False, "channel": "none", "count": 0, "tickets": []}

    if not is_enabled():
        log.info("expo_push: disabled (PLNT_CLOUD_PUSH_ENABLED unset), skipping %d token(s)", len(tokens))
        return {"sent": False, "channel": "disabled", "count": len(tokens), "tickets": []}

    messages = [
        {
            "to": t,
            "title": title,
            "body": body,
            "data": data or {},
            "priority": priority,
            "sound": "default",
        }
        for t in tokens
    ]

    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(
                _EXPO_ENDPOINT,
                json=messages,
                headers={"accept": "application/json", "content-type": "application/json"},
            )
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as e:
        log.warning("expo_push: HTTP error: %s", e)
        return {"sent": False, "channel": "expo", "count": len(tokens),
                "tickets": [], "error": str(e)}
    tickets = payload.get("data") if isinstance(payload, dict) else None
    return {
        "sent": True, "channel": "expo", "count": len(tokens),
        "tickets": tickets or [],
    }
