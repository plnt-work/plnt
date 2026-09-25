---
title: Web console
description: See every customer's conversations, usage and settings.
---

`plnt serve` serves a web console at `/console`.

Sign in with:

- **the admin token**, to see all tenants and create new ones, or
- **a tenant's `pk_…` key**, to see only that tenant. You can hand this to a customer who wants to manage their own agent.

For each tenant:

| Tab | What it shows |
| --- | --- |
| Overview | Tokens, cost and runs over time, by agent and model. |
| Conversations | Every session with its full transcript and event trace. Live sessions stream, and have a Kill button. |
| Agents | Installed bundles. Install from the catalog; edit settings in a form generated from the bundle's `config_schema.json`; enable, disable, uninstall. Shows which required secrets are missing. |
| Settings | Secrets (write-only), the tenant's own model with a health check. |
| Audit | The append-only audit log. |

The console keeps the key in this browser's local storage until you sign out, and sends it as a bearer token. Sign out on shared machines. It uses the same public HTTP API as everything else, so anything it does you can script.

## Building it from source

A pip install includes the built console. From a git checkout, build it once:

```bash
cd console && npm ci && npm run build   # writes plnt/server/console/
```

Until then `/console` shows a "not built" message.
