"""Per-tenant installed-agents registry.

The marketplace of agents (features/agents/registry.ts on the FE) is a
GLOBAL catalogue. This store records which of them a given tenant has
INSTALLED, whether they are enabled, and any per-tenant override config
(threshold values, tone, etc.). Backing the admin v2 endpoints:

    GET    /v1/admin/tenants/:tid/agents
    POST   /v1/admin/tenants/:tid/agents/:slug
    PATCH  /v1/admin/tenants/:tid/agents/:slug
    DELETE /v1/admin/tenants/:tid/agents/:slug
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


_SCHEMA = """
    CREATE TABLE IF NOT EXISTS installed_agents (
        slug                 TEXT PRIMARY KEY,
        enabled              INTEGER NOT NULL DEFAULT 1,
        config               TEXT NOT NULL DEFAULT '{}',
        installed_at         REAL NOT NULL,
        last_used_at         REAL,
        conversation_count   INTEGER NOT NULL DEFAULT 0
    );
"""


@dataclass(frozen=True)
class InstalledAgentRow:
    slug: str
    enabled: bool
    config: dict[str, Any]
    installed_at: float
    last_used_at: float | None
    conversation_count: int


class InstalledAgentsStore:
    def __init__(self, db_path: Path):
        self._path = db_path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as cx:
            cx.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        cx = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        cx.execute("PRAGMA journal_mode=WAL")
        cx.execute("PRAGMA synchronous=NORMAL")
        cx.row_factory = sqlite3.Row
        return cx

    def list(self) -> list[InstalledAgentRow]:
        with self._lock, self._connect() as cx:
            rows = cx.execute(
                "SELECT * FROM installed_agents ORDER BY installed_at DESC",
            ).fetchall()
        return [_row_to_installed(r) for r in rows]

    def get(self, slug: str) -> InstalledAgentRow | None:
        with self._lock, self._connect() as cx:
            row = cx.execute(
                "SELECT * FROM installed_agents WHERE slug = ?", (slug,),
            ).fetchone()
        return _row_to_installed(row) if row else None

    def install(self, slug: str, default_config: dict[str, Any] | None = None) -> InstalledAgentRow:
        cfg_json = json.dumps(default_config or {})
        now = time.time()
        with self._lock, self._connect() as cx:
            cx.execute(
                "INSERT INTO installed_agents (slug, enabled, config, installed_at) "
                "VALUES (?, 1, ?, ?) "
                "ON CONFLICT(slug) DO UPDATE SET enabled=1",
                (slug, cfg_json, now),
            )
            row = cx.execute(
                "SELECT * FROM installed_agents WHERE slug = ?", (slug,),
            ).fetchone()
        return _row_to_installed(row)

    def patch(
        self,
        slug: str,
        *,
        enabled: bool | None = None,
        config: dict[str, Any] | None = None,
    ) -> InstalledAgentRow:
        with self._lock, self._connect() as cx:
            row = cx.execute(
                "SELECT * FROM installed_agents WHERE slug = ?", (slug,),
            ).fetchone()
            if not row:
                raise KeyError(slug)
            new_enabled = int(bool(row["enabled"])) if enabled is None else int(bool(enabled))
            existing_cfg: dict[str, Any] = {}
            try:
                existing_cfg = json.loads(str(row["config"] or "{}"))
            except json.JSONDecodeError:
                existing_cfg = {}
            if config is not None:
                existing_cfg = {**existing_cfg, **config}
            cx.execute(
                "UPDATE installed_agents SET enabled=?, config=? WHERE slug=?",
                (new_enabled, json.dumps(existing_cfg), slug),
            )
            row = cx.execute(
                "SELECT * FROM installed_agents WHERE slug = ?", (slug,),
            ).fetchone()
        return _row_to_installed(row)

    def uninstall(self, slug: str) -> bool:
        with self._lock, self._connect() as cx:
            cur = cx.execute("DELETE FROM installed_agents WHERE slug = ?", (slug,))
            return cur.rowcount > 0

    def mark_used(self, slug: str) -> None:
        try:
            with self._lock, self._connect() as cx:
                cx.execute(
                    "UPDATE installed_agents "
                    "SET last_used_at=?, conversation_count=conversation_count+1 "
                    "WHERE slug=?",
                    (time.time(), slug),
                )
        except sqlite3.DatabaseError:
            pass


def _row_to_installed(r: sqlite3.Row) -> InstalledAgentRow:
    try:
        cfg = json.loads(str(r["config"] or "{}"))
    except json.JSONDecodeError:
        cfg = {}
    return InstalledAgentRow(
        slug=str(r["slug"]),
        enabled=bool(r["enabled"]),
        config=cfg,
        installed_at=float(r["installed_at"]),
        last_used_at=float(r["last_used_at"]) if r["last_used_at"] is not None else None,
        conversation_count=int(r["conversation_count"] or 0),
    )


@lru_cache(maxsize=256)
def installed_agents_for(tenant_id: str) -> InstalledAgentsStore:
    from tenancy.factory import cloud_home
    db_path = cloud_home() / "tenants" / tenant_id / "installed_agents.db"
    return InstalledAgentsStore(db_path)


def clear_cache() -> None:
    installed_agents_for.cache_clear()
