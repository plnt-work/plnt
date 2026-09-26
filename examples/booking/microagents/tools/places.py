"""places_text_search — Google Places (New) Text Search as a real tool call.

Replaces the post-hoc `_ground_resolve_business` overlay. The model decides
when to call this and what query to use; the result flows back into context
so the model can pick a best_match or ask for disambiguation grounded in
real names, real addresses, real Place IDs.
"""
from __future__ import annotations

from typing import Any

from services import places as places_svc
from tenancy.context import TenantContext

from microagents.tools import Tool, register


_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "Free-text business query, e.g. 'pizza places in Mumbai' "
                "or 'Joey's Pizza Bandra'. Include location words when known."
            ),
        },
        "max_results": {
            "type": "integer",
            "description": "Upper bound on candidates returned (1..10).",
            "minimum": 1,
            "maximum": 10,
        },
    },
    "required": ["query"],
}


def _places_text_search(
    ctx: TenantContext, *, query: str, max_results: int = 5,
) -> dict[str, Any]:
    """Tool body. Returns {candidates, source, enabled}.

    When the Places API is unconfigured we tell the model explicitly via
    `enabled: false` rather than fabricating an answer — the prompt instructs
    it to fall back to its own world knowledge in that case.
    """
    if not places_svc.is_enabled():
        return {"enabled": False, "candidates": [], "source": "disabled"}

    hits = places_svc.search(query, max_results=max(1, min(int(max_results), 10)))
    candidates = [
        {
            "name": p.name,
            "address": p.address,
            "category": (p.types[0] if p.types else ""),
            "place_id": p.place_id,
            "lat": p.latitude,
            "lng": p.longitude,
        }
        for p in hits
    ]
    return {
        "enabled": True,
        "candidates": candidates,
        "source": "google_places",
    }


register(Tool(
    name="places_text_search",
    description=(
        "Search Google Places for real businesses matching a free-text query. "
        "Returns candidates with real names, addresses, lat/lng, and stable "
        "Place IDs. Returns enabled=false when the Places API key is unset; "
        "in that case fall back to your own world knowledge."
    ),
    schema=_SCHEMA,
    fn=_places_text_search,
))
