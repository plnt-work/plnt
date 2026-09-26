"""Tenant-scoped audit log — one JSONL file per tenant.

Every micro-agent Activity call appends a line. The admin metrics endpoint
reads back from this file to produce conversation/role/last-activity stats
without consulting Temporal (which can be slow at query time and isn't
guaranteed to be reachable from the surface).

Format: one JSON object per line, fields:
  ts          float, epoch seconds
  session_id  string
  user_id     string
  role        string  — micro-agent role
  status      "ok" | "error"
  has_output  bool    — did the activity produce non-empty output
  detail      optional short string (error message, etc.)

Append-only, thread-safe (file-level lock per process). Production swaps
the backend for Loki / CloudWatch / etc. behind the same write_event API.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


_FILE_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_LOCK = threading.Lock()


def _audit_path(tenant_id: str) -> Path:
    from tenancy.factory import cloud_home
    p = cloud_home() / "tenants" / tenant_id / "audit.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _lock_for(tenant_id: str) -> threading.Lock:
    with _LOCKS_LOCK:
        lock = _FILE_LOCKS.get(tenant_id)
        if lock is None:
            lock = threading.Lock()
            _FILE_LOCKS[tenant_id] = lock
        return lock


def write_event(
    *,
    tenant_id: str,
    session_id: str,
    user_id: str,
    role: str,
    status: str = "ok",
    has_output: bool = True,
    detail: str | None = None,
) -> None:
    """Append one audit event. Never raises (audit must not break the spawn)."""
    if not tenant_id:
        return
    evt: dict[str, Any] = {
        "ts": time.time(),
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "status": status,
        "has_output": bool(has_output),
    }
    if detail:
        evt["detail"] = detail[:500]
    try:
        path = _audit_path(tenant_id)
        line = json.dumps(evt) + "\n"
        with _lock_for(tenant_id), path.open("a") as f:
            f.write(line)
            f.flush()
    except OSError:
        # Audit failures are silent — the spawn's correctness is more important
        # than perfect logs. A real deployment alerts on persistent OSError.
        pass


def read_events(tenant_id: str) -> list[dict[str, Any]]:
    """Read the entire audit log for a tenant. Used by the admin aggregator."""
    path = _audit_path(tenant_id)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        with path.open() as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out
