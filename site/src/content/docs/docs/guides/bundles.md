---
title: Write a bundle
description: A bundle is one agent as a folder. Build it once, install it for every tenant.
---

```bash
plnt init my-reviewer
```

```
my-reviewer/
├── skill.toml           what the agent is and what it may do
├── prompt.md            system prompt; {{config.x}} is filled per tenant
├── config_schema.json   the settings each tenant provides (JSON Schema)
└── tools/
    └── extra.py         optional Python tools the model can call
```

## skill.toml

```toml
[meta]
name = "my-reviewer"
version = "0.1.0"
description = "Reviews a workspace against our team's rules and cites path:line."
tags = ["code", "review"]

[runtime]
model_hint = "small"                          # small | deep | auto
tools = ["list_files", "read_file", "search"] # built-ins, and @tool names from tools/
require_tool = "read_file"                    # optional: no answer before this is called
max_steps = 10

[budget]
tokens = 30000                  # per message
wall_seconds = 180

[secrets]
required = []                   # e.g. ["GITHUB_TOKEN"] if a tool needs one
```

Every field is described in the [skill.toml reference](/docs/reference/skill-toml/). The built-in tools are listed in [Workspaces](/docs/guides/workspaces/#tools-over-the-workspace).

## prompt.md

Plain text or Markdown. `{{config.<key>}}` is replaced with the tenant's install config. Strings are inserted as they are; lists and objects are inserted as JSON. Tell the agent how to work and what to answer with; the shipped bundles are good templates.

```markdown
You are my-reviewer. Review the workspace against these rules: {{config.rules}}.

1. `list_files`, then `read_file` what the request names. Never describe code you have not read.
2. Report at most {{config.max_findings}} findings as `path:line` — what, why, fix.
```

The parent sees the bundle's `description`, not its prompt. Write the description for the parent: what the bundle is for.

## config_schema.json

A JSON Schema (draft 2020-12) for the per-tenant settings. Installs are validated against it, defaults are filled in, and the console builds its settings form from it. Set `"additionalProperties": false` so a typo fails the install and isn't silently ignored.

```json
{
  "type": "object",
  "properties": {
    "rules": {"type": "string", "title": "Review rules", "default": "no bare except, no print"},
    "max_findings": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8}
  },
  "additionalProperties": false
}
```

## Tools

The built-ins cover files and commands. For anything else (an API, a database, a ticket system) see [Tools and ToolContext](/docs/guides/tools/).

## Try it

```bash
plnt run ./my-reviewer "review src/" --workspace ~/src/api --config rules="no TODOs"
```

`plnt run` installs the bundle for a tenant (`local` unless you pass `--tenant`), sends one message, and prints each event. It exits non-zero if the run did not finish with an answer, so you can use it in CI.

## Versions and upgrades

An install is a frozen copy of the bundle at the time you installed it, with a sha256 digest. Editing the bundle folder does not change what existing tenants run. To roll out a change, bump `meta.version` and install again. If a tenant has several versions installed, the highest enabled version is used.

## Where the server finds bundles

`plnt install <slug>` and the HTTP API look up slugs in the catalog, in this order:

1. directories on `PLNT_BUNDLE_PATH` (`:`-separated)
2. the bundles that ship with plnt (`code-reviewer`, `test-writer`, `repo-explainer`, `changelog-writer`)

Over the HTTP API, tenants can only install catalog slugs, never arbitrary paths, so a tenant key cannot load new code onto the server.
