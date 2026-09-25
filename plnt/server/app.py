"""The plnt HTTP API (`plnt serve`).

Auth (fail-closed):
  * Operator routes need `Authorization: Bearer $PLNT_ADMIN_TOKEN`. If the
    server has no admin token they answer 503 — never open.
  * Tenant routes accept the admin token or that tenant's own API key
    (`pk_…`, shown once at creation). A key for tenant A is rejected on
    tenant B's routes.
  * `dev=True` (only via `plnt dev`, bound to loopback) disables auth.

Routes (all under /v1):
  GET    /health
  GET    /bundles                                   catalog of installable bundles
  POST   /tenants                     {id, name}    -> {tenant, api_key}
  GET    /tenants
  GET    /tenants/{t}
  DELETE /tenants/{t}
  POST   /tenants/{t}/keys                          rotate -> {api_key}
  GET    /tenants/{t}/installs
  POST   /tenants/{t}/installs        {bundle, config}
  PATCH  /tenants/{t}/installs/{slug} {enabled?, config?}
  DELETE /tenants/{t}/installs/{slug}
  GET    /tenants/{t}/secrets                       names only
  PUT    /tenants/{t}/secrets/{name}  {value}
  DELETE /tenants/{t}/secrets/{name}
  GET    /tenants/{t}/model           PUT {…} / DELETE      per-tenant model (BYO)
  GET    /tenants/{t}/model/health                  reachability + model present
  POST   /tenants/{t}/sessions        {bundle, user_id?}    -> {session_id}
  GET    /tenants/{t}/sessions
  POST   /tenants/{t}/sessions/{sid}/messages {text}        -> {run_id}
  GET    /tenants/{t}/sessions/{sid}/events?after=N         JSON
  GET    /tenants/{t}/sessions/{sid}/stream?after=N         SSE
  POST   /tenants/{t}/sessions/{sid}/kill
  GET    /tenants/{t}/usage?since=<epoch>
  GET    /tenants/{t}/audit?limit=N&action=
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets as _secrets
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from plnt import __version__
from plnt.bundles import catalog
from plnt.bundles.bundle import BundleError
from plnt.executors import LocalExecutor, SessionError
from plnt.models import ModelError, get_provider
from plnt.tenancy import installs
from plnt.tenancy.tenants import Tenant, TenantError, TenantNotFound, TenantStore


class TenantCreate(BaseModel):
    id: str
    name: str = ""


class InstallBody(BaseModel):
    bundle: str
    config: dict[str, Any] = Field(default_factory=dict)


class InstallPatch(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class SecretBody(BaseModel):
    value: str


class SessionCreate(BaseModel):
    bundle: str
    user_id: str = ""


class MessageBody(BaseModel):
    text: str = Field(min_length=1, max_length=32_000)


def create_app(
    *,
    store: TenantStore | None = None,
    executor: LocalExecutor | None = None,
    admin_token: str | None = None,
    dev: bool = False,
) -> FastAPI:
    store = store or TenantStore()
    executor = executor or LocalExecutor(store)
    admin_token = admin_token if admin_token is not None else os.environ.get("PLNT_ADMIN_TOKEN", "")
    app = FastAPI(title="plnt", version=__version__)
    app.state.store, app.state.executor, app.state.dev = store, executor, dev

    # ---------------------------------------------------------------- auth

    def _bearer(authorization: str) -> str:
        scheme, _, token = authorization.partition(" ")
        return token.strip() if scheme.lower() == "bearer" else ""

    def _is_admin(token: str) -> bool:
        return bool(admin_token) and bool(token) and _secrets.compare_digest(token, admin_token)

    def require_admin(authorization: str = Header(default="")) -> None:
        if dev:
            return
        if not admin_token:
            raise HTTPException(503, "operator routes are disabled: set PLNT_ADMIN_TOKEN")
        if not _is_admin(_bearer(authorization)):
            raise HTTPException(401, "admin token required")

    def tenant_access(t: str, authorization: str = Header(default="")) -> Tenant:
        try:
            tenant = store.get(t)
        except (TenantNotFound, TenantError):
            raise HTTPException(404, f"tenant {t!r} not found") from None
        if dev:
            return tenant
        token = _bearer(authorization)
        if _is_admin(token) or (token and tenant.verify_key(token)):
            return tenant
        raise HTTPException(401, "tenant API key or admin token required")

    def _bad(e: Exception, code: int = 400) -> HTTPException:
        return HTTPException(code, str(e))

    # ---------------------------------------------------------------- meta

    @app.get("/v1/whoami")
    def whoami(authorization: str = Header(default="")) -> dict[str, Any]:
        """What the presented credential can do — lets the console pick its mode."""
        if dev:
            return {"role": "dev"}
        token = _bearer(authorization)
        if _is_admin(token):
            return {"role": "admin"}
        tenant = store.find_by_key(token) if token else None
        if tenant is None:
            raise HTTPException(401, "unknown token")
        return {"role": "tenant", "tenant_id": tenant.id}

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "version": __version__, "dev": dev}

    @app.get("/v1/bundles")
    def list_bundles() -> dict[str, Any]:
        found, errors = catalog.available()
        return {
            "bundles": [
                {
                    "slug": b.slug,
                    "version": b.version,
                    "description": b.manifest.meta.description,
                    "tags": b.manifest.meta.tags,
                    "tools": b.manifest.runtime.tools,
                    "config_schema": b.config_schema,
                    "secrets": b.manifest.secrets.required,
                }
                for b in found.values()
            ],
            "errors": errors,
        }

    # ---------------------------------------------------------------- tenants

    @app.post("/v1/tenants", status_code=201, dependencies=[Depends(require_admin)])
    def create_tenant(body: TenantCreate) -> dict[str, Any]:
        try:
            tenant, key = store.create(body.id, body.name)
        except TenantError as e:
            raise _bad(e, 409 if "exists" in str(e) else 400) from None
        return {"tenant": tenant.summary(), "api_key": key}

    @app.get("/v1/tenants", dependencies=[Depends(require_admin)])
    def list_tenants() -> dict[str, Any]:
        return {"tenants": [t.summary() for t in store.list()]}

    @app.get("/v1/tenants/{t}")
    def get_tenant(tenant: Tenant = Depends(tenant_access)) -> dict[str, Any]:
        return {
            **tenant.summary(),
            "installs": [_install_view(i) for i in installs.list_installed(tenant)],
            "secrets": tenant.secret_names(),
            "model": _public_model(tenant),
        }

    @app.delete("/v1/tenants/{t}", status_code=204, dependencies=[Depends(require_admin)])
    def delete_tenant(t: str) -> None:
        try:
            store.delete(t)
        except (TenantNotFound, TenantError):
            raise HTTPException(404, f"tenant {t!r} not found") from None

    @app.post("/v1/tenants/{t}/keys", dependencies=[Depends(require_admin)])
    def rotate_key(t: str) -> dict[str, str]:
        try:
            return {"api_key": store.get(t).rotate_key()}
        except (TenantNotFound, TenantError):
            raise HTTPException(404, f"tenant {t!r} not found") from None

    # ---------------------------------------------------------------- installs

    @app.get("/v1/tenants/{t}/installs")
    def list_installs(tenant: Tenant = Depends(tenant_access)) -> dict[str, Any]:
        return {"installs": [_install_view(i) for i in installs.list_installed(tenant)]}

    @app.post("/v1/tenants/{t}/installs", status_code=201)
    def install(body: InstallBody, tenant: Tenant = Depends(tenant_access)) -> dict[str, Any]:
        # Installing arbitrary paths from a tenant key would let a tenant load
        # code onto the server; tenants may only install catalog slugs.
        try:
            found, _ = catalog.available()
            if body.bundle not in found:
                raise BundleError(f"no bundle {body.bundle!r} in the catalog")
            inst = installs.install(tenant, found[body.bundle], body.config)
        except BundleError as e:
            raise _bad(e, 422) from None
        return _install_view(inst)

    @app.patch("/v1/tenants/{t}/installs/{slug}")
    def patch_install(
        slug: str, body: InstallPatch, tenant: Tenant = Depends(tenant_access)
    ) -> dict[str, Any]:
        try:
            return _install_view(
                installs.update(tenant, slug, enabled=body.enabled, config=body.config)
            )
        except BundleError as e:
            raise _bad(e, 404 if "not installed" in str(e) else 422) from None

    @app.delete("/v1/tenants/{t}/installs/{slug}", status_code=204)
    def uninstall(slug: str, tenant: Tenant = Depends(tenant_access)) -> None:
        try:
            installs.uninstall(tenant, slug)
        except BundleError as e:
            raise _bad(e, 404) from None

    # ---------------------------------------------------------------- secrets

    @app.get("/v1/tenants/{t}/secrets")
    def list_secrets(tenant: Tenant = Depends(tenant_access)) -> dict[str, list[str]]:
        return {"secrets": tenant.secret_names()}

    @app.put("/v1/tenants/{t}/secrets/{name}", status_code=204)
    def put_secret(name: str, body: SecretBody, tenant: Tenant = Depends(tenant_access)) -> None:
        try:
            tenant.set_secret(name, body.value)
        except TenantError as e:
            raise _bad(e) from None
        tenant.audit("secret.set", name=name)

    @app.delete("/v1/tenants/{t}/secrets/{name}", status_code=204)
    def delete_secret(name: str, tenant: Tenant = Depends(tenant_access)) -> None:
        if not tenant.delete_secret(name):
            raise HTTPException(404, f"secret {name!r} not set")
        tenant.audit("secret.deleted", name=name)

    # ---------------------------------------------------------------- model

    def _public_model(tenant: Tenant) -> dict[str, Any] | None:
        return tenant.model_config()  # holds a secret *name*, never a value

    @app.get("/v1/tenants/{t}/model")
    def get_model(tenant: Tenant = Depends(tenant_access)) -> dict[str, Any]:
        return {"model": _public_model(tenant)}

    @app.put("/v1/tenants/{t}/model")
    def put_model(body: dict[str, Any], tenant: Tenant = Depends(tenant_access)) -> dict[str, Any]:
        try:
            tenant.set_model_config(body)
        except TenantError as e:
            raise _bad(e) from None
        tenant.audit("model.set", provider=body.get("provider"), model=body.get("model"))
        return {"model": _public_model(tenant)}

    @app.delete("/v1/tenants/{t}/model", status_code=204)
    def delete_model(tenant: Tenant = Depends(tenant_access)) -> None:
        tenant.set_model_config(None)
        tenant.audit("model.cleared")

    @app.get("/v1/tenants/{t}/model/health")
    def model_health(tenant: Tenant = Depends(tenant_access)) -> dict[str, Any]:
        try:
            profile = tenant.model_profile()
        except (ModelError, TenantError) as e:
            return {"ok": False, "detail": str(e), "hint": getattr(e, "hint", "")}
        rep = get_provider(profile).health()
        return {
            "ok": rep.ok,
            "provider": rep.provider,
            "base_url": rep.base_url,
            "model": rep.model,
            "reachable": rep.reachable,
            "model_present": rep.model_present,
            "detail": rep.detail,
            "hint": rep.hint,
        }

    # ---------------------------------------------------------------- sessions

    @app.post("/v1/tenants/{t}/sessions", status_code=201)
    def create_session(
        body: SessionCreate, tenant: Tenant = Depends(tenant_access)
    ) -> dict[str, str]:
        try:
            sid = executor.start_session(tenant.id, body.bundle, body.user_id)
        except BundleError as e:
            raise _bad(e, 409) from None
        return {"session_id": sid}

    @app.get("/v1/tenants/{t}/sessions")
    def list_sessions(limit: int = 100, tenant: Tenant = Depends(tenant_access)) -> dict[str, Any]:
        return {"sessions": executor.db(tenant).sessions(limit)}

    @app.post("/v1/tenants/{t}/sessions/{sid}/messages", status_code=202)
    def send_message(
        sid: str, body: MessageBody, tenant: Tenant = Depends(tenant_access)
    ) -> dict[str, str]:
        try:
            run_id = executor.send(tenant.id, sid, body.text)
        except SessionError as e:
            raise _bad(e, 409 if "already running" in str(e) else 404) from None
        return {"run_id": run_id}

    @app.get("/v1/tenants/{t}/sessions/{sid}/events")
    def get_events(
        sid: str, after: int = 0, tenant: Tenant = Depends(tenant_access)
    ) -> dict[str, Any]:
        try:
            return {"events": executor.events_since(tenant.id, sid, after)}
        except SessionError as e:
            raise _bad(e, 404) from None

    @app.get("/v1/tenants/{t}/sessions/{sid}/stream")
    async def stream(
        sid: str,
        request: Request,
        after: int = 0,
        until_idle: bool = False,
        tenant: Tenant = Depends(tenant_access),
    ) -> EventSourceResponse:
        try:
            executor.events_since(tenant.id, sid, after)
        except SessionError as e:
            raise _bad(e, 404) from None

        async def gen():
            last = after
            while not await request.is_disconnected():
                events = await asyncio.to_thread(executor.events_since, tenant.id, sid, last)
                for e in events:
                    last = e["seq"]
                    yield {"id": str(e["seq"]), "event": e["kind"], "data": json.dumps(e)}
                    if until_idle and e["kind"] == "run_finished":
                        return
                await asyncio.sleep(0.2)

        return EventSourceResponse(gen())

    @app.post("/v1/tenants/{t}/sessions/{sid}/kill")
    def kill(sid: str, tenant: Tenant = Depends(tenant_access)) -> dict[str, bool]:
        killed = executor.kill(tenant.id, sid)
        if killed:
            tenant.audit("run.kill_requested", session_id=sid)
        return {"killed": killed}

    # ---------------------------------------------------------------- usage / audit

    @app.get("/v1/tenants/{t}/usage")
    def usage(since: float = 0.0, tenant: Tenant = Depends(tenant_access)) -> dict[str, Any]:
        return executor.db(tenant).usage_summary(since)

    @app.get("/v1/tenants/{t}/audit")
    def audit(
        limit: int = 200, action: str | None = None, tenant: Tenant = Depends(tenant_access)
    ) -> dict[str, Any]:
        return {"events": tenant.audit_events(limit, action)}

    _mount_console(app)
    return app


def _install_view(inst: installs.Installation) -> dict[str, Any]:
    """An install plus what a UI needs to edit it: the installed version's own
    config schema and required secrets (they can differ from the catalog's)."""
    view = inst.to_dict()
    try:
        b = inst.load()
        view["config_schema"] = b.config_schema
        view["secrets_required"] = b.manifest.secrets.required
        view["description"] = b.manifest.meta.description
    except BundleError as e:
        view["load_error"] = str(e)
    return view


CONSOLE_DIR = Path(__file__).parent / "console"


def _mount_console(app: FastAPI) -> None:
    """Serve the built web console (console/ → plnt/server/console) at /console."""
    index = CONSOLE_DIR / "index.html"

    if not index.is_file():

        @app.get("/console", include_in_schema=False)
        @app.get("/console/{path:path}", include_in_schema=False)
        def console_missing(path: str = "") -> HTMLResponse:
            return HTMLResponse(
                "<p>The console is not built. Run <code>npm ci && npm run build</code> "
                "in <code>console/</code>, then restart the server.</p>",
                status_code=404,
            )

        return

    app.mount("/console/assets", StaticFiles(directory=CONSOLE_DIR / "assets"), name="console")

    @app.get("/console", include_in_schema=False)
    @app.get("/console/{path:path}", include_in_schema=False)
    def console_index(path: str = "") -> FileResponse:
        # Client-side routing: every console URL serves the SPA shell.
        return FileResponse(index)
