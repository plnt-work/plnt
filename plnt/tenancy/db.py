"""Per-tenant SQLite: sessions, the durable event log, and usage.

One database file per tenant (`<tenant>/data.db`) — a tenant's conversations
and spend never share a table with another tenant's.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    bundle TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle'
);
CREATE TABLE IF NOT EXISTS events (
    session_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    ts REAL NOT NULL,
    run_id TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (session_id, seq)
);
CREATE TABLE IF NOT EXISTS usage (
    ts REAL NOT NULL,
    session_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    bundle TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL
);
"""

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


class TenantDB:
    def __init__(self, path: Path):
        self.path = path
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(str(path), threading.Lock())
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    # ------------------------------------------------------------ sessions

    def create_session(self, bundle: str, user_id: str = "") -> str:
        sid = "s_" + uuid.uuid4().hex[:16]
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO sessions (id, bundle, user_id, created_at) VALUES (?,?,?,?)",
                (sid, bundle, user_id, time.time()),
            )
        return sid

    def session(self, sid: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        return dict(row) if row else None

    def sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def set_status(self, sid: str, status: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, sid))

    # ------------------------------------------------------------ events

    def append(self, sid: str, kind: str, payload: dict[str, Any], run_id: str = "") -> int:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM events WHERE session_id = ?", (sid,)
            ).fetchone()
            seq = int(row[0]) + 1
            c.execute(
                "INSERT INTO events (session_id, seq, ts, run_id, kind, payload) "
                "VALUES (?,?,?,?,?,?)",
                (sid, seq, time.time(), run_id, kind, json.dumps(payload, default=str)),
            )
        return seq

    def events_since(self, sid: str, after: int = 0, limit: int = 1000) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT seq, ts, run_id, kind, payload FROM events "
                "WHERE session_id = ? AND seq > ? ORDER BY seq LIMIT ?",
                (sid, after, limit),
            ).fetchall()
        return [
            {
                "seq": r["seq"],
                "ts": r["ts"],
                "run_id": r["run_id"],
                "kind": r["kind"],
                "payload": json.loads(r["payload"]),
            }
            for r in rows
        ]

    def history(self, sid: str) -> list[dict[str, Any]]:
        """Chat history (user + assistant turns) for building the next prompt."""
        msgs = []
        for e in self.events_since(sid, 0, limit=100_000):
            if e["kind"] == "user_message":
                msgs.append({"role": "user", "content": e["payload"]["text"]})
            elif e["kind"] == "assistant_message":
                msgs.append({"role": "assistant", "content": e["payload"]["text"]})
        return msgs

    # ------------------------------------------------------------ usage

    def record_usage(
        self,
        *,
        session_id: str,
        run_id: str,
        bundle: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO usage VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    time.time(),
                    session_id,
                    run_id,
                    bundle,
                    provider,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                ),
            )

    def usage_summary(self, since: float = 0.0) -> dict[str, Any]:
        with self._conn() as c:
            tot = c.execute(
                "SELECT COUNT(*) calls, COALESCE(SUM(prompt_tokens),0) p, "
                "COALESCE(SUM(completion_tokens),0) o, COALESCE(SUM(cost_usd),0) cost "
                "FROM usage WHERE ts >= ?",
                (since,),
            ).fetchone()
            by = c.execute(
                "SELECT bundle, model, COUNT(*) calls, SUM(prompt_tokens) p, "
                "SUM(completion_tokens) o, SUM(cost_usd) cost FROM usage WHERE ts >= ? "
                "GROUP BY bundle, model ORDER BY cost DESC, p DESC",
                (since,),
            ).fetchall()
        return {
            "model_calls": tot["calls"],
            "prompt_tokens": tot["p"],
            "completion_tokens": tot["o"],
            "cost_usd": round(tot["cost"], 6),
            "by_bundle_model": [
                {
                    "bundle": r["bundle"],
                    "model": r["model"],
                    "model_calls": r["calls"],
                    "prompt_tokens": r["p"],
                    "completion_tokens": r["o"],
                    "cost_usd": round(r["cost"], 6),
                }
                for r in by
            ],
        }
