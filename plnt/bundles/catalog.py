"""Where installable bundles come from.

Search path, first match wins per slug:
  1. $PLNT_BUNDLE_PATH (colon-separated directories of bundles)
  2. `registry/bundles/` and `skills/` next to the plnt package (source checkout)
  3. `plnt/_bundles/`: registry/bundles copied into the wheel at build time

The hosted registry with sha256-verified downloads is roadmap Phase 5.
"""

from __future__ import annotations

import os
from pathlib import Path

from plnt.bundles.bundle import Bundle, BundleError, load_bundle

_REPO = Path(__file__).resolve().parents[2]
_PACKAGED = Path(__file__).resolve().parents[1] / "_bundles"


def search_path() -> list[Path]:
    dirs = [Path(p).expanduser() for p in os.environ.get("PLNT_BUNDLE_PATH", "").split(":") if p]
    dirs += [_REPO / "registry" / "bundles", _REPO / "skills", _PACKAGED]
    return [d for d in dirs if d.is_dir()]


def available() -> tuple[dict[str, Bundle], dict[str, str]]:
    """All loadable bundles by slug, plus {dir: error} for ones that failed to load."""
    found: dict[str, Bundle] = {}
    errors: dict[str, str] = {}
    for root in search_path():
        for d in sorted(p for p in root.iterdir() if (p / "skill.toml").is_file()):
            try:
                b = load_bundle(d)
            except BundleError as e:
                errors[str(d)] = str(e)
                continue
            found.setdefault(b.slug, b)
    return found, errors


def resolve(source: str) -> Bundle:
    """A bundle directory path, or a slug from the search path."""
    p = Path(source).expanduser()
    if p.is_dir():
        return load_bundle(p)
    bundles, _ = available()
    if source in bundles:
        return bundles[source]
    raise BundleError(
        f"no bundle {source!r}: not a directory and not in the catalog "
        f"({', '.join(sorted(bundles)) or 'empty'})"
    )
