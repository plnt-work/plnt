---
title: Config and secrets
description: Per-tenant settings and credentials.
---

## Config

Config is what varies between tenants and is safe to show: review focus, test framework, audience, house rules. It is declared by the bundle's `config_schema.json` and given at install time.

```bash
plnt install code-reviewer --tenant acme \
  --config focus=security --config max_findings=5 \
  --config-json language_hint='"Django 5, Python 3.12"'
```

`--config key=value` sets a string. `--config-json key=<json>` sets any JSON value.

Over HTTP:

```bash
curl -X POST $API/tenants/acme/installs -H "$AUTH" -H 'content-type: application/json' \
  -d '{"bundle":"code-reviewer","config":{"focus":"security","max_findings":5}}'

# change settings later
curl -X PATCH $API/tenants/acme/installs/code-reviewer -H "$AUTH" \
  -H 'content-type: application/json' -d '{"config":{"focus":"all"}}'
```

Invalid config is rejected (HTTP 422) with the failing path. Config changes are recorded in the tenant's audit log.

## Secrets

Secrets are credentials: a tracker token, a registry key. A bundle declares which ones it needs:

```toml
[secrets]
required = ["TRACKER_TOKEN"]
```

Each tenant sets its own:

```bash
curl -X PUT $API/tenants/acme/secrets/TRACKER_TOKEN -H "$AUTH" \
  -H 'content-type: application/json' -d '{"value":"ghp_..."}'
```

- Secrets are **write-only** over the API. Listing returns names, never values.
- A session whose bundle needs a secret the tenant hasn't set fails with a clear error before any model call.
- Tools read them with `ctx.secret("TRACKER_TOKEN")`.
- They are stored in `<tenant>/secrets.json` with file mode `0600`. They are not encrypted at rest in 0.1, so protect the disk.
- A tool can read any secret its tenant has set, not only the ones its bundle declares.

## Per-tenant model

A tenant can bring its own model. The API key is stored as a secret and referenced by name:

```bash
curl -X PUT $API/tenants/acme/secrets/OPENAI_KEY -H "$AUTH" -d '{"value":"sk-..."}' \
  -H 'content-type: application/json'
curl -X PUT $API/tenants/acme/model -H "$AUTH" -H 'content-type: application/json' -d '{
  "provider": "openai",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4.1-mini",
  "api_key_secret": "OPENAI_KEY",
  "cost_in_per_m": 0.4, "cost_out_per_m": 1.6
}'
curl $API/tenants/acme/model/health -H "$AUTH"
```

See [Local models](/docs/guides/local-models/#one-model-per-tenant) for the on-prem case.
