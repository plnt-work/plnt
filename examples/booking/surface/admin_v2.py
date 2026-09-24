"""Admin v2 — bookings, sessions, users, marketplace, installed agents.

Additive layer on top of surface/admin.py. Shapes match the typed
frontend client at web/src/lib/api/admin-v2.ts. All routes gated by
`require_tenant_access`: admin bearer OR the owning merchant's
`plnt_onboard` session cookie (slice 6).

Data sources (all per-tenant, on-disk — no Temporal round-trips):
  bookings   — workflows/bookings_store.py (chat confirm-and-book path)
               merged with services/orders_store.py (multi-service cart path)
  sessions   — tenancy/audit.py events grouped by session_id
  agents     — the tenant's agents_dir bundles (slice-2 install semantics:
               `<slug>@<version>/` dirs, `disabled` marker, `.trash/`,
               `.reload` cache-bust marker consumed by microagents/loader.py)
  catalog    — marketplace/catalog.json (versioned in git)
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from surface.auth_deps import require_admin_or_merchant, require_tenant_access


# ─────────────────────────────────────────────────────────── helpers


def _session_status(last_ts: float) -> str:
    """Map last-activity age to the SessionStatus enum."""
    age = time.time() - last_ts
    if age < 5 * 60:
        return "active"
    if age < 60 * 60:
        return "idle"
    return "closed"


def _ledger_to_booking(b) -> dict[str, Any]:
    # user_contact carries the user_id when the chat path had no explicit
    # contact (workflows/session.py falls back to user_id).
    return {
        "booking_id": b.booking_id,
        "user_id": b.user_contact,
        "business_id": b.business_id,
        "slot": b.slot,
        "status": b.status,
        "idempotency_key": b.idempotency_key,
        "created_at": b.created_at,
    }


def _order_to_booking(order) -> dict[str, Any]:
    slot_iso = f"{order.date}T{order.slot}:00"
    return {
        "booking_id": order.order_id,
        "user_id": order.user_id,
        "business_id": order.place_id,
        "slot": slot_iso,
        "status": order.status,
        "idempotency_key": order.idempotency_key,
        "created_at": order.created_at,
    }


def _all_bookings(
    tid: str,
    status_: str | None = None,
    user_id: str | None = None,
    since: float | None = None,
) -> list[dict[str, Any]]:
    """Both booking ledgers merged, newest first. Filters applied in SQL."""
    from workflows.bookings_store import bookings_for
    from services.orders_store import orders_for

    ledger, _ = bookings_for(tid).list_all(
        status=status_, user_id=user_id, since=since, limit=None,
    )
    orders, _ = orders_for(tid).list_all(
        status=status_, user_id=user_id, since=since, limit=None,
    )
    rows = [_ledger_to_booking(b) for b in ledger] + [_order_to_booking(o) for o in orders]
    rows.sort(key=lambda r: float(r["created_at"]), reverse=True)
    return rows


def _aggregate_sessions(tid: str, user_filter: str | None = None) -> list[dict[str, Any]]:
    from tenancy.audit import read_events

    by_sid: dict[str, dict[str, Any]] = {}
    for evt in read_events(tid):
        sid = evt.get("session_id")
        if not sid:
            continue
        uid = str(evt.get("user_id") or "")
        if user_filter and uid != user_filter:
            continue
        ts = evt.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        row = by_sid.setdefault(str(sid), {
            "session_id": str(sid),
            "user_id": uid,
            "business_id": None,
            "message_count": 0,
            "last_message_at": float(ts),
            "started_at": float(ts),
        })
        row["message_count"] = int(row["message_count"]) + 1
        row["last_message_at"] = max(float(row["last_message_at"]), float(ts))
        row["started_at"] = min(float(row["started_at"]), float(ts))
        if uid and not row["user_id"]:
            row["user_id"] = uid

    out: list[dict[str, Any]] = []
    for row in by_sid.values():
        row["status"] = _session_status(float(row["last_message_at"]))
        out.append(row)
    out.sort(key=lambda r: float(r["last_message_at"]), reverse=True)
    return out


# ─────────────────────────────────────────────────────────── admin router


# Every route here is /tenants/{tid}/… — the gate admits the admin bearer
# OR the merchant whose onboard-session email owns tenant {tid}.
router = APIRouter(
    prefix="/v1/admin", dependencies=[Depends(require_tenant_access)], tags=["admin_v2"],
)


@router.get("/tenants/{tid}/bookings")
def list_bookings(
    tid: str,
    status_: str | None = Query(default=None, alias="status"),
    user_id: str | None = None,
    since: float | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    rows = _all_bookings(tid, status_=status_, user_id=user_id, since=since)
    total = len(rows)
    if limit is not None:
        rows = rows[:limit]
    return {"bookings": rows, "total": total}


@router.get("/tenants/{tid}/sessions")
def list_sessions(
    tid: str,
    user_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    sessions = _aggregate_sessions(tid, user_filter=user_id)
    total = len(sessions)
    if limit is not None:
        sessions = sessions[:limit]
    return {"sessions": sessions, "total": total}


@router.get("/tenants/{tid}/sessions/{sid}/transcript")
def get_transcript(tid: str, sid: str) -> dict[str, list[dict[str, Any]]]:
    from tenancy.audit import read_events

    entries: list[dict[str, Any]] = []
    for evt in read_events(tid):
        if str(evt.get("session_id") or "") != sid:
            continue
        ts = evt.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        content = {k: v for k, v in evt.items() if k not in ("session_id", "role", "ts", "action")}
        entries.append({
            "seq": 0,
            "role": str(evt.get("role") or ""),
            "content": content,
            "action": evt.get("action") if isinstance(evt.get("action"), dict) else None,
            "at": float(ts),
        })
    entries.sort(key=lambda e: e["at"])
    for i, e in enumerate(entries, 1):
        e["seq"] = i
    return {"transcript": entries}


# ─────────────────────────────────────────────────────────── notifications


class NotificationsRead(BaseModel):
    ids: list[str]


@router.get("/tenants/{tid}/notifications")
def list_notifications(
    tid: str,
    limit: int | None = None,
    unread: bool = False,
) -> dict[str, Any]:
    from tenancy.notifications import list_notifications as feed_list, unread_count

    return {
        "notifications": feed_list(tid, limit=limit, unread_only=unread),
        "unread_count": unread_count(tid),
    }


@router.post("/tenants/{tid}/notifications/read")
def mark_notifications_read(tid: str, body: NotificationsRead) -> dict[str, Any]:
    from tenancy.notifications import mark_read

    return {"updated": mark_read(tid, body.ids)}


@router.get("/tenants/{tid}/users")
def list_users(tid: str) -> dict[str, list[dict[str, Any]]]:
    from tenancy.audit import read_events

    per_user: dict[str, dict[str, Any]] = {}
    sessions_by_user: dict[str, set[str]] = {}
    for evt in read_events(tid):
        uid = str(evt.get("user_id") or "")
        if not uid:
            continue
        ts = evt.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        row = per_user.setdefault(uid, {
            "user_id": uid,
            "first_seen": float(ts),
            "last_seen": float(ts),
            "sessions": 0,
            "bookings": 0,
        })
        row["first_seen"] = min(float(row["first_seen"]), float(ts))
        row["last_seen"] = max(float(row["last_seen"]), float(ts))
        sid = evt.get("session_id")
        if sid:
            sessions_by_user.setdefault(uid, set()).add(str(sid))

    for uid, sids in sessions_by_user.items():
        per_user[uid]["sessions"] = len(sids)

    for b in _all_bookings(tid):
        uid = str(b["user_id"] or "")
        if not uid:
            continue
        created = float(b["created_at"])
        row = per_user.setdefault(uid, {
            "user_id": uid,
            "first_seen": created,
            "last_seen": created,
            "sessions": 0,
            "bookings": 0,
        })
        row["bookings"] = int(row["bookings"]) + 1
        row["first_seen"] = min(float(row["first_seen"]), created)
        row["last_seen"] = max(float(row["last_seen"]), created)

    users = sorted(per_user.values(), key=lambda r: float(r["last_seen"]), reverse=True)
    return {"users": users}


@router.get("/tenants/{tid}/users/{uid}")
def get_user(tid: str, uid: str) -> dict[str, Any]:
    bookings = _all_bookings(tid, user_id=uid)
    sessions = _aggregate_sessions(tid, user_filter=uid)
    return {"user_id": uid, "bookings": bookings, "sessions": sessions}


# ─────────────────────────────────────────────────────────── marketplace


def _catalog_path() -> Path:
    return Path(__file__).resolve().parent.parent / "marketplace" / "catalog.json"


def _catalog() -> list[dict[str, Any]]:
    path = _catalog_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    agents = data.get("agents")
    return agents if isinstance(agents, list) else []


def _catalog_entry(slug: str) -> dict[str, Any] | None:
    for entry in _catalog():
        if entry.get("slug") == slug:
            return entry
    return None


# Catalog is not per-tenant; the merchant Console's Agents tab needs it,
# so any signed-in merchant session passes alongside the admin bearer.
marketplace_router = APIRouter(
    prefix="/v1/marketplace",
    dependencies=[Depends(require_admin_or_merchant)],
    tags=["marketplace"],
)


@marketplace_router.get("/agents")
def marketplace_agents(vertical: str | None = None) -> dict[str, list[dict[str, Any]]]:
    agents = _catalog()
    if vertical:
        wanted = {v.strip() for v in vertical.split(",") if v.strip()}
        agents = [
            a for a in agents
            if (verts := {v.strip() for v in str(a.get("vertical", "")).split(",")})
            and ("any" in verts or wanted & verts)
        ]
    return {"agents": agents}


# ─────────────────────────────────────────────────────────── installed agents


def _agents_dir(tid: str) -> Path:
    from tenancy.factory import for_tenant
    return for_tenant(tid).agents_dir


def _touch_reload(agents_dir: Path) -> None:
    (agents_dir / ".reload").touch()


def _parse_version(raw: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in raw.split("."))
    except ValueError:
        return None


def _installed_bundles(agents_dir: Path) -> dict[str, Path]:
    """slug → highest-semver bundle dir. Includes disabled bundles (the
    admin must see them; only the loader skips them)."""
    best: dict[str, tuple[tuple[int, ...], Path]] = {}
    if not agents_dir.is_dir():
        return {}
    for d in agents_dir.iterdir():
        if not d.is_dir() or d.name.startswith(".") or "@" not in d.name:
            continue
        slug, _, raw_ver = d.name.rpartition("@")
        version = _parse_version(raw_ver)
        if not slug or version is None:
            continue
        cur = best.get(slug)
        if cur is None or version > cur[0]:
            best[slug] = (version, d)
    return {slug: path for slug, (_, path) in best.items()}


def _usage_by_role(tid: str) -> dict[str, dict[str, Any]]:
    """role → {last_used_at, sessions} from the audit log. An installed
    bundle's slug IS the role the loader serves it under, so audit rows
    with role == slug are that agent's real usage."""
    from tenancy.audit import read_events

    out: dict[str, dict[str, Any]] = {}
    for evt in read_events(tid):
        role = str(evt.get("role") or "")
        ts = evt.get("ts")
        if not role or not isinstance(ts, (int, float)):
            continue
        row = out.setdefault(role, {"last_used_at": float(ts), "sessions": set()})
        row["last_used_at"] = max(float(row["last_used_at"]), float(ts))
        sid = evt.get("session_id")
        if sid:
            row["sessions"].add(str(sid))
    return out


def _read_config(bundle_dir: Path) -> dict[str, Any]:
    cfg_path = bundle_dir / "config.json"
    if not cfg_path.exists():
        return {}
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return cfg if isinstance(cfg, dict) else {}


def _installed_agent_dict(
    slug: str, bundle_dir: Path, usage: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    u = usage.get(slug)
    return {
        "slug": slug,
        "version": bundle_dir.name.rpartition("@")[2],
        "enabled": not (bundle_dir / "disabled").exists(),
        "config": _read_config(bundle_dir),
        "installed_at": bundle_dir.stat().st_mtime,
        "last_used_at": float(u["last_used_at"]) if u else None,
        "conversation_count": len(u["sessions"]) if u else 0,
    }


class AgentInstall(BaseModel):
    version: str | None = None
    config: dict[str, Any] | None = None


class AgentPatch(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None


@router.get("/tenants/{tid}/agents")
def list_installed_agents(tid: str) -> dict[str, list[dict[str, Any]]]:
    agents_dir = _agents_dir(tid)
    usage = _usage_by_role(tid)
    rows = [
        _installed_agent_dict(slug, path, usage)
        for slug, path in _installed_bundles(agents_dir).items()
    ]
    rows.sort(key=lambda r: float(r["installed_at"]), reverse=True)
    return {"agents": rows}


@router.post("/tenants/{tid}/agents/{slug}", status_code=status.HTTP_201_CREATED)
def install_agent(tid: str, slug: str, body: AgentInstall | None = None) -> dict[str, Any]:
    entry = _catalog_entry(slug)
    if entry is None:
        raise HTTPException(404, f"agent {slug!r} not in catalog")
    if not entry.get("available", True):
        raise HTTPException(409, f"agent {slug!r} is not yet available")

    # v1: catalog agents are the local bundles shipped with the package —
    # no tarball fetch yet.
    from microagents import SKILLS_DIR
    src = SKILLS_DIR / slug
    if not (src / "skill.toml").exists() or not (src / "prompt.md").exists():
        raise HTTPException(409, f"agent {slug!r} has no local bundle source")

    version = (body.version if body else None) or str(entry.get("version") or "0.0.0")
    agents_dir = _agents_dir(tid)
    dest = agents_dir / f"{slug}@{version}"
    shutil.copytree(src, dest, dirs_exist_ok=True)
    # Reinstall re-enables.
    (dest / "disabled").unlink(missing_ok=True)

    config = dict(entry.get("default_config") or {})
    if body and body.config:
        config.update(body.config)
    (dest / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    _touch_reload(agents_dir)
    return _installed_agent_dict(slug, dest, _usage_by_role(tid))


@router.patch("/tenants/{tid}/agents/{slug}")
def patch_agent(tid: str, slug: str, body: AgentPatch) -> dict[str, Any]:
    agents_dir = _agents_dir(tid)
    bundle_dir = _installed_bundles(agents_dir).get(slug)
    if bundle_dir is None:
        raise HTTPException(404, f"agent {slug!r} not installed")

    if body.enabled is not None:
        marker = bundle_dir / "disabled"
        if body.enabled:
            marker.unlink(missing_ok=True)
        else:
            marker.touch()
    if body.config is not None:
        merged = {**_read_config(bundle_dir), **body.config}
        (bundle_dir / "config.json").write_text(json.dumps(merged, indent=2), encoding="utf-8")
    _touch_reload(agents_dir)
    return _installed_agent_dict(slug, bundle_dir, _usage_by_role(tid))


@router.delete("/tenants/{tid}/agents/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def uninstall_agent(tid: str, slug: str) -> None:
    agents_dir = _agents_dir(tid)
    victims = [
        d for d in agents_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name.rpartition("@")[0] == slug
    ] if agents_dir.is_dir() else []
    if not victims:
        raise HTTPException(404, f"agent {slug!r} not installed")

    trash = agents_dir / ".trash"
    trash.mkdir(exist_ok=True)
    for d in victims:
        dest = trash / d.name
        if dest.exists():
            dest = trash / f"{d.name}-{int(time.time() * 1000)}"
        shutil.move(str(d), str(dest))
    _touch_reload(agents_dir)
