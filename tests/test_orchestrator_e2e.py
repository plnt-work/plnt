"""End-to-end: intent -> orchestrator -> sandbox -> result event in the BB."""

from __future__ import annotations

from plnt.control.orchestrator import Orchestrator
from plnt.control.skills import SkillRegistry


def test_e2e_intent_to_result(isolated_home, tmp_path, monkeypatch):
    # Explicitly select the deterministic offline provider so this test is
    # hermetic — no external Ollama / cloud API needed.
    monkeypatch.setenv("PLNT_REQUIRED_PATH", str(tmp_path / "never-exists"))
    monkeypatch.delenv("PLNT_CLOUD_URL", raising=False)
    monkeypatch.delenv("PLNT_CLOUD_API_KEY", raising=False)
    monkeypatch.setenv("PLNT_LOCAL_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("PLNT_FORCE", "offline")

    from plnt.config import paths

    sk_dir = paths().skills
    (sk_dir / "general-helper.md").write_text(
        "---\nmodel_hint: small\ntokens: 5000\nwall_seconds: 30\n---\n"
        "You are the general helper."
    )
    reg = SkillRegistry(sk_dir)

    orch = Orchestrator(skill_registry=reg, runs_root=paths().runs)
    handle = orch.start_run("find agent memory in the source tree")

    events = handle.blackboard.read_all()
    kinds = [e["kind"] for e in events]
    assert "intent" in kinds
    assert "spawn" in kinds
    assert "started" in kinds
    assert "finished" in kinds
    # offline provider -> at least one tool_call event
    assert "tool_call" in kinds


def test_e2e_without_model_reports_error_not_fake_answer(isolated_home, tmp_path, monkeypatch):
    """No model reachable and none forced: the run must say so, loudly."""
    monkeypatch.delenv("PLNT_FORCE", raising=False)
    monkeypatch.delenv("PLNT_CLOUD_URL", raising=False)
    monkeypatch.delenv("PLNT_CLOUD_API_KEY", raising=False)
    monkeypatch.setenv("PLNT_LOCAL_URL", "http://127.0.0.1:1")

    from plnt.config import paths

    sk_dir = paths().skills
    (sk_dir / "general-helper.md").write_text(
        "---\nmodel_hint: small\ntokens: 5000\nwall_seconds: 30\n---\nYou are the general helper."
    )
    orch = Orchestrator(skill_registry=SkillRegistry(sk_dir), runs_root=paths().runs)
    handle = orch.start_run("find agent memory in the source tree")

    events = handle.blackboard.read_all()
    errors = [e for e in events if e["kind"] == "model_error"]
    assert errors, [e["kind"] for e in events]
    assert "ollama" in errors[0]["payload"]["hint"]
    results = [e for e in events if e["kind"] == "result"]
    assert results and "error" in results[0]["payload"]["output"]
    assert "offline stub" not in results[0]["payload"]["output"]["answer"]
