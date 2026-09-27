---
title: Web console
description: Start sessions, watch runs, and manage every tenant's agents, usage and settings.
---

`plnt serve` serves a web console at `/console`.

Sign in with:

- **the admin token**, to see all tenants and create new ones, or
- **a tenant's `pk_…` key**, to see only that tenant. You can hand this to a team that manages its own agents.

For each tenant:

| Tab | What it shows |
| --- | --- |
| Overview | Tokens, cost and runs over time, by agent and model (the parent is booked as `parent`). |
| Sessions | Every session by title and workspace. **New session** takes a workspace and who answers (the parent, or one bundle). The session view has a header (agents, messages, elapsed, Kill run) and four tabs: **Run** (task, parent decision, plan, agent cards, reply), **Agents** (each spawned agent with its full spec and steps), **Files** (what was listed, read, searched, written, run), **Events** (the raw stream). Live sessions stream. |
| Agents | Installed bundles. Install from the catalog; edit settings in a form generated from the bundle's `config_schema.json`; enable, disable, uninstall. Shows which required secrets are missing. |
| Settings | Secrets (write-only), the tenant's own model with a health check. |
| Audit log | The append-only audit log. |

The console keeps the key in this browser's local storage until you sign out, and sends it as a bearer token. Sign out on shared machines. It uses the same public HTTP API as everything else, so anything it does you can script.

## Building it from source

The PyPI package and the Docker image include the built console. When you install from git or run from a checkout, build it once:

```bash
cd console && npm ci && npm run build   # writes plnt/server/console/
```

Until then `/console` shows a "not built" message.
