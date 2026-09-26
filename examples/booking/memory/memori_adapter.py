"""Memori adapter — one instance per tenant on SQL.

Per the design: a tenant's Memori instance is keyed by `tenant_id`; internally
it scopes memory by `entity_id=user_id` and `process_id=skill_role`. We expose
a thin generic interface (`recall`, `remember`) so the rest of plnt-cloud
doesn't depend on Memori's specific shape.

Implementation strategy:
  1. If `memorisdk` is importable AND `PLNT_CLOUD_MEMORY_BACKEND != "stub"`,
     use the real Memori with a SQLite/Postgres backend per tenant.
  2. Otherwise fall back to a SQLite stub that implements the same interface
     by recency. Lets slice-1 run end-to-end without external deps.

The stub is a deliberate first-class citizen — slice 1's verification doesn't
need semantic recall; it needs the partitioning guarantee (tenant A's writes
never appear in tenant B's reads).
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _real_memori_available() -> bool:
    if os.environ.get("PLNT_CLOUD_MEMORY_BACKEND", "").lower() == "stub":
        return False
    try:
        import memori  # noqa: F401
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────── stub backend


class _SqliteStub:
    """Recency-based recall over SQLite. One DB file per tenant.

    Schema is intentionally small — this is the integration point for the
    real Memori, not a memory product in its own right.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            user_id TEXT NOT NULL,
            process_id TEXT NOT NULL,
            session_id TEXT,
            role TEXT NOT NULL,         -- 'user' | 'assistant' | 'system'
            content TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_turns_lookup
            ON turns (user_id, process_id, ts DESC);
    """

    def __init__(self, db_path: Path):
        self._path = db_path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as cx:
            cx.executescript(self._SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        # check_same_thread=False so the lock can guard cross-thread access;
        # the Workflow Activity worker pool uses multiple threads.
        cx = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        cx.execute("PRAGMA journal_mode=WAL")
        cx.execute("PRAGMA synchronous=NORMAL")
        return cx

    def recall(self, *, user_id: str, process_id: str, query: str, k: int) -> list[dict[str, Any]]:
        """Return the k most recent turns for (user_id, process_id).

        `query` is accepted for interface parity with the real Memori; the
        stub ignores it (no vector search). A future swap to real Memori
        passes `query` through unchanged.
        """
        with self._lock, self._connect() as cx:
            rows = cx.execute(
                "SELECT ts, session_id, role, content FROM turns "
                "WHERE user_id = ? AND process_id = ? "
                "ORDER BY ts DESC LIMIT ?",
                (user_id, process_id, int(k)),
            ).fetchall()
        return [
            {"ts": r[0], "session_id": r[1], "role": r[2], "content": r[3]}
            for r in rows
        ]

    def remember(
        self,
        *,
        user_id: str,
        process_id: str,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        with self._lock, self._connect() as cx:
            cx.execute(
                "INSERT INTO turns (ts, user_id, process_id, session_id, role, content) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), user_id, process_id, session_id, role, content),
            )


# ─────────────────────────────────────────────────────────── real backend


class _RealMemori:
    """Thin wrapper over the real `memori` package, exposing the same interface.

    Kept narrow so the rest of plnt-cloud is agnostic. When the real Memori
    matures or its API shifts, only this class needs touching.
    """

    def __init__(self, tenant_id: str, sqlite_path: Path):
        from memori import Memori  # type: ignore

        # Real Memori takes a connection string for BYODB. We use SQLite
        # per tenant in dev; production swaps for `postgresql+psycopg://...`.
        self._mem = Memori(database_url=f"sqlite:///{sqlite_path}")
        self._tenant_id = tenant_id

    def recall(self, *, user_id: str, process_id: str, query: str, k: int) -> list[dict[str, Any]]:
        try:
            return list(self._mem.recall(
                entity_id=user_id,
                process_id=process_id,
                query=query,
                limit=k,
            ))
        except Exception:
            # Memori's API surface may shift; never fail the spawn over a
            # recall miss. Empty context is a valid prompt input.
            return []

    def remember(
        self,
        *,
        user_id: str,
        process_id: str,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        try:
            self._mem.record(
                entity_id=user_id,
                process_id=process_id,
                session_id=session_id,
                role=role,
                content=content,
            )
        except Exception:
            pass


# ─────────────────────────────────────────────────────────── public adapter


@dataclass
class MemoriAdapter:
    """Per-tenant memory handle. Routes to stub or real Memori transparently.

    Construct via `memori_for(tenant_id)`. Do not instantiate directly.
    """

    tenant_id: str
    _backend: Any  # _SqliteStub | _RealMemori (duck-typed: recall / remember)

    def recall(self, *, user_id: str, role: str, query: str = "", k: int = 5) -> list[dict[str, Any]]:
        return self._backend.recall(user_id=user_id, process_id=role, query=query, k=k)

    def remember(
        self,
        *,
        user_id: str,
        role: str,
        session_id: str,
        turn_role: str,
        content: str,
    ) -> None:
        self._backend.remember(
            user_id=user_id,
            process_id=role,
            session_id=session_id,
            role=turn_role,
            content=content,
        )


@lru_cache(maxsize=256)
def memori_for(tenant_id: str, *, home: Path | None = None) -> MemoriAdapter:
    """Cached per-tenant Memori instance. Same instance for the process lifetime."""
    if home is None:
        from tenancy.factory import cloud_home
        home = cloud_home() / "tenants" / tenant_id
    sqlite_path = home / "memori.db"

    if _real_memori_available():
        backend: Any = _RealMemori(tenant_id, sqlite_path)
    else:
        backend = _SqliteStub(sqlite_path)
    return MemoriAdapter(tenant_id=tenant_id, _backend=backend)


def clear_cache() -> None:
    """Drop cached adapters. Test-only."""
    memori_for.cache_clear()
