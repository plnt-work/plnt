---
title: Serve many customers
description: Tenants, API keys, and what is kept separate between them.
---

## Tenants and keys

```bash
export PLNT_ADMIN_TOKEN=$(openssl rand -hex 24)
plnt serve --port 8787

curl -X POST $API/tenants -H "Authorization: Bearer $PLNT_ADMIN_TOKEN" \
  -H 'content-type: application/json' -d '{"id":"acme","name":"Acme Dental"}'
# → {"tenant": {...}, "api_key": "pk_..."}   the key is shown once
```

There are two kinds of credential:

| Credential | Can do |
| --- | --- |
| **Admin token** (`PLNT_ADMIN_TOKEN`) | Everything: create, list and delete tenants, rotate keys, and act on any tenant. |
| **Tenant key** (`pk_…`) | Only that tenant's routes: installs, config, secrets, model, sessions, usage, audit. A key for tenant A gets 401 on tenant B. |

Give the tenant key to your backend that serves that customer, or to the customer if they manage their own agent in the [console](/docs/guides/console/). Rotate it with `POST /v1/tenants/{id}/keys` (admin only). Only a sha256 hash of each key is stored.

Auth fails closed: if `PLNT_ADMIN_TOKEN` is not set, admin routes answer 503, never open. `plnt dev` turns auth off, and only listens on `127.0.0.1`.

## What is separate per tenant

| | Where | How it's kept apart |
| --- | --- | --- |
| Installs and config | `<tenant>/bundles/` | Per-tenant copies; config validated per install. |
| Secrets | `<tenant>/secrets.json` | Only this tenant's tools receive them. |
| Model | `<tenant>/model.json` | Overrides the server default for this tenant only. |
| Conversations, events, usage | `<tenant>/data.db` | One SQLite file per tenant. |
| Bundle data | `<tenant>/data/<slug>/` | `ToolContext.data_dir`. |
| Audit | `<tenant>/audit.jsonl` | Append-only. |

The tenant id in the URL selects the directory; ids are validated so they cannot escape `$PLNT_HOME/tenants/`. The test suite checks that two tenants with the same bundle see disjoint sessions, usage, audit and data.

What is **not** separate in 0.1: all tenants share one server process and its CPU, memory and filesystem permissions. A bundle's tool code could read another tenant's files if it tried. That's why you should only install bundles you trust.

## Talking to an agent

```bash
KEY="Authorization: Bearer pk_..."
SID=$(curl -s -X POST $API/tenants/acme/sessions -H "$KEY" \
  -H 'content-type: application/json' -d '{"bundle":"support-desk","user_id":"cust-42"}' \
  | jq -r .session_id)

curl -X POST $API/tenants/acme/sessions/$SID/messages -H "$KEY" \
  -H 'content-type: application/json' -d '{"text":"do you do emergency appointments?"}'
# → 202 {"run_id": "..."}

curl -N $API/tenants/acme/sessions/$SID/stream -H "$KEY"
```

Messages are handled asynchronously. Read results from the SSE `stream` (live) or `events?after=N` (polling). The reply is the `assistant_message` event; the run ends with `run_finished`. See [Events](/docs/reference/events/).

A session handles one message at a time. Sending while a run is in progress returns 409.

## Usage and cost

```bash
curl "$API/tenants/acme/usage?since=$(date -d '30 days ago' +%s)" -H "$KEY"
```

This returns tokens and cost broken down by bundle and model. Cost is computed from `cost_in_per_m` / `cost_out_per_m` on the model profile (per million tokens). Set them if you want dollar figures; they default to 0.
