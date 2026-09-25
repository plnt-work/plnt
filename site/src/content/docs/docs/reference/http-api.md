---
title: HTTP API
description: Every route plnt serve exposes.
---

All routes are under `/v1`. Send credentials as `Authorization: Bearer <token>`. JSON in, JSON out. Errors are `{"detail": "..."}`.

**Auth** column: **admin** needs `PLNT_ADMIN_TOKEN`; **tenant** accepts the admin token or that tenant's `pk_…` key; **none** is public.

## Meta

| Method | Path | Auth | |
| --- | --- | --- | --- |
| GET | `/health` | none | `{ok, version, dev}` |
| GET | `/whoami` | any | `{role: "admin"}` or `{role: "tenant", tenant_id}` |
| GET | `/bundles` | none | Catalog: slug, version, description, tools, `config_schema`, required secrets. |

## Tenants

| Method | Path | Auth | Body → Response |
| --- | --- | --- | --- |
| POST | `/tenants` | admin | `{id, name?}` → 201 `{tenant, api_key}` (key shown once; 409 if the id exists) |
| GET | `/tenants` | admin | `{tenants: [...]}` |
| GET | `/tenants/{t}` | tenant | Summary plus installs, secret names, model |
| DELETE | `/tenants/{t}` | admin | 204. Deletes all of the tenant's data. |
| POST | `/tenants/{t}/keys` | admin | Rotate → `{api_key}`. The old key stops working. |

## Installs

| Method | Path | Auth | Body → Response |
| --- | --- | --- | --- |
| GET | `/tenants/{t}/installs` | tenant | `{installs: [...]}`, each with its `config_schema` and `secrets_required` |
| POST | `/tenants/{t}/installs` | tenant | `{bundle, config}` → 201 install. Catalog slugs only. 422 on invalid config. |
| PATCH | `/tenants/{t}/installs/{slug}` | tenant | `{enabled?, config?}` → install |
| DELETE | `/tenants/{t}/installs/{slug}` | tenant | 204 |

## Secrets and model

| Method | Path | Auth | Body → Response |
| --- | --- | --- | --- |
| GET | `/tenants/{t}/secrets` | tenant | `{secrets: ["NAME", ...]}`: names only |
| PUT | `/tenants/{t}/secrets/{NAME}` | tenant | `{value}` → 204. Names are `UPPER_SNAKE`. |
| DELETE | `/tenants/{t}/secrets/{NAME}` | tenant | 204 |
| GET | `/tenants/{t}/model` | tenant | `{model: {...} \| null}` |
| PUT | `/tenants/{t}/model` | tenant | Model profile (below) → `{model}` |
| DELETE | `/tenants/{t}/model` | tenant | 204: back to the server default |
| GET | `/tenants/{t}/model/health` | tenant | `{ok, reachable, model_present, detail, hint, ...}` |

Model profile fields: `provider` (`ollama` or `openai`), `base_url`, `model` (required); `deep_model`, `api_key_secret` (the name of a tenant secret), `num_ctx`, `temperature`, `max_tokens`, `timeout`, `native_tools` (`auto`/`on`/`off`), `cost_in_per_m`, `cost_out_per_m`.

## Sessions

| Method | Path | Auth | Body → Response |
| --- | --- | --- | --- |
| POST | `/tenants/{t}/sessions` | tenant | `{bundle, user_id?}` → 201 `{session_id}` |
| GET | `/tenants/{t}/sessions?limit=100` | tenant | `{sessions: [...]}` |
| POST | `/tenants/{t}/sessions/{sid}/messages` | tenant | `{text}` → 202 `{run_id}`. 409 if a run is in progress. |
| GET | `/tenants/{t}/sessions/{sid}/events?after=N` | tenant | `{events: [...]}` with `seq > N` |
| GET | `/tenants/{t}/sessions/{sid}/stream?after=N&until_idle=0` | tenant | Server-sent events. `until_idle=1` closes after the next `run_finished`. |
| POST | `/tenants/{t}/sessions/{sid}/kill` | tenant | `{killed: bool}` |

Each SSE message has `id` = the event's `seq`, `event` = its kind, and `data` = the event as JSON. See [Events](/docs/reference/events/).

## Usage and audit

| Method | Path | Auth | |
| --- | --- | --- | --- |
| GET | `/tenants/{t}/usage?since=<unix seconds>` | tenant | Totals (`model_calls`, `prompt_tokens`, `completion_tokens`, `cost_usd`) and a breakdown by bundle and model. |
| GET | `/tenants/{t}/audit?limit=200&action=` | tenant | `{events: [...]}`: the most recent `limit` entries, oldest first. |

## Playground (only with `--playground`)

Anonymous, limited to the seeded demo tenants, rate-limited per IP.

| Method | Path | |
| --- | --- | --- |
| GET | `/playground` | Demo tenants, their agents and config, limits. |
| POST | `/playground/sessions` | `{tenant, bundle}` → `{session_id, token}` |
| POST | `/playground/sessions/{sid}/messages?token=` | `{text}` (≤ 500 chars). 429 when rate-limited, 503 when the daily budget is used up. |
| GET | `/playground/sessions/{sid}/stream?token=&after=` | SSE, as above. |
| POST | `/playground/sessions/{sid}/kill?token=` | |

The OpenAPI schema is at `/openapi.json`, and interactive docs at `/docs`, on any running server.
