"""Skill bundles for plnt-cloud micro-agents.

Each skill lives in `skills/<role>/` as a `skill.toml` + `prompt.md` pair,
following plnt's SkillManifest format (see plnt/control/skill_schema.py).
The bundles are loaded by plnt's SkillRegistry, pointed at this directory.
"""
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"
