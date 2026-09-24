"""Expo push token registration.

Mobile clients register their Expo push token on boot; the booking saga
looks it up by (tenant_id, user_id) to fire booking_confirmed pushes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.push_tokens import push_tokens_for


router = APIRouter(prefix="/v1/push", tags=["push"])


class PushRegister(BaseModel):
    tenant_id: str
    user_id: str
    expo_token: str
    platform: str | None = None


class PushUnregister(BaseModel):
    tenant_id: str
    user_id: str


@router.post("/register")
def register(body: PushRegister) -> dict[str, bool]:
    push_tokens_for(body.tenant_id).upsert(
        user_id=body.user_id,
        expo_token=body.expo_token,
        platform=body.platform or "unknown",
    )
    return {"ok": True}


@router.delete("/register")
def unregister(body: PushUnregister) -> dict[str, bool]:
    push_tokens_for(body.tenant_id).delete(body.user_id)
    return {"ok": True}
