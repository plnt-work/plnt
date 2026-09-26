"""Per-tenant booking + idempotency-key store (SQLite).

Two roles:
  1. **Idempotency** — `create_booking` Activity may be retried by Temporal.
     The store maps `idempotency_key` → `booking_id` so a retry sees the
     same booking instead of creating a duplicate.
  2. **Lifecycle ledger** — track booking status so `cancel_booking` (the
     saga compensation step) can recognise already-cancelled bookings and
     return a no-op.

Backend mirrors the Memori adapter: SQLite per tenant in dev, easy to swap
for Postgres in prod. Same `cloud_home()` root.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


_SCHEMA = """
    CREATE TABLE IF NOT EXISTS bookings (
        booking_id        TEXT PRIMARY KEY,
        idempotency_key   TEXT NOT NULL UNIQUE,
        business_id       TEXT NOT NULL,
        slot              TEXT NOT NULL,
        user_contact      TEXT,
        status            TEXT NOT NULL,    -- confirmed | cancelled
        created_at        REAL NOT NULL,
        cancelled_at      REAL,
        cancel_reason     TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_bookings_idem ON bookings(idempotency_key);
"""


@dataclass(frozen=True)
class Booking:
    booking_id: str
    idempotency_key: str
    business_id: str
    slot: str
    user_contact: str
    status: str
    created_at: float
    cancelled_at: float | None
    cancel_reason: str | None


class BookingsStore:
    """SQLite-backed booking ledger for one tenant."""

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

    # ------------------------------------------------------ create

    def upsert_confirmed(
        self,
        *,
        idempotency_key: str,
        booking_id: str,
        business_id: str,
        slot: str,
        user_contact: str,
    ) -> tuple[str, bool]:
        """Insert a confirmed booking, OR return the existing one if the
        idempotency_key was already seen.

        Returns (booking_id, was_inserted).
        """
        with self._lock, self._connect() as cx:
            row = cx.execute(
                "SELECT booking_id FROM bookings WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row:
                return str(row["booking_id"]), False
            cx.execute(
                "INSERT INTO bookings "
                "(booking_id, idempotency_key, business_id, slot, user_contact, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'confirmed', ?)",
                (booking_id, idempotency_key, business_id, slot, user_contact, time.time()),
            )
            return booking_id, True

    # ------------------------------------------------------ cancel

    def cancel(self, booking_id: str, reason: str) -> str:
        """Mark a booking cancelled. Returns one of:
            'cancelled' — was confirmed, now cancelled
            'already_cancelled' — was already cancelled (no-op)
            'not_found' — no such booking
        Compensation step calls this; must be idempotent.
        """
        with self._lock, self._connect() as cx:
            row = cx.execute(
                "SELECT status FROM bookings WHERE booking_id = ?",
                (booking_id,),
            ).fetchone()
            if not row:
                return "not_found"
            if str(row["status"]) == "cancelled":
                return "already_cancelled"
            cx.execute(
                "UPDATE bookings SET status='cancelled', cancelled_at=?, cancel_reason=? "
                "WHERE booking_id = ?",
                (time.time(), reason, booking_id),
            )
            return "cancelled"

    # ------------------------------------------------------ inspect

    def get(self, booking_id: str) -> Booking | None:
        with self._lock, self._connect() as cx:
            row = cx.execute(
                "SELECT * FROM bookings WHERE booking_id = ?", (booking_id,),
            ).fetchone()
        return _row_to_booking(row) if row else None

    def list_all(
        self,
        status: str | None = None,
        user_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> tuple[list[Booking], int]:
        """Filtered listing for the admin surface.

        `user_id` matches `user_contact` — the chat path fills that column
        with the user_id when no explicit contact was given (session.py).
        Returns (rows newest-first, total matching before limit).
        """
        clauses: list[str] = []
        params: list[object] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if user_id:
            clauses.append("user_contact = ?")
            params.append(user_id)
        if since is not None:
            clauses.append("created_at >= ?")
            params.append(float(since))
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        with self._lock, self._connect() as cx:
            total = int(cx.execute(
                f"SELECT COUNT(*) AS n FROM bookings{where}", tuple(params),
            ).fetchone()["n"])
            sql = f"SELECT * FROM bookings{where} ORDER BY created_at DESC"
            if limit is not None:
                sql += " LIMIT ?"
                params = [*params, int(limit)]
            rows = cx.execute(sql, tuple(params)).fetchall()
        return [_row_to_booking(r) for r in rows], total

    def count_by_status(self) -> dict[str, int]:
        with self._lock, self._connect() as cx:
            rows = cx.execute(
                "SELECT status, COUNT(*) AS n FROM bookings GROUP BY status",
            ).fetchall()
        return {str(r["status"]): int(r["n"]) for r in rows}


def _row_to_booking(r: sqlite3.Row) -> Booking:
    return Booking(
        booking_id=str(r["booking_id"]),
        idempotency_key=str(r["idempotency_key"]),
        business_id=str(r["business_id"]),
        slot=str(r["slot"]),
        user_contact=str(r["user_contact"] or ""),
        status=str(r["status"]),
        created_at=float(r["created_at"]),
        cancelled_at=float(r["cancelled_at"]) if r["cancelled_at"] is not None else None,
        cancel_reason=str(r["cancel_reason"]) if r["cancel_reason"] is not None else None,
    )


@lru_cache(maxsize=256)
def bookings_for(tenant_id: str) -> BookingsStore:
    """Per-tenant store, cached process-wide."""
    from tenancy.factory import cloud_home
    db_path = cloud_home() / "tenants" / tenant_id / "bookings.db"
    return BookingsStore(db_path)


def clear_cache() -> None:
    bookings_for.cache_clear()
