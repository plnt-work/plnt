"""Minimal skill loader for plnt-cloud bundles.

plnt has its own SkillRegistry that reads `$PLNT_HOME/skills/<role>/`. We
intentionally bypass it for slice 1 — plnt-cloud owns its skill catalog at
`plnt-cloud/microagents/skills/<role>/` so it ships with the package.

Per-tenant bundles installed at `<tenant_home>/agents/<slug>@<version>/`
shadow the process-global catalog when `load_skill` is called with a
tenant_id (slice 2). Tenants without installed bundles fall through.

The loader returns the prompt text and a parsed manifest dict. The Activity
injects the prompt into `spec.inputs["skill_prompt"]`, which the runner
already honors (runner.py: `skill_md = spec.inputs.get("skill_prompt") or _default_skill_prompt(...)`).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover — pyproject pins >=3.11
    import tomli as tomllib

from microagents import SKILLS_DIR


@dataclass(frozen=True)
class LoadedSkill:
    role: str
    prompt: str
    manifest: dict[str, Any]

    @property
    def budget_tokens(self) -> int:
        return int(self.manifest.get("budget", {}).get("tokens", 8000))

    @property
    def budget_wall_seconds(self) -> int:
        return int(self.manifest.get("budget", {}).get("wall_seconds", 60))

    @property
    def model_hint(self) -> str:
        return str(self.manifest.get("runtime", {}).get("model_hint", "auto"))

    @property
    def isolation(self) -> str:
        return str(self.manifest.get("runtime", {}).get("default_isolation", "process"))

    @property
    def tools(self) -> list[str]:
        """Named tools the skill may call. Empty = single-shot prompt skill."""
        return list(self.manifest.get("runtime", {}).get("tools", []))

    @property
    def max_steps(self) -> int:
        """Maximum LLM rounds for this skill. Per skill type:
            classifier / synthesizer = 1
            retriever (resolve_business, check_availability) = 2-3
            transactor (create_booking, cancel_booking) = 3-4

        Read from `[runtime] max_steps`. Defaults to 1 (single-shot) so a
        skill that forgets to declare it can't accidentally burn budget.
        """
        return int(self.manifest.get("runtime", {}).get("max_steps", 1))

    @property
    def response_schema(self) -> dict[str, Any] | None:
        """JSON Schema for the final response, when declared.

        When set AND `tools` is empty, the agent loop forwards this to
        Gemini as response_format.json_schema for native structured output —
        no more relying on the "FINAL: <json>" prompt convention.
        """
        rs = self.manifest.get("response_schema")
        if isinstance(rs, dict) and rs:
            return rs
        return None


# Manual cache (not lru_cache) so the `.reload` marker can evict per-tenant
# entries. Key: (tenant_id or None, role).
_cache: dict[tuple[str | None, str], LoadedSkill] = {}


def _parse_version(raw: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in raw.split("."))
    except ValueError:
        return None


def _tenant_bundle_dir(agents_dir: Path, role: str) -> Path | None:
    """Highest-semver installed bundle dir for `role`, or None."""
    if not agents_dir.is_dir():
        return None
    best: tuple[tuple[int, ...], Path] | None = None
    for d in agents_dir.glob(f"{role}@*"):
        if not d.is_dir() or (d / "disabled").exists():
            continue
        version = _parse_version(d.name.split("@", 1)[1])
        if version is None:
            continue
        if best is None or version > best[0]:
            best = (version, d)
    return best[1] if best else None


def _read_bundle(skill_dir: Path, role: str) -> LoadedSkill:
    prompt_path = skill_dir / "prompt.md"
    manifest_path = skill_dir / "skill.toml"
    if not prompt_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(
            f"skill bundle incomplete: {skill_dir} (need prompt.md and skill.toml)"
        )
    prompt = prompt_path.read_text(encoding="utf-8")
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    return LoadedSkill(role=role, prompt=prompt, manifest=manifest)


def load_skill(role: str, tenant_id: str | None = None) -> LoadedSkill:
    """Read a skill bundle from disk. Cached per (tenant_id, role).

    With a tenant_id, a bundle installed under the tenant's agents dir
    (`<agents_dir>/<role>@<version>/`) shadows the process-global one.
    """
    key = (tenant_id, role)
    agents_dir: Path | None = None
    if tenant_id is not None:
        # Lazy import: loader must stay importable without the tenancy stack.
        from tenancy.factory import for_tenant
        agents_dir = for_tenant(tenant_id).agents_dir
        marker = agents_dir / ".reload"
        if marker.exists():
            for stale in [k for k in _cache if k[0] == tenant_id]:
                del _cache[stale]
            marker.unlink(missing_ok=True)

    cached = _cache.get(key)
    if cached is not None:
        return cached

    skill_dir: Path | None = None
    if agents_dir is not None:
        skill_dir = _tenant_bundle_dir(agents_dir, role)
    if skill_dir is None:
        skill_dir = SKILLS_DIR / role
        if not skill_dir.is_dir():
            raise FileNotFoundError(f"skill bundle missing: {skill_dir}")

    skill = _read_bundle(skill_dir, role)
    _cache[key] = skill
    return skill


def list_skills() -> list[str]:
    """All skill roles currently shipped with plnt-cloud."""
    return sorted(
        p.name for p in SKILLS_DIR.iterdir()
        if p.is_dir() and (p / "skill.toml").exists()
    )


def clear_cache() -> None:
    _cache.clear()
