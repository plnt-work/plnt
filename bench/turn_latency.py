"""Turn-latency benchmark — plnt runtime overhead absent the model.

Measures wall time from Orchestrator.start_run(intent) to result using the
deterministic offline echo backend, so the number is pure framework overhead
(spawn + sandbox + event plumbing), comparable across commits.

Optionally (--compare-langgraph) runs a minimal two-node LangGraph graph with
a fake model callable and appends its numbers to the same CSV. langgraph is
NOT a dependency; the comparison only runs if it is already importable.

Usage:
  python bench/turn_latency.py [--n 20] [--compare-langgraph]

Results append to bench/results/turn_latency.csv.
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

RESULTS = Path(__file__).parent / "results" / "turn_latency.csv"
FIELDS = ["framework", "timestamp", "n", "p50_ms", "p95_ms", "events_per_run"]


def _percentile(sorted_ms: list[float], q: float) -> float:
    idx = min(len(sorted_ms) - 1, max(0, round(q * (len(sorted_ms) - 1))))
    return sorted_ms[idx]


def _append_row(row: dict) -> None:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    new_file = not RESULTS.exists()
    with open(RESULTS, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerow(row)


def _report(framework: str, samples_ms: list[float], events_per_run: float) -> dict:
    s = sorted(samples_ms)
    row = {
        "framework": framework,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n": len(s),
        "p50_ms": round(_percentile(s, 0.50), 1),
        "p95_ms": round(_percentile(s, 0.95), 1),
        "events_per_run": round(events_per_run, 1),
    }
    _append_row(row)
    print(
        f"{framework}: n={row['n']} p50={row['p50_ms']}ms "
        f"p95={row['p95_ms']}ms events/run={row['events_per_run']}"
    )
    return row


def bench_plnt(n: int) -> None:
    # Force the offline echo backend and box all run state in a tempdir
    # BEFORE any plnt import reads the environment.
    tmp = tempfile.mkdtemp(prefix="plnt-bench-")
    os.environ["PLNT_HOME"] = tmp
    os.environ["PLNT_REQUIRED_PATH"] = str(Path(tmp) / "never-exists")
    os.environ["PLNT_LOCAL_URL"] = "http://127.0.0.1:1"
    os.environ.pop("PLNT_CLOUD_URL", None)
    os.environ.pop("PLNT_CLOUD_API_KEY", None)

    from plnt.config import paths
    from plnt.control.orchestrator import Orchestrator
    from plnt.control.skills import SkillRegistry

    paths().ensure()
    corpus = Path(tmp) / "corpus"
    corpus.mkdir()
    (corpus / "note.txt").write_text("plnt turn latency benchmark corpus\n")

    orch = Orchestrator(skill_registry=SkillRegistry())
    intent = f"find benchmark in {corpus}"

    orch.start_run(intent)  # warmup, unmeasured

    samples_ms: list[float] = []
    event_counts: list[int] = []
    for _ in range(n):
        t0 = time.monotonic()
        handle = orch.start_run(intent)
        samples_ms.append((time.monotonic() - t0) * 1000)
        event_counts.append(len(handle.blackboard.read_all()))

    _report("plnt-offline", samples_ms, statistics.mean(event_counts))


def bench_langgraph(n: int) -> None:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        print("langgraph not importable — skipping comparison (not installed on purpose)")
        return

    from typing import TypedDict

    class State(TypedDict):
        messages: list

    def fake_model(prompt: str) -> str:
        # Deterministic echo, mirroring plnt's offline backend.
        return f"echo: {prompt[:64]}"

    def plan(state: State) -> State:
        return {"messages": state["messages"] + [fake_model(str(state["messages"][-1]))]}

    def act(state: State) -> State:
        return {"messages": state["messages"] + [fake_model("act")]}

    g = StateGraph(State)
    g.add_node("plan", plan)
    g.add_node("act", act)
    g.set_entry_point("plan")
    g.add_edge("plan", "act")
    g.add_edge("act", END)
    graph = g.compile()

    graph.invoke({"messages": ["warmup"]})  # warmup, unmeasured

    samples_ms: list[float] = []
    for _ in range(n):
        t0 = time.monotonic()
        graph.invoke({"messages": ["find benchmark in corpus"]})
        samples_ms.append((time.monotonic() - t0) * 1000)

    # events/run = node executions (2) — the closest analogue to plnt events.
    _report("langgraph-fake-model", samples_ms, 2.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=20, help="measured runs per framework")
    ap.add_argument("--compare-langgraph", action="store_true")
    args = ap.parse_args()

    bench_plnt(args.n)
    if args.compare_langgraph:
        bench_langgraph(args.n)
    print(f"results appended to {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
