---
title: Concepts
description: Parent, agents, bundles, workspaces, tenants, sessions, runs and events.
---

| Term | What it is |
| --- | --- |
| **Parent** | The planner in front of a session. One model call per message decides: answer, ask, or spawn agents (which bundle, what intent, what each depends on). A second call merges several agents' answers. |
| **Agent** | One micro-agent doing one part of a task: an installed bundle, or a role the parent invented. Runs the agent loop with its own tools, budget and guardrails. |
| **Bundle** | An agent as a folder: `skill.toml`, `prompt.md`, `config_schema.json`, optional `tools/*.py`. Versioned by `meta.version`. |
| **Catalog** | The bundles a server can install. Found on `PLNT_BUNDLE_PATH`, then in the bundles that ship with plnt. |
| **Workspace** | What a session works on: `demo:<name>`, a local folder, or a git URL. A private copy is made in the session's working directory; agents only see that copy. |
| **Tenant** | Whom the agents work for. Has an id, a hashed API key, secrets, an optional model, and its own data directory. |
| **Install** | A bundle installed for one tenant with that tenant's config. A frozen copy with a sha256 digest. |
| **Session** | One task and its follow-ups. Has a title (the first message), a workspace, and either a bundle (that agent answers every message) or none (the parent decides). |
| **Run** | The work on one message, from `user_message` to `run_finished`. |
| **Event** | One recorded step, with the id of the agent that produced it. Numbered per session; streamed over SSE. See [Events](/docs/reference/events/). |
| **Transcript** | The events folded into turns: parent decision, plan, agent cards, reply. See [Transcript](/docs/reference/transcript/). |

## What happens on a message

1. The session's workspace copy is already in place (made when the session started).
2. **Parent mode.** The parent is told the tenant, the workspace, the installed bundles (name, description, tools) and whether it may invent roles. One structured model call returns `chat`, `clarify` or `agents` with a plan. The decision and its reason are recorded.
3. For each planned agent, the runtime builds a spec: the bundle's rendered prompt, its tools (built-ins over the workspace plus its own `tools/*.py`), its model, its budget and `require_tool`. In read-only mode, `write_file` and `execute` are removed. The spec is recorded as `agent_spawned`.
4. Agents with no unmet dependency run in parallel (up to `PLNT_MAX_CONCURRENCY`). A dependent agent starts once its upstream agents finished and gets their results in its prompt.
5. Each agent's loop records model calls, tool calls and results, guardrail actions, and `agent_finished` with its answer, tokens and wall time.
6. One agent: its answer is the reply. Several: the parent merges them (`assistant_message` with `source: synth`).
7. Usage is booked per agent (`parent`, each bundle slug, `role:<name>` for invented roles); the run is recorded in the tenant's audit log.

**Agent mode** (a session with a bundle) skips steps 2 and 6: the bundle handles every message itself.

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
    ├── work/<session>/            the session's workspace copy (ToolContext.workdir)
    └── audit.jsonl                append-only audit log
```

Deleting a tenant is deleting its directory.
