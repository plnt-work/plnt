"""FastAPI surface — slice 1 mounts only the web WebSocket channel.

Run:
    uvicorn surface.app:app --reload --port 8080
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from channels.web_ws import router as web_ws_router
from surface.admin import router as admin_router
from surface.admin_v2 import router as admin_v2_router, marketplace_router
from surface.auth import router as auth_router
from surface.bookings_v2 import router as bookings_v2_router
from surface.catalogue_admin import router as catalogue_admin_router
from surface.docs_upload import router as docs_upload_router
from surface.onboard import router as onboard_router
from surface.push import router as push_router
from surface.venues import router as venues_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="plnt-cloud",
        version="0.1.0",
        description="Multi-tenant micro-agent platform — slice 1 surface",
    )

    # CORS allow-list. Comma-separated. Add the Cloudflare tunnel hostname
    # (e.g. https://api.dev.<your-zone>) here so the mobile app and any
    # tunnel-routed callers can hit the surface without code edits.
    allow_origins = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in allow_origins if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/skills")
    def skills() -> dict[str, list[str]]:
        """List the micro-agent roles shipped with this build."""
        from microagents.loader import list_skills
        return {"skills": list_skills()}

    app.include_router(web_ws_router)
    app.include_router(admin_router)
    app.include_router(admin_v2_router)
    app.include_router(marketplace_router)
    app.include_router(auth_router)
    app.include_router(bookings_v2_router)
    app.include_router(catalogue_admin_router)
    app.include_router(docs_upload_router)
    app.include_router(onboard_router)
    app.include_router(push_router)
    app.include_router(venues_router)
    return app


app = create_app()
