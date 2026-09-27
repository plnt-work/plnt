---
title: skill.toml
description: The bundle manifest.
---

```toml
[meta]
name = "code-reviewer"       # required; the slug. lowercase, digits, '-'
version = "0.1.0"            # dotted integers; installs are keyed by it
description = "..."          # shown in the catalog, the console, and to the parent
tags = ["code", "review"]

[runtime]
model_hint = "small"         # small | deep | auto  (which model slot to use)
tools = ["list_files", "read_file", "search"]
                             # @tool names from tools/, or built-ins: list_files,
                             # read_file, search, write_file, execute
require_tool = "read_file"   # optional; see Guardrails
max_steps = 10               # model calls per message, 1..50 (default 6)

[budget]
tokens = 30000               # per message (default 20000, min 100)
wall_seconds = 180           # per message (default 300)

[secrets]
required = ["TRACKER_TOKEN"] # tenant must set these before a run can start

# optional: make the final answer a validated JSON object
[response_schema]
type = "object"
required = ["reply"]
[response_schema.properties.reply]
type = "string"
```

Optional files next to `skill.toml`:

- `config_schema.json`: the per-tenant settings schema. Use a different file name with `[install] config_schema = "settings.json"`.
- `examples.md`: appended to the rendered prompt (few-shot examples).

Loading a bundle fails with a clear error if:

- a tool in `runtime.tools` is neither a built-in nor defined in `tools/`
- `require_tool` isn't in `runtime.tools`
- `config_schema.json` is not valid JSON Schema (draft 2020-12)
- `prompt.md` references `{{config.x}}` where `x` isn't in the schema

Other sections in the file (`[requires]`, `[output]`, `[graph]`, `[triggers]`) are accepted for compatibility with plnt's older skill format and are not used by the platform runtime.
