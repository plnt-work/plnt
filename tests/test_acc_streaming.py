"""Streaming ACC: runaway agents die while running, not on post-hoc replay."""

from __future__ import annotations

import sys
import time

from plnt.control.acc import ACCMonitor
from plnt.control.orchestrator import Orchestrator
from plnt.control.skills import SkillRegistry
from plnt.execution.blackboard import Blackboard
from plnt.execution.sandbox.process import ProcessSandbox
from plnt.execution.spec import AgentSpec, Budget

# Fake runner: reads the spec envelope, then emits the identical tool_call
# forever. Without a live kill it would burn the whole wall budget.
_LOOPING_RUNNER = [
    sys.executable,
    "-c",
    (
        "import json, sys, time\n"
        "sys.stdin.readline()\n"
        "evt = json.dumps({'kind': 'tool_call', "
        "'payload': {'tool': 'search', 'args': {'pattern': 'x'}}})\n"
        "while True:\n"
        "    print(evt, flush=True)\n"
        "    time.sleep(0.02)\n"
    ),
]


def _force_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_REQUIRED_PATH", str(tmp_path / "never-exists"))
    monkeypatch.delenv("PLNT_CLOUD_URL", raising=False)
    monkeypatch.delenv("PLNT_CLOUD_API_KEY", raising=False)
    monkeypatch.setenv("PLNT_LOCAL_URL", "http://127.0.0.1:1")


def test_sandbox_on_event_feeds_acc_and_kills_under_3s(isolated_home):
    bb = Blackboard("r-acc-kill")
    sandbox = ProcessSandbox(bb, runner_cmd=_LOOPING_RUNNER)
    acc = ACCMonitor(kill_fn=sandbox.kill)
    spec = AgentSpec(
        role="x",
        run_id="r-acc-kill",
        inputs={},
        budget=Budget(wall_seconds=30),
    )
    started = time.monotonic()
    result = sandbox.run(spec, on_event=acc.observe)
    elapsed = time.monotonic() - started

    assert elapsed < 3, f"streaming kill should land in ms, took {elapsed:.1f}s"
    assert result.killed
    assert result.kill_reason.startswith("ACC:loop")
    killed = [e for e in bb.read_all() if e["kind"] == "killed"]
    assert killed and "ACC:loop" in killed[0]["payload"]["reason"]


def test_orchestrator_start_run_kills_runaway_live(isolated_home, monkeypatch):
    def fake_get_sandbox(isolation):
        def make(blackboard):
            return ProcessSandbox(blackboard, runner_cmd=_LOOPING_RUNNER)

        return make

    monkeypatch.setattr("plnt.control.orchestrator.get_sandbox", fake_get_sandbox)

    orch = Orchestrator(skill_registry=SkillRegistry())
    started = time.monotonic()
    handle = orch.start_run("loop forever")
    elapsed = time.monotonic() - started

    assert elapsed < 3, f"orchestrator should kill live, took {elapsed:.1f}s"
    assert handle.result is not None and handle.result.killed
    assert handle.result.kill_reason.startswith("ACC:loop")
    killed = [e for e in handle.blackboard.read_all() if e["kind"] == "killed"]
    assert killed and "ACC:loop" in killed[0]["payload"]["reason"]


def test_normal_short_run_is_not_killed(isolated_home, tmp_path, monkeypatch):
    # Real runner on the offline echo backend — the happy path must not
    # trip the streaming ACC.
    _force_offline(tmp_path, monkeypatch)
    (tmp_path / "src.txt").write_text("plnt streaming acc happy path\n")

    orch = Orchestrator(skill_registry=SkillRegistry())
    handle = orch.start_run(f"find plnt in {tmp_path}")

    assert handle.result is not None
    assert not handle.result.killed
    assert handle.result.exit_code == 0
    assert not [e for e in handle.blackboard.read_all() if e["kind"] == "killed"]
