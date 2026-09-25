"""Bundles — the unit you build once and install into many tenants.

A bundle is a directory:

    my-agent/
      skill.toml            manifest (plnt.control.skill_schema.SkillManifest)
      prompt.md             system prompt; may reference {{config.<key>}}
      config_schema.json    optional JSON Schema for per-tenant config
      examples.md           optional few-shots appended to the prompt
      tools/*.py            optional @tool functions (see plnt.bundles.sdk)

`load_bundle()` validates all of it up front: manifest shape, that every
tool the manifest lists is either a built-in or defined in tools/, that the
prompt only references config keys the schema declares.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import ValidationError

from plnt.bundles.sdk import TOOL_ATTR, ToolSpec
from plnt.control.skill_schema import SkillManifest

BUILTIN_TOOLS = frozenset({"search", "execute"})
_CONFIG_REF_RE = re.compile(r"\{\{\s*config\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class BundleError(ValueError):
    """The bundle (or a tenant config for it) is invalid. Message says why."""


@dataclass
class Bundle:
    path: Path
    manifest: SkillManifest
    prompt_template: str
    config_schema: dict[str, Any] | None = None
    tools: dict[str, ToolSpec] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        return self.manifest.meta.name

    @property
    def version(self) -> str:
        return self.manifest.meta.version

    @property
    def builtin_tools(self) -> list[str]:
        return [t for t in self.manifest.runtime.tools if t in BUILTIN_TOOLS]

    # ------------------------------------------------------------- config

    def validate_config(self, config: dict[str, Any] | None) -> dict[str, Any]:
        """Apply schema defaults, validate, and return the effective config."""
        cfg = dict(config or {})
        schema = self.config_schema
        if not schema:
            if cfg:
                raise BundleError(f"{self.slug} takes no config, got keys {sorted(cfg)}")
            return {}
        for key, prop in (schema.get("properties") or {}).items():
            if key not in cfg and isinstance(prop, dict) and "default" in prop:
                cfg[key] = prop["default"]
        try:
            jsonschema.validate(cfg, schema)
        except jsonschema.ValidationError as e:
            where = "/".join(str(p) for p in e.absolute_path) or "(root)"
            raise BundleError(f"invalid config for {self.slug} at {where}: {e.message}") from None
        return cfg

    def missing_secrets(self, available: set[str]) -> list[str]:
        return [s for s in self.manifest.secrets.required if s not in available]

    # ------------------------------------------------------------- prompt

    def render_prompt(self, config: dict[str, Any]) -> str:
        def sub(m: re.Match[str]) -> str:
            v = config.get(m.group(1), "")
            return v if isinstance(v, str) else json.dumps(v)

        text = _CONFIG_REF_RE.sub(sub, self.prompt_template)
        if self.manifest.examples:
            text += "\n\n" + self.manifest.examples
        return text

    def digest(self) -> str:
        """sha256 over the bundle's files — identifies exactly what was installed."""
        h = hashlib.sha256()
        for p in sorted(self.path.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith("."):
                h.update(str(p.relative_to(self.path)).encode())
                h.update(p.read_bytes())
        return h.hexdigest()


def _load_tools(bundle_dir: Path, slug: str) -> dict[str, ToolSpec]:
    tools_dir = bundle_dir / "tools"
    found: dict[str, ToolSpec] = {}
    if not tools_dir.is_dir():
        return found
    for py in sorted(tools_dir.glob("*.py")):
        if py.name.startswith("_"):
            continue
        digest = hashlib.sha1(str(py.resolve()).encode()).hexdigest()[:10]
        mod_name = f"plnt_bundle_{slug.replace('-', '_')}_{py.stem}_{digest}"
        spec = importlib.util.spec_from_file_location(mod_name, py)
        if spec is None or spec.loader is None:
            raise BundleError(f"cannot import {py}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as e:  # noqa: BLE001 — report any import failure as a bundle error
            raise BundleError(f"{py.relative_to(bundle_dir)} failed to import: {e}") from e
        for obj in vars(module).values():
            ts = getattr(obj, TOOL_ATTR, None)
            if isinstance(ts, ToolSpec):
                if ts.name in found or ts.name in BUILTIN_TOOLS:
                    raise BundleError(f"duplicate tool name {ts.name!r} in {slug}")
                found[ts.name] = ts
    return found


def load_bundle(path: str | Path) -> Bundle:
    bundle_dir = Path(path).expanduser().resolve()
    manifest_path = bundle_dir / "skill.toml"
    prompt_path = bundle_dir / "prompt.md"
    if not manifest_path.is_file() or not prompt_path.is_file():
        raise BundleError(f"{bundle_dir} is not a bundle (needs skill.toml and prompt.md)")
    try:
        data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise BundleError(f"skill.toml: {e}") from e
    try:
        manifest = SkillManifest.model_validate(data)
    except ValidationError as e:
        raise BundleError(f"skill.toml: {e}") from e
    if not _SLUG_RE.match(manifest.meta.name):
        raise BundleError(f"[meta] name {manifest.meta.name!r} must be a lowercase slug")
    examples = bundle_dir / "examples.md"
    if examples.is_file():
        manifest.examples = examples.read_text(encoding="utf-8")

    schema_rel = manifest.install.config_schema or "config_schema.json"
    schema_path = bundle_dir / schema_rel
    config_schema = None
    if schema_path.is_file():
        try:
            config_schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(config_schema)
        except (json.JSONDecodeError, jsonschema.SchemaError) as e:
            raise BundleError(f"{schema_rel}: {e}") from e
    elif manifest.install.config_schema:
        raise BundleError(f"[install] config_schema {schema_rel!r} does not exist")

    prompt = prompt_path.read_text(encoding="utf-8")
    declared = set((config_schema or {}).get("properties", {}))
    undeclared = sorted(set(_CONFIG_REF_RE.findall(prompt)) - declared)
    if undeclared:
        raise BundleError(f"prompt.md references config keys not in the schema: {undeclared}")

    tools = _load_tools(bundle_dir, manifest.meta.name)
    unknown = [t for t in manifest.runtime.tools if t not in BUILTIN_TOOLS and t not in tools]
    if unknown:
        raise BundleError(
            f"skill.toml lists tools {unknown} that are neither built-in "
            f"({sorted(BUILTIN_TOOLS)}) nor defined in tools/*.py"
        )
    req = manifest.runtime.require_tool
    if req and req not in manifest.runtime.tools:
        raise BundleError(f"[runtime] require_tool {req!r} must also be listed in tools")
    # Only tools the manifest lists are exposed to the model.
    tools = {n: t for n, t in tools.items() if n in manifest.runtime.tools}
    return Bundle(
        path=bundle_dir,
        manifest=manifest,
        prompt_template=prompt,
        config_schema=config_schema,
        tools=tools,
    )


def parse_version(raw: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in raw.split("."))
    except ValueError:
        raise BundleError(f"version {raw!r} must be dotted integers like 1.2.0") from None
