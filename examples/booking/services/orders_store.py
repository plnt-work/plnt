"""Per-tenant multi-service order ledger (SQLite).

Sits alongside the single-slot `BookingsStore` (workflows/bookings_store.py).
That store handles the chat-driven single-slot confirm-and-book path; this
store is the Fresha-style multi-service cart path: N services against one
professional in one time slot. Both stores are additive — the older path
still writes through `BookingsStore`.

Same shape contract as `BookingsStore`: idempotency-keyed unique, threading
lock + WAL journal, dataclass row.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


_SCHEMA = """
    CREATE TABLE IF NOT EXISTS orders (
        order_id         TEXT PRIMARY KEY,
        tenant_id        TEXT NOT NULL,
        user_id          TEXT NOT NULL,
        place_id         TEXT NOT NULL,
        venue_name       TEXT NOT NULL,
        date             TEXT NOT NULL,
        slot             TEXT NOT NULL,
        pro_id           TEXT NOT NULL,
        total_cents      INTEGER NOT NULL,
        status           TEXT NOT NULL,
        created_at       REAL NOT NULL,
        cancelled_at     REAL,
        cancel_reason    TEXT,
        provider         TEXT,
        provider_ref     TEXT,
        idempotency_key  TEXT NOT NULL UNIQUE
    );
    CREATE TABLE IF NOT EXISTS order_items (
        order_id        TEXT NOT NULL,
        service_id      TEXT NOT NULL,
        service_name    TEXT NOT NULL,
        duration_min    INTEGER NOT NULL,
        price_cents     INTEGER NOT NULL,
        PRIMARY KEY (order_id, service_id)
    );
    CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
    CREATE INDEX IF NOT EXISTS idx_orders_idem ON orders(idempotency_key);
"""


@dataclass(frozen=True)
class Order:
    order_id: str
    tenant_id: str
    user_id: str
    place_id: str
    venue_name: str
    date: str
    slot: str
    pro_id: str
    services: list[dict]
    total_cents: int
    status: str
    created_at: float
    cancelled_at: float | None
    cancel_reason: str | None
    provider: str | None
    provider_ref: str | None
    idempotency_key: str


class OrdersStore:
    """SQLite-backed multi-service order ledger for one tenant."""

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

    def create_order(
        self,
        *,
        tenant_id: str,
        user_id: str,
        place_id: str,
        venue_name: str,
        date: str,
        slot: str,
        pro_id: str,
        services: list[dict],
        idempotency_key: str,
        provider: str = "local",
        provider_ref: str = "",
    ) -> Order:
        order_id = "ord_" + hashlib.sha1(idempotency_key.encode()).hexdigest()[:12]
        total_cents = int(sum(int(s.get("price_cents") or 0) for s in services))
        now = time.time()

        with self._lock, self._connect() as cx:
            row = cx.execute(
                "SELECT order_id FROM orders WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row:
                existing = self._get_locked(cx, str(row["order_id"]))
                if existing is not None:
                    return existing

            cx.execute(
                "INSERT INTO orders "
                "(order_id, tenant_id, user_id, place_id, venue_name, date, slot, pro_id, "
                " total_cents, status, created_at, cancelled_at, cancel_reason, provider, "
                " provider_ref, idempotency_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, NULL, NULL, ?, ?, ?)",
                (
                    order_id, tenant_id, user_id, place_id, venue_name, date, slot, pro_id,
                    total_cents, now, provider, provider_ref, idempotency_key,
                ),
            )
            for s in services:
                cx.execute(
                    "INSERT OR IGNORE INTO order_items "
                    "(order_id, service_id, service_name, duration_min, price_cents) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        order_id,
                        str(s.get("id") or ""),
                        str(s.get("name") or ""),
                        int(s.get("duration_min") or 0),
                        int(s.get("price_cents") or 0),
                    ),
                )
            fresh = self._get_locked(cx, order_id)
        assert fresh is not None
        return fresh

    # ------------------------------------------------------ read

    def get_order(self, order_id: str) -> Order | None:
        with self._lock, self._connect() as cx:
            return self._get_locked(cx, order_id)

    def _get_locked(self, cx: sqlite3.Connection, order_id: str) -> Order | None:
        row = cx.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,),
        ).fetchone()
        if not row:
            return None
        items = cx.execute(
            "SELECT service_id, service_name, duration_min, price_cents "
            "FROM order_items WHERE order_id = ?",
            (order_id,),
        ).fetchall()
        return _row_to_order(row, items)

    def list_for_user(self, user_id: str) -> list[Order]:
        with self._lock, self._connect() as cx:
            rows = cx.execute(
                "SELECT order_id FROM orders WHERE user_id = ? "
                "ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [o for o in (self._get_locked(cx, str(r["order_id"])) for r in rows) if o]

    def list_all(
        self,
        status: str | None = None,
        user_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> tuple[list[Order], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if since is not None:
            clauses.append("created_at >= ?")
            params.append(float(since))
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        with self._lock, self._connect() as cx:
            total = int(cx.execute(
                f"SELECT COUNT(*) AS n FROM orders{where}", tuple(params),
            ).fetchone()["n"])
            sql = f"SELECT order_id FROM orders{where} ORDER BY created_at DESC"
            if limit is not None:
                sql += " LIMIT ?"
                params = [*params, int(limit)]
            rows = cx.execute(sql, tuple(params)).fetchall()
            orders = [o for o in (self._get_locked(cx, str(r["order_id"])) for r in rows) if o]
        return orders, total

    # ------------------------------------------------------ cancel

    def cancel(self, order_id: str, reason: str) -> str:
        with self._lock, self._connect() as cx:
            row = cx.execute(
                "SELECT status FROM orders WHERE order_id = ?", (order_id,),
            ).fetchone()
            if not row:
                return "not_found"
            if str(row["status"]) == "cancelled":
                return "already_cancelled"
            cx.execute(
                "UPDATE orders SET status='cancelled', cancelled_at=?, cancel_reason=? "
                "WHERE order_id = ?",
                (time.time(), reason, order_id),
            )
            return "cancelled"

    # ------------------------------------------------------ stats

    def count_by_status(self) -> dict[str, int]:
        with self._lock, self._connect() as cx:
            rows = cx.execute(
                "SELECT status, COUNT(*) AS n FROM orders GROUP BY status",
            ).fetchall()
        return {str(r["status"]): int(r["n"]) for r in rows}


def _row_to_order(r: sqlite3.Row, item_rows: list[sqlite3.Row]) -> Order:
    services = [
        {
            "id": str(i["service_id"]),
            "name": str(i["service_name"]),
            "duration_min": int(i["duration_min"]),
            "price_cents": int(i["price_cents"]),
        }
        for i in item_rows
    ]
    return Order(
        order_id=str(r["order_id"]),
        tenant_id=str(r["tenant_id"]),
        user_id=str(r["user_id"]),
        place_id=str(r["place_id"]),
        venue_name=str(r["venue_name"]),
        date=str(r["date"]),
        slot=str(r["slot"]),
        pro_id=str(r["pro_id"]),
        services=services,
        total_cents=int(r["total_cents"]),
        status=str(r["status"]),
        created_at=float(r["created_at"]),
        cancelled_at=float(r["cancelled_at"]) if r["cancelled_at"] is not None else None,
        cancel_reason=str(r["cancel_reason"]) if r["cancel_reason"] is not None else None,
        provider=str(r["provider"]) if r["provider"] is not None else None,
        provider_ref=str(r["provider_ref"]) if r["provider_ref"] is not None else None,
        idempotency_key=str(r["idempotency_key"]),
    )


def order_to_dict(o: Order) -> dict[str, Any]:
    """JSON-safe dict view — used at the Activity boundary."""
    return {
        "order_id": o.order_id,
        "tenant_id": o.tenant_id,
        "user_id": o.user_id,
        "place_id": o.place_id,
        "venue_name": o.venue_name,
        "date": o.date,
        "slot": o.slot,
        "pro_id": o.pro_id,
        "services": list(o.services),
        "total_cents": o.total_cents,
        "status": o.status,
        "created_at": o.created_at,
        "cancelled_at": o.cancelled_at,
        "cancel_reason": o.cancel_reason,
        "provider": o.provider,
        "provider_ref": o.provider_ref,
        "idempotency_key": o.idempotency_key,
    }


@lru_cache(maxsize=256)
def orders_for(tenant_id: str) -> OrdersStore:
    from tenancy.factory import cloud_home
    db_path = cloud_home() / "tenants" / tenant_id / "orders.db"
    return OrdersStore(db_path)


def clear_cache() -> None:
    orders_for.cache_clear()


# json import kept for callers that want to serialise ad-hoc.
_ = json
