"""Per-tenant merchant notification feed — notifications.jsonl.

Same append-only JSONL pattern as tenancy/audit.py, but writes RAISE on
failure: the saga treats a lost notification as a notify failure.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any


_FILE_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_LOCK = threading.Lock()


def _feed_path(tenant_id: str) -> Path:
    from tenancy.factory import cloud_home
    p = cloud_home() / "tenants" / tenant_id / "notifications.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _lock_for(tenant_id: str) -> threading.Lock:
    with _LOCKS_LOCK:
        lock = _FILE_LOCKS.get(tenant_id)
        if lock is None:
            lock = threading.Lock()
            _FILE_LOCKS[tenant_id] = lock
        return lock


def notification_id(booking_id: str, kind: str) -> str:
    """Deterministic id — Temporal activity retries map to the same entry."""
    return "ntf_" + hashlib.sha1(f"{booking_id}:{kind}".encode()).hexdigest()[:12]


def append(
    tenant_id: str,
    kind: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Append one feed entry; returns (entry, created).

    Idempotent on id derived from (data["booking_id"], kind) — a retry
    after a successful write returns the existing entry with created=False.
    """
    if not tenant_id:
        raise ValueError("append: tenant_id required")
    data = dict(data or {})
    booking_id = str(data.get("booking_id") or "")
    nid = notification_id(booking_id, kind) if booking_id else (
        "ntf_" + hashlib.sha1(f"{time.time_ns()}:{kind}".encode()).hexdigest()[:12]
    )
    with _lock_for(tenant_id):
        existing = {e["id"]: e for e in _read(tenant_id)}
        if nid in existing:
            return existing[nid], False
        entry: dict[str, Any] = {
            "id": nid,
            "ts": time.time(),
            "kind": kind,
            "title": title,
            "body": body,
            "data": data,
            "read": False,
        }
        with _feed_path(tenant_id).open("a") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()
        return entry, True


def _read(tenant_id: str) -> list[dict[str, Any]]:
    path = _feed_path(tenant_id)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(evt, dict) and evt.get("id"):
                out.append(evt)
    return out


def list_notifications(
    tenant_id: str,
    limit: int | None = None,
    unread_only: bool = False,
) -> list[dict[str, Any]]:
    """Feed entries newest-first, optionally unread-only / limited."""
    entries = sorted(_read(tenant_id), key=lambda e: float(e.get("ts") or 0), reverse=True)
    if unread_only:
        entries = [e for e in entries if not e.get("read")]
    if limit is not None:
        entries = entries[:limit]
    return entries


def unread_count(tenant_id: str) -> int:
    return sum(1 for e in _read(tenant_id) if not e.get("read"))


def mark_read(tenant_id: str, ids: list[str]) -> int:
    """Flip read=True for the given ids; rewrites the file. Returns updated count."""
    wanted = set(ids)
    updated = 0
    with _lock_for(tenant_id):
        entries = _read(tenant_id)
        for e in entries:
            if e["id"] in wanted and not e.get("read"):
                e["read"] = True
                updated += 1
        if updated:
            path = _feed_path(tenant_id)
            tmp = path.with_suffix(".jsonl.tmp")
            with tmp.open("w") as f:
                for e in entries:
                    f.write(json.dumps(e) + "\n")
            tmp.replace(path)
    return updated
