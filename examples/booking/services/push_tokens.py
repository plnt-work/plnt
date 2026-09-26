"""Per-tenant Expo push-token store.

Mobile registers on boot: POST /v1/push/register with {tenant_id, user_id,
expo_token, platform}. Booking saga's notify step looks up the token by
(tenant_id, user_id) and dispatches through the Expo push API.

SQLite per tenant, keyed by user_id so re-registers overwrite. Stores the
platform + last_seen for debugging.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


_SCHEMA = """
    CREATE TABLE IF NOT EXISTS push_tokens (
        user_id     TEXT PRIMARY KEY,
        expo_token  TEXT NOT NULL,
        platform    TEXT NOT NULL DEFAULT 'unknown',
        updated_at  REAL NOT NULL
    );
"""


@dataclass(frozen=True)
class PushToken:
    user_id: str
    expo_token: str
    platform: str
    updated_at: float


class PushTokenStore:
    def __init__(self, db_path: Path):
        self._path = db_path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as cx:
            cx.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        cx = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        cx.execute("PRAGMA journal_mode=WAL")
        cx.row_factory = sqlite3.Row
        return cx

    def upsert(self, *, user_id: str, expo_token: str, platform: str = "unknown") -> PushToken:
        with self._lock, self._connect() as cx:
            cx.execute(
                "INSERT INTO push_tokens (user_id, expo_token, platform, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "  expo_token=excluded.expo_token, platform=excluded.platform, "
                "  updated_at=excluded.updated_at",
                (user_id, expo_token, platform, time.time()),
            )
        return PushToken(user_id, expo_token, platform, time.time())

    def get(self, user_id: str) -> PushToken | None:
        with self._lock, self._connect() as cx:
            row = cx.execute(
                "SELECT * FROM push_tokens WHERE user_id = ?", (user_id,),
            ).fetchone()
        if not row:
            return None
        return PushToken(
            user_id=str(row["user_id"]),
            expo_token=str(row["expo_token"]),
            platform=str(row["platform"] or "unknown"),
            updated_at=float(row["updated_at"]),
        )

    def delete(self, user_id: str) -> bool:
        with self._lock, self._connect() as cx:
            cur = cx.execute("DELETE FROM push_tokens WHERE user_id = ?", (user_id,))
            return cur.rowcount > 0

    def list_all(self) -> list[PushToken]:
        with self._lock, self._connect() as cx:
            rows = cx.execute("SELECT * FROM push_tokens ORDER BY updated_at DESC").fetchall()
        return [PushToken(
            user_id=str(r["user_id"]), expo_token=str(r["expo_token"]),
            platform=str(r["platform"] or "unknown"),
            updated_at=float(r["updated_at"]),
        ) for r in rows]


@lru_cache(maxsize=256)
def push_tokens_for(tenant_id: str) -> PushTokenStore:
    from tenancy.factory import cloud_home
    db_path = cloud_home() / "tenants" / tenant_id / "push_tokens.db"
    return PushTokenStore(db_path)


def clear_cache() -> None:
    push_tokens_for.cache_clear()
