"""Record a real parent run on a demo workspace for the site's replay.

    set -a; . gemini.env; set +a          # or point PLNT_LOCAL_URL at Ollama
    python scripts/record_replay.py notes-api "Audit app/store.py ..." > site/src/data/replay-notes-api.json

Runs the parent with the four developer bundles installed, read-only (as the
public playground does), and dumps the session's events verbatim.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from plnt.bundles import catalog
from plnt.executors import LocalExecutor
from plnt.server.playground import DEMO_TENANTS
from plnt.tenancy import TenantStore, installs


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    demo, task = sys.argv[1], " ".join(sys.argv[2:])
    spec = next(t for t in DEMO_TENANTS if t["id"] == demo)
    store = TenantStore(Path(tempfile.mkdtemp(prefix="plnt-replay-")) / "tenants")
    tenant, _ = store.create(spec["id"], spec["name"])
    bundles, _ = catalog.available()
    for slug, cfg in spec["installs"].items():
        installs.install(tenant, bundles[slug], cfg)
    ex = LocalExecutor(store, dynamic_roles=True, read_only=True)
    sid = ex.start_session(spec["id"], "", user_id="replay", workspace=spec["workspace"])
    ex.send(spec["id"], sid, task, wait=True)
    events = ex.events_since(spec["id"], sid)
    started = next(e for e in events if e["kind"] == "run_started")
    out = {
        "workspace": spec["workspace"].removeprefix("demo:"),
        "model": started["payload"]["model"]["model"],
        "recorded_at": events[0]["ts"],
        "events": events,
    }
    json.dump(out, sys.stdout, indent=1)
    ok = events[-1]["payload"].get("outcome") == "ok"
    print(f"\n{len(events)} events, outcome {events[-1]['payload'].get('outcome')}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
