"""Business-owner identity + magic-link auth.

Global (not per-tenant) SQLite table at $PLNT_CLOUD_HOME/owners.db.

Model: an owner has an email. They are associated with one or more
tenant_ids. A magic-link token issued by /v1/auth/magic-link/request
becomes a session on /v1/auth/magic-link/verify. Sessions are opaque
tokens stored server-side with a 7-day TTL.

This is intentionally minimal — no passwords, no OAuth, no email
delivery (the token is returned in the response body in dev; a real
deployment routes it through a mailer). Enough to gate the console
against a real identity.
"""
from __future__ import annotations

import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable


_SCHEMA = """
    CREATE TABLE IF NOT EXISTS owners (
        owner_id    TEXT PRIMARY KEY,
        email       TEXT NOT NULL UNIQUE,
        created_at  REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS owner_tenants (
        owner_id    TEXT NOT NULL,
        tenant_id   TEXT NOT NULL,
        role        TEXT NOT NULL DEFAULT 'owner',
        PRIMARY KEY (owner_id, tenant_id)
    );
    CREATE TABLE IF NOT EXISTS magic_links (
        token       TEXT PRIMARY KEY,
        email       TEXT NOT NULL,
        expires_at  REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
        session_token   TEXT PRIMARY KEY,
        owner_id        TEXT NOT NULL,
        created_at      REAL NOT NULL,
        expires_at      REAL NOT NULL
    );
"""

_MAGIC_LINK_TTL_S = 15 * 60         # 15 minutes
_SESSION_TTL_S = 7 * 24 * 3600      # 7 days


@dataclass(frozen=True)
class Owner:
    owner_id: str
    email: str
    created_at: float
    tenant_ids: list[str]


@dataclass(frozen=True)
class Session:
    session_token: str
    owner_id: str
    expires_at: float


class BusinessOwnersStore:
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

    # ─── owners ────────────────────────────────────────────
    def upsert_owner(self, email: str) -> Owner:
        email = email.strip().lower()
        with self._lock, self._connect() as cx:
            row = cx.execute("SELECT owner_id FROM owners WHERE email = ?", (email,)).fetchone()
            if row:
                owner_id = str(row["owner_id"])
            else:
                owner_id = "own_" + secrets.token_hex(8)
                cx.execute(
                    "INSERT INTO owners (owner_id, email, created_at) VALUES (?, ?, ?)",
                    (owner_id, email, time.time()),
                )
        return self.get_owner(owner_id)  # type: ignore[return-value]

    def get_owner(self, owner_id: str) -> Owner | None:
        with self._lock, self._connect() as cx:
            row = cx.execute("SELECT * FROM owners WHERE owner_id = ?", (owner_id,)).fetchone()
            if not row:
                return None
            tenants = [str(t["tenant_id"]) for t in cx.execute(
                "SELECT tenant_id FROM owner_tenants WHERE owner_id = ?", (owner_id,),
            ).fetchall()]
        return Owner(str(row["owner_id"]), str(row["email"]),
                     float(row["created_at"]), tenants)

    def get_owner_by_email(self, email: str) -> Owner | None:
        email = email.strip().lower()
        with self._lock, self._connect() as cx:
            row = cx.execute("SELECT owner_id FROM owners WHERE email = ?", (email,)).fetchone()
        return self.get_owner(str(row["owner_id"])) if row else None

    def link_tenant(self, owner_id: str, tenant_id: str, role: str = "owner") -> None:
        with self._lock, self._connect() as cx:
            cx.execute(
                "INSERT OR IGNORE INTO owner_tenants (owner_id, tenant_id, role) VALUES (?, ?, ?)",
                (owner_id, tenant_id, role),
            )

    def unlink_tenant(self, owner_id: str, tenant_id: str) -> None:
        with self._lock, self._connect() as cx:
            cx.execute(
                "DELETE FROM owner_tenants WHERE owner_id = ? AND tenant_id = ?",
                (owner_id, tenant_id),
            )

    def list_owners_for_tenant(self, tenant_id: str) -> list[Owner]:
        with self._lock, self._connect() as cx:
            rows = cx.execute(
                "SELECT owner_id FROM owner_tenants WHERE tenant_id = ?", (tenant_id,),
            ).fetchall()
        return [o for o in (self.get_owner(str(r["owner_id"])) for r in rows) if o]

    # ─── magic link ────────────────────────────────────────
    def issue_magic_link(self, email: str) -> str:
        """Create + persist a fresh single-use magic-link token."""
        email = email.strip().lower()
        token = "ml_" + secrets.token_urlsafe(24)
        with self._lock, self._connect() as cx:
            # Purge expired tokens opportunistically to keep the table small.
            cx.execute("DELETE FROM magic_links WHERE expires_at < ?", (time.time(),))
            cx.execute(
                "INSERT INTO magic_links (token, email, expires_at) VALUES (?, ?, ?)",
                (token, email, time.time() + _MAGIC_LINK_TTL_S),
            )
        return token

    def consume_magic_link(self, token: str) -> Owner | None:
        """One-shot: verify+consume a token. Returns the owner (creating on
        first use) or None if invalid/expired."""
        with self._lock, self._connect() as cx:
            row = cx.execute(
                "SELECT email, expires_at FROM magic_links WHERE token = ?", (token,),
            ).fetchone()
            if not row:
                return None
            if float(row["expires_at"]) < time.time():
                cx.execute("DELETE FROM magic_links WHERE token = ?", (token,))
                return None
            email = str(row["email"])
            cx.execute("DELETE FROM magic_links WHERE token = ?", (token,))
        return self.upsert_owner(email)

    # ─── sessions ──────────────────────────────────────────
    def issue_session(self, owner_id: str) -> Session:
        session_token = "sess_" + secrets.token_urlsafe(24)
        expires = time.time() + _SESSION_TTL_S
        with self._lock, self._connect() as cx:
            cx.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
            cx.execute(
                "INSERT INTO sessions (session_token, owner_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (session_token, owner_id, time.time(), expires),
            )
        return Session(session_token, owner_id, expires)

    def resolve_session(self, session_token: str) -> Owner | None:
        with self._lock, self._connect() as cx:
            row = cx.execute(
                "SELECT owner_id, expires_at FROM sessions WHERE session_token = ?",
                (session_token,),
            ).fetchone()
            if not row or float(row["expires_at"]) < time.time():
                return None
            owner_id = str(row["owner_id"])
        return self.get_owner(owner_id)

    def revoke_session(self, session_token: str) -> None:
        with self._lock, self._connect() as cx:
            cx.execute("DELETE FROM sessions WHERE session_token = ?", (session_token,))


@lru_cache(maxsize=1)
def owners_store() -> BusinessOwnersStore:
    from tenancy.factory import cloud_home
    return BusinessOwnersStore(cloud_home() / "owners.db")


def clear_cache() -> None:
    owners_store.cache_clear()
