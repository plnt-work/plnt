"""Per-tenant catalogue store — services, professionals, opening hours.

This is the backing store for the Fresha-style marketplace: each tenant
(business) has a list of bookable Services, a list of Professionals who
can perform them, an OpeningHours schedule, and enough data to compute
real availability slots (not LLM-invented ones).

SQLite per tenant, at $PLNT_CLOUD_HOME/tenants/<tid>/catalogue.db.
Cheap to seed, easy to swap for Postgres later. Same lifetime pattern as
BookingsStore.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
from typing import Any


_SCHEMA = """
    CREATE TABLE IF NOT EXISTS services (
        id            TEXT PRIMARY KEY,
        name          TEXT NOT NULL,
        duration_min  INTEGER NOT NULL,
        price_cents   INTEGER NOT NULL,
        description   TEXT,
        pro_ids       TEXT NOT NULL DEFAULT '[]',   -- JSON array of professional ids; empty = any
        created_at    REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS professionals (
        id         TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        role       TEXT NOT NULL,
        avatar_uri TEXT,
        created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS opening_hours (
        weekday    INTEGER PRIMARY KEY,   -- 0 = Monday .. 6 = Sunday
        open_min   INTEGER NOT NULL,      -- minutes since 00:00 local
        close_min  INTEGER NOT NULL
    );
"""


@dataclass(frozen=True)
class Service:
    id: str
    name: str
    duration_min: int
    price_cents: int
    description: str
    pro_ids: list[str]


@dataclass(frozen=True)
class Professional:
    id: str
    name: str
    role: str
    avatar_uri: str


@dataclass(frozen=True)
class DayHours:
    weekday: int          # 0 Mon .. 6 Sun
    open_min: int         # e.g. 540 = 09:00
    close_min: int        # e.g. 1140 = 19:00


class CatalogueStore:
    """SQLite-backed catalogue for one tenant."""

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

    # ─── services ──────────────────────────────────────────────
    def upsert_service(
        self, *, id: str, name: str, duration_min: int,
        price_cents: int, description: str = "", pro_ids: list[str] | None = None,
    ) -> Service:
        pro_ids = pro_ids or []
        with self._lock, self._connect() as cx:
            cx.execute(
                "INSERT INTO services (id, name, duration_min, price_cents, description, pro_ids, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "  name=excluded.name, duration_min=excluded.duration_min, "
                "  price_cents=excluded.price_cents, description=excluded.description, "
                "  pro_ids=excluded.pro_ids",
                (id, name, int(duration_min), int(price_cents),
                 description, json.dumps(pro_ids), time.time()),
            )
        return Service(id, name, int(duration_min), int(price_cents),
                       description, list(pro_ids))

    def delete_service(self, service_id: str) -> bool:
        with self._lock, self._connect() as cx:
            cur = cx.execute("DELETE FROM services WHERE id = ?", (service_id,))
            return cur.rowcount > 0

    def list_services(self) -> list[Service]:
        with self._lock, self._connect() as cx:
            rows = cx.execute("SELECT * FROM services ORDER BY name").fetchall()
        return [_row_to_service(r) for r in rows]

    def get_service(self, service_id: str) -> Service | None:
        with self._lock, self._connect() as cx:
            row = cx.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        return _row_to_service(row) if row else None

    # ─── professionals ─────────────────────────────────────────
    def upsert_professional(
        self, *, id: str, name: str, role: str = "", avatar_uri: str = "",
    ) -> Professional:
        with self._lock, self._connect() as cx:
            cx.execute(
                "INSERT INTO professionals (id, name, role, avatar_uri, created_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "  name=excluded.name, role=excluded.role, avatar_uri=excluded.avatar_uri",
                (id, name, role, avatar_uri, time.time()),
            )
        return Professional(id, name, role, avatar_uri)

    def delete_professional(self, pro_id: str) -> bool:
        with self._lock, self._connect() as cx:
            cur = cx.execute("DELETE FROM professionals WHERE id = ?", (pro_id,))
            return cur.rowcount > 0

    def list_professionals(self) -> list[Professional]:
        with self._lock, self._connect() as cx:
            rows = cx.execute("SELECT * FROM professionals ORDER BY name").fetchall()
        return [Professional(
            id=str(r["id"]), name=str(r["name"]), role=str(r["role"] or ""),
            avatar_uri=str(r["avatar_uri"] or ""),
        ) for r in rows]

    def get_professional(self, pro_id: str) -> Professional | None:
        with self._lock, self._connect() as cx:
            row = cx.execute("SELECT * FROM professionals WHERE id = ?", (pro_id,)).fetchone()
        if not row:
            return None
        return Professional(
            id=str(row["id"]), name=str(row["name"]),
            role=str(row["role"] or ""), avatar_uri=str(row["avatar_uri"] or ""),
        )

    # ─── opening hours ─────────────────────────────────────────
    def set_hours(self, hours: list[DayHours]) -> None:
        with self._lock, self._connect() as cx:
            cx.execute("DELETE FROM opening_hours")
            cx.executemany(
                "INSERT INTO opening_hours (weekday, open_min, close_min) VALUES (?, ?, ?)",
                [(h.weekday, h.open_min, h.close_min) for h in hours],
            )

    def list_hours(self) -> list[DayHours]:
        with self._lock, self._connect() as cx:
            rows = cx.execute("SELECT * FROM opening_hours ORDER BY weekday").fetchall()
        return [DayHours(int(r["weekday"]), int(r["open_min"]), int(r["close_min"])) for r in rows]

    def hours_for(self, weekday: int) -> DayHours | None:
        with self._lock, self._connect() as cx:
            row = cx.execute(
                "SELECT * FROM opening_hours WHERE weekday = ?", (weekday,),
            ).fetchone()
        if not row:
            return None
        return DayHours(int(row["weekday"]), int(row["open_min"]), int(row["close_min"]))


def _row_to_service(r: sqlite3.Row) -> Service:
    try:
        pros = json.loads(r["pro_ids"]) if r["pro_ids"] else []
        pros = [str(x) for x in pros if isinstance(x, (str, int))]
    except json.JSONDecodeError:
        pros = []
    return Service(
        id=str(r["id"]), name=str(r["name"]),
        duration_min=int(r["duration_min"]), price_cents=int(r["price_cents"]),
        description=str(r["description"] or ""), pro_ids=pros,
    )


@lru_cache(maxsize=256)
def catalogue_for(tenant_id: str) -> CatalogueStore:
    from tenancy.factory import cloud_home
    db_path = cloud_home() / "tenants" / tenant_id / "catalogue.db"
    store = CatalogueStore(db_path)
    _maybe_seed(store)
    return store


def clear_cache() -> None:
    catalogue_for.cache_clear()


# ─── availability computation ─────────────────────────────────

def compute_available_slots(
    store: CatalogueStore,
    *,
    date_iso: str,
    service_ids: list[str],
    pro_id: str,
    booked_slots: set[str],
    grid_min: int = 30,
) -> list[str]:
    """Compute real HH:mm slots for a given date, respecting:
    - Opening hours for that weekday
    - Total service duration (needs enough runway before close)
    - Booked slots for this professional on this date (excluded)
    - Optional pro_ids constraint on each service

    Returns HH:mm strings on the `grid_min` grid inside the open window.
    """
    from datetime import date as date_cls
    try:
        y, m, d = date_iso.split("-")
        weekday = date_cls(int(y), int(m), int(d)).weekday()
    except (ValueError, TypeError):
        return []

    hours = store.hours_for(weekday)
    if not hours or hours.open_min >= hours.close_min:
        return []

    # Total duration across selected services; if the professional isn't
    # allowed for any requested service, return empty.
    total_min = 0
    for sid in service_ids:
        s = store.get_service(sid)
        if not s:
            continue
        if pro_id and pro_id != "no-preference" and s.pro_ids and pro_id not in s.pro_ids:
            return []
        total_min += s.duration_min
    if total_min <= 0:
        total_min = grid_min  # nothing selected → single-grid probe

    slots: list[str] = []
    t = hours.open_min
    while t + total_min <= hours.close_min:
        hh = t // 60
        mm = t % 60
        label = f"{hh:02d}:{mm:02d}"
        if label not in booked_slots:
            slots.append(label)
        t += grid_min
    return slots


# ─── dev-time seed ─────────────────────────────────────────────

_DEFAULT_HOURS = [DayHours(w, 9 * 60, 19 * 60) for w in range(7)]


def _maybe_seed(store: CatalogueStore) -> None:
    """Seed a minimal 3-service / 3-pro / 9-19 catalogue when empty.

    Deterministic — reruns are no-ops (upserts are id-keyed and hours
    are set() only when empty). Lets a fresh tenant show usable data
    immediately without every dev running manual admin POSTs.
    """
    if not store.list_hours():
        store.set_hours(_DEFAULT_HOURS)
    if not store.list_professionals():
        store.upsert_professional(id="pro-asha", name="Asha Iyer", role="Lead practitioner")
        store.upsert_professional(id="pro-vikram", name="Vikram Rao", role="Senior associate")
        store.upsert_professional(id="pro-mira", name="Mira Shah", role="Associate")
    if not store.list_services():
        store.upsert_service(id="svc-consult", name="Consultation",
                             duration_min=30, price_cents=5000, pro_ids=[])
        store.upsert_service(id="svc-standard", name="Standard appointment",
                             duration_min=45, price_cents=8000, pro_ids=[])
        store.upsert_service(id="svc-premium", name="Premium appointment",
                             duration_min=60, price_cents=12000,
                             pro_ids=["pro-asha", "pro-vikram"])


def service_to_dict(s: Service) -> dict[str, Any]:
    return asdict(s)


def professional_to_dict(p: Professional) -> dict[str, Any]:
    return asdict(p)


def hours_to_dict(h: DayHours) -> dict[str, Any]:
    return asdict(h)
