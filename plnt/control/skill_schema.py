"""Pydantic schema for plnt skill manifests.

A skill in plnt v0.2 is a *directory*:

  ~/.plnt/skills/<role>/
    ├── skill.toml      typed metadata (this module's schema)
    └── prompt.md       system prompt (raw markdown, agent sees it verbatim)

Optional:
    └── examples.md     few-shot examples appended to the prompt

The TOML carries:
  [meta]      identity, version, tags
  [runtime]   model hint, tools, isolation rung
  [budget]    tokens / wall_seconds / joules
  [requires]  inputs the skill needs before it can run (drives triage)
  [output]    JSON-Schema-ish description of the agent's structured output
  [graph]     which child skills this skill is allowed to spawn

Optional sections (all default to empty):
  [triggers]               event kinds / cron schedule that wake the skill
  [integrations_required]  map of integration name -> required?
  [install]                install-time hooks (config_schema path)

Old-format markdown skills (`~/.plnt/skills/<role>.md`) keep working — the
loader probes for both forms.

The HTML/RAG storage layer uses the [output] schema's `format = "html"` hint
to know which fields are rendered HTML (for storage and TUI display);
prompts and skill metadata themselves stay markdown/TOML for token
efficiency (per 2026 research — see SETUP.md).
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SkillMeta(BaseModel):
    name: str
    version: str = "0.1"
    description: str = ""
    tags: list[str] = Field(default_factory=list)


_TOOL_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")


class SkillRuntime(BaseModel):
    model_hint: Literal["small", "deep", "auto"] = "auto"
    # Built-ins are `search` / `execute`; bundles may also define their own
    # tools in `tools/*.py`. Whether each name resolves is checked when the
    # bundle is loaded (plnt.bundles), not here.
    tools: list[str] = Field(default_factory=lambda: ["search", "execute"])
    default_isolation: Literal["process", "docker", "gvisor", "microvm", "wasm"] = "process"
    # Maximum model turns per message (tool calls + final answer).
    max_steps: int = Field(default=6, ge=1, le=50)

    @field_validator("tools")
    @classmethod
    def _check_tools(cls, v: list[str]) -> list[str]:
        bad = [t for t in v if not _TOOL_NAME_RE.match(t)]
        if bad:
            raise ValueError(f"invalid tool names {bad}; use identifiers like `lookup_order`")
        return v


class SkillBudget(BaseModel):
    tokens: int = Field(default=20_000, ge=100)
    wall_seconds: int = Field(default=300, ge=1)
    joules: int = Field(default=0, ge=0)


class RequiredInput(BaseModel):
    """One thing the skill MUST be given before it can plan or run.

    The triage layer reads these to compose a clarifying question when the
    user's intent doesn't already include them. The match is by name in
    spec.inputs / spec.inputs.from_agents.
    """

    name: str
    type: Literal["path", "file", "directory", "string", "url", "list"] = "string"
    description: str = ""
    example: str = ""

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum():
            raise ValueError(f"name must be a simple identifier, got {v!r}")
        return v


class OptionalInput(RequiredInput):
    default: Any = None


class SkillRequires(BaseModel):
    inputs: list[RequiredInput] = Field(default_factory=list)
    optional: list[OptionalInput] = Field(default_factory=list)


class OutputProperty(BaseModel):
    """One field in the skill's structured output.

    format='html' marks this field as HTML — the storage layer (and TUI)
    will treat it as rich content. Default is plain text/markdown.
    """

    type: Literal["string", "array", "object", "path", "number", "boolean"] = "string"
    description: str = ""
    format: Literal["text", "markdown", "html", "json"] = "text"
    items: str | None = None  # for arrays — element type


class SkillOutput(BaseModel):
    schema_type: Literal["object", "string", "free"] = Field(default="object", alias="schema")
    required: list[str] = Field(default_factory=list)
    properties: dict[str, OutputProperty] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class SkillTriggers(BaseModel):
    """What wakes this skill up besides a direct user intent."""

    kinds: list[str] = Field(default_factory=list)
    schedule: str = ""

    @field_validator("schedule")
    @classmethod
    def _check_schedule(cls, v: str) -> str:
        # Loose shape check only: 5 whitespace-separated cron fields.
        if v and len(v.split()) != 5:
            raise ValueError(f"schedule must have 5 cron fields, got {v!r}")
        return v


class SkillInstall(BaseModel):
    """Install-time hooks — paths are relative to the skill directory."""

    config_schema: str = ""

    @field_validator("config_schema")
    @classmethod
    def _check_config_schema(cls, v: str) -> str:
        if not v:
            return v
        if v.startswith("/") or ".." in v.split("/"):
            raise ValueError(f"config_schema must be a relative path without '..', got {v!r}")
        return v


class SkillSecrets(BaseModel):
    """Secrets a tenant must set before this bundle can run (e.g. an API key).

    Values are stored per tenant (plnt.tenancy.secrets) and handed to the
    bundle's tools via `ctx.secret(name)`; they never enter the prompt.
    """

    required: list[str] = Field(default_factory=list)


class SkillGraph(BaseModel):
    """Static bound on what this skill is allowed to spawn.

    Empty list means 'no child agents'. Use this to prevent runaway fan-outs
    from skills that should be leaves.
    """

    can_spawn: list[str] = Field(default_factory=list)


class SkillManifest(BaseModel):
    """The complete parsed skill.toml plus the markdown body."""

    meta: SkillMeta
    runtime: SkillRuntime = Field(default_factory=SkillRuntime)
    budget: SkillBudget = Field(default_factory=SkillBudget)
    requires: SkillRequires = Field(default_factory=SkillRequires)
    output: SkillOutput = Field(default_factory=SkillOutput)
    graph: SkillGraph = Field(default_factory=SkillGraph)
    triggers: SkillTriggers = Field(default_factory=SkillTriggers)
    integrations_required: dict[str, bool] = Field(default_factory=dict)
    install: SkillInstall = Field(default_factory=SkillInstall)
    secrets: SkillSecrets = Field(default_factory=SkillSecrets)
    # JSON Schema for a structured final answer (optional).
    response_schema: dict[str, Any] | None = None

    # The markdown body — system prompt the agent sees.
    prompt: str = ""
    # Optional few-shots, appended below the prompt at runtime.
    examples: str = ""

    @property
    def role(self) -> str:
        return self.meta.name
