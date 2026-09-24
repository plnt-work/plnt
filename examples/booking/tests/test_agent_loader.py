"""Slice-2 loader tests — per-tenant bundle shadowing of the global catalog."""
from __future__ import annotations

from pathlib import Path

import pytest

from microagents import SKILLS_DIR

ROLE = "classify_intent"


@pytest.fixture()
def loader_env(tmp_path, monkeypatch):
    """Isolated PLNT_CLOUD_HOME with all relevant caches cleared."""
    monkeypatch.setenv("PLNT_CLOUD_HOME", str(tmp_path))
    monkeypatch.setenv("PLNT_CLOUD_MEMORY_BACKEND", "stub")

    from memory import memori_adapter as ma
    from tenancy import factory as tf
    from microagents import loader
    ma.clear_cache()
    tf.clear_cache()
    loader.clear_cache()
    yield loader
    ma.clear_cache()
    tf.clear_cache()
    loader.clear_cache()


def _install_bundle(tmp_path: Path, tenant_id: str, version: str, prompt: str) -> Path:
    bundle = tmp_path / "tenants" / tenant_id / "agents" / f"{ROLE}@{version}"
    bundle.mkdir(parents=True)
    bundle.joinpath("skill.toml").write_text(
        (SKILLS_DIR / ROLE / "skill.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    bundle.joinpath("prompt.md").write_text(prompt, encoding="utf-8")
    return bundle


def test_per_tenant_bundle_overrides_global(tmp_path, loader_env):
    _install_bundle(tmp_path, "acme", "1.0.0", "TENANT PROMPT acme")

    skill = loader_env.load_skill(ROLE, tenant_id="acme")
    assert skill.prompt == "TENANT PROMPT acme"
    # Manifest still parses as the global one it was copied from.
    assert skill.manifest["meta"]["name"] == ROLE


def test_no_bundle_falls_back_to_global(tmp_path, loader_env):
    _install_bundle(tmp_path, "acme", "1.0.0", "TENANT PROMPT acme")
    global_prompt = (SKILLS_DIR / ROLE / "prompt.md").read_text(encoding="utf-8")

    skill = loader_env.load_skill(ROLE, tenant_id="globex")
    assert skill.prompt == global_prompt


def test_version_pick_highest(tmp_path, loader_env):
    _install_bundle(tmp_path, "acme", "1.2.0", "PROMPT v1.2.0")
    # 1.10.0 > 1.2.0 numerically but not lexicographically.
    _install_bundle(tmp_path, "acme", "1.10.0", "PROMPT v1.10.0")

    skill = loader_env.load_skill(ROLE, tenant_id="acme")
    assert skill.prompt == "PROMPT v1.10.0"


def test_disabled_marker_skips_bundle(tmp_path, loader_env):
    bundle = _install_bundle(tmp_path, "acme", "1.0.0", "TENANT PROMPT acme")
    bundle.joinpath("disabled").touch()
    global_prompt = (SKILLS_DIR / ROLE / "prompt.md").read_text(encoding="utf-8")

    skill = loader_env.load_skill(ROLE, tenant_id="acme")
    assert skill.prompt == global_prompt


def test_reload_marker_busts_cache(tmp_path, loader_env):
    bundle = _install_bundle(tmp_path, "acme", "1.0.0", "PROMPT before")
    assert loader_env.load_skill(ROLE, tenant_id="acme").prompt == "PROMPT before"

    bundle.joinpath("prompt.md").write_text("PROMPT after", encoding="utf-8")
    # Still cached until the marker appears.
    assert loader_env.load_skill(ROLE, tenant_id="acme").prompt == "PROMPT before"

    marker = tmp_path / "tenants" / "acme" / "agents" / ".reload"
    marker.touch()
    assert loader_env.load_skill(ROLE, tenant_id="acme").prompt == "PROMPT after"
    assert not marker.exists()
