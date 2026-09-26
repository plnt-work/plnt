---
title: Concepts
description: Bundles, tenants, installs, sessions, runs and events.
---

| Term | What it is |
| --- | --- |
| **Bundle** | An agent, as a folder: `skill.toml`, `prompt.md`, `config_schema.json`, `tools/*.py`. Versioned by `meta.version`. |
| **Catalog** | The bundles a server can install. Found on `PLNT_BUNDLE_PATH`, then in the bundles that ship with plnt. |
| **Tenant** | One of your customers. Has an id, a hashed API key, secrets, an optional model, and its own data directory. |
| **Install** | A bundle installed for one tenant with that tenant's config. It is a frozen copy with a sha256 digest, so later edits to the bundle don't change running customers until you reinstall. |
| **Session** | One conversation between a tenant's user and one installed bundle. Holds the chat history. |
| **Run** | The agent's work on one message: model calls and tool calls until it answers, fails, hits a budget or is killed. |
| **Event** | One recorded step of a run (`model_call`, `tool_call`, `assistant_message`, …). Numbered per session; streamed over SSE. See [Events](/docs/reference/events/). |

## What happens on a message

1. The server loads the tenant's install of the session's bundle and checks that its required secrets are set.
2. It resolves the model: the tenant's own model if one is set, otherwise the server default.
3. It renders `prompt.md` with the install's config (`{{config.business_name}}` → `Bright Smile Dental`).
4. It gives the model the bundle's tools. Each tool gets a `ToolContext` bound to this tenant: its config, its secrets, its data directory.
5. The agent loop runs, recording each step as an event. The loop stops on the answer, on `max_steps`, on the token or wall-clock budget, if the loop detector sees the same tool call repeated, or on a kill request.
6. Token usage and cost are written to the tenant's usage table, and the run is recorded in its audit log.

## Where things are stored

```
$PLNT_HOME/                        default ~/.plnt
└── tenants/<id>/
    ├── tenant.json                name, created_at, sha256 of the API key
    ├── secrets.json               mode 0600; write-only over the API
    ├── model.json                 optional per-tenant model
    ├── bundles/<slug>@<version>/  frozen bundle copy + its install record
    ├── data/<slug>/               the bundle's private data (ToolContext.data_dir)
    ├── data.db                    sessions, events, usage (SQLite)
    ├── work/<session>/            scratch dir for the built-in file tools
    └── audit.jsonl                append-only audit log
```

Deleting a tenant is deleting its directory.
