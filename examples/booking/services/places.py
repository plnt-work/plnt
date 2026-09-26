"""Google Places API (New) Text Search — real business data for resolve_business.

Activates automatically when the env var `PLNT_CLOUD_PLACES_KEY` is set
(falls back to `PLNT_CLOUD_API_KEY` since the same Google API key works for
both Gemini and Places when both are enabled on the project).

Caching strategy (TOS-aligned):
  * Place IDs may be stored indefinitely.
  * Place Details: 30 days max.

We cache the full text-search result for 30 days, keyed by the normalized
query. SQLite-backed, shared across tenants (place data is public).

Public API:
  is_enabled()                  → True when PLACES_KEY is set
  search(query, max_results=5)  → list[PlaceResult] | [] (empty on error)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx


PLACES_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
# Field mask drives BILLING tier. Stay in "Essentials" (cheapest) by only
# requesting basic fields. Pro fields (rating, opening hours, reviews) add
# ~3× cost — opt in per skill when worth it.
ESSENTIAL_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.location,places.types"
)
CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 days


def _places_key() -> str:
    return (
        os.environ.get("PLNT_CLOUD_PLACES_KEY")
        or os.environ.get("PLNT_CLOUD_API_KEY")
        or ""
    )


def is_enabled() -> bool:
    return bool(_places_key())


@dataclass(frozen=True)
class PlaceResult:
    place_id: str
    name: str
    address: str
    latitude: float
    longitude: float
    types: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────── cache


_CACHE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS text_search (
        query_norm  TEXT PRIMARY KEY,
        fetched_at  REAL NOT NULL,
        results_json TEXT NOT NULL
    );
"""


def _cache_path() -> Path:
    from tenancy.factory import cloud_home
    p = cloud_home() / "places_cache.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


_db_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    cx = sqlite3.connect(str(_cache_path()), check_same_thread=False, isolation_level=None)
    cx.execute("PRAGMA journal_mode=WAL")
    cx.execute("PRAGMA synchronous=NORMAL")
    cx.executescript(_CACHE_SCHEMA)
    return cx


def _norm(query: str) -> str:
    return " ".join(query.lower().strip().split())


def _cache_get(query: str) -> list[PlaceResult] | None:
    with _db_lock, _connect() as cx:
        row = cx.execute(
            "SELECT fetched_at, results_json FROM text_search WHERE query_norm = ?",
            (_norm(query),),
        ).fetchone()
    if not row:
        return None
    fetched_at, results_json = row
    if time.time() - float(fetched_at) > CACHE_TTL_SECONDS:
        return None
    try:
        data = json.loads(results_json)
    except json.JSONDecodeError:
        return None
    return [PlaceResult(**r) for r in data]


def _cache_put(query: str, results: list[PlaceResult]) -> None:
    payload = json.dumps([r.to_dict() for r in results])
    with _db_lock, _connect() as cx:
        cx.execute(
            "INSERT OR REPLACE INTO text_search (query_norm, fetched_at, results_json) "
            "VALUES (?, ?, ?)",
            (_norm(query), time.time(), payload),
        )


def cache_stats() -> dict[str, int]:
    """Used by admin metrics to surface cache hit ratio over time."""
    try:
        with _db_lock, _connect() as cx:
            n = cx.execute("SELECT COUNT(*) FROM text_search").fetchone()[0]
        return {"text_search_rows": int(n)}
    except sqlite3.DatabaseError:
        return {"text_search_rows": 0}


# ─────────────────────────────────────────────────── HTTP


def _do_request(query: str, max_results: int) -> list[PlaceResult]:
    """Synchronous HTTP — the Activity is async but the underlying network
    call is short and httpx.Client is fine in a worker thread."""
    key = _places_key()
    if not key:
        return []
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": ESSENTIAL_FIELD_MASK,
    }
    body = {"textQuery": query, "maxResultCount": int(max_results)}
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(PLACES_ENDPOINT, json=body, headers=headers)
    except httpx.HTTPError:
        return []
    if r.status_code != 200:
        # 403 = API not enabled, 401 = bad key, 429 = rate-limited.
        # Caller falls back to Gemini-derived candidates silently.
        return []
    payload = r.json()
    out: list[PlaceResult] = []
    for p in payload.get("places", []):
        loc = p.get("location") or {}
        out.append(PlaceResult(
            place_id=str(p.get("id") or ""),
            name=str((p.get("displayName") or {}).get("text") or ""),
            address=str(p.get("formattedAddress") or ""),
            latitude=float(loc.get("latitude") or 0.0),
            longitude=float(loc.get("longitude") or 0.0),
            types=list(p.get("types") or []),
        ))
    return out


# ─────────────────────────────────────────────────── public


def search(query: str, *, max_results: int = 5) -> list[PlaceResult]:
    """Cached Places Text Search. Returns [] when disabled, errored,
    or rate-limited — caller falls back to Gemini knowledge."""
    if not query.strip() or not is_enabled():
        return []
    cached = _cache_get(query)
    if cached is not None:
        return cached
    results = _do_request(query, max_results)
    if results:
        _cache_put(query, results)
    return results


@lru_cache(maxsize=1)
def availability_summary() -> str:
    """One-line description used by the admin /health endpoint and the
    skill's prompt prefix so the LLM knows whether to trust Places-grounded
    candidates or fall back to its own world knowledge."""
    return "Places API enabled" if is_enabled() else "Places API disabled (using LLM knowledge)"
