"""Backend picker — compatibility view over `plnt.models.resolve_profile`.

Kept for callers that want the (kind, url, model) triple for audit events.
The decision logic lives in `plnt/models/profiles.py`. There is no implicit
"offline" fallback: when nothing is reachable, `choose()` raises
`NoModelConfigured` with a hint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from plnt.models.profiles import resolve_profile

BackendKind = Literal["local", "cloud", "offline"]


@dataclass
class BackendChoice:
    kind: BackendKind
    url: str
    model: str
    api_key: str = ""
    reason: str = ""

    def to_event(self) -> dict:
        # Never write the api_key into events. Audit log stays grep-safe.
        return {"kind": self.kind, "url": self.url, "model": self.model, "reason": self.reason}


def choose(
    *,
    model_hint: Literal["small", "deep", "auto"] = "auto",
    force: Literal["auto", "local", "cloud", "offline"] | None = None,
) -> BackendChoice:
    p = resolve_profile(model_hint, force)
    kind: BackendKind = "offline" if p.provider == "offline" else p.source  # type: ignore[assignment]
    return BackendChoice(kind, p.base_url, p.model, api_key=p.api_key, reason=p.reason)
