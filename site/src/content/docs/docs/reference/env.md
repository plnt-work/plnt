---
title: Environment variables
description: Server and model settings.
---

## Server

| Variable | Default | |
| --- | --- | --- |
| `PLNT_HOME` | `~/.plnt` | All state: tenants, installs, databases, audit logs. |
| `PLNT_ADMIN_TOKEN` | unset | Admin bearer token. Unset means admin routes answer 503. |
| `PLNT_BUNDLE_PATH` | unset | `:`-separated directories of bundles, searched before the built-in ones. |
| `PLNT_HOST` / `PORT` | `127.0.0.1` / `8787` | Where `plnt serve` listens (same as `--host` / `--port`). The Docker image sets `0.0.0.0`; platforms like Render set `PORT`. |

## Default model

Used for tenants without their own model. See [Local models](/docs/guides/local-models/#how-the-default-model-is-chosen).

| Variable | Default | |
| --- | --- | --- |
| `PLNT_FORCE` | `auto` | `local`, `cloud` or `offline` (test stub) to skip auto-selection. |
| `PLNT_LOCAL_URL` | `http://127.0.0.1:11434` | Local server. `/v1` in the path means OpenAI-compatible. |
| `PLNT_LOCAL_PROVIDER` | guessed | `ollama` or `openai`. |
| `PLNT_LOCAL_API_KEY` | unset | For local servers that require one. |
| `PLNT_PLANNER_MODEL` | `llama3.2:3b` | Local model for `small`/`auto` bundles. |
| `PLNT_DEEP_MODEL` | `llama3.1:8b` | Local model for `deep` bundles. |
| `PLNT_CLOUD_URL` | unset | OpenAI-compatible base URL. |
| `PLNT_CLOUD_API_KEY` | unset | |
| `PLNT_CLOUD_SMALL_MODEL` | unset | Required for cloud. |
| `PLNT_CLOUD_DEEP_MODEL` | small model | |
| `PLNT_NUM_CTX` | `8192` | Context window requested from Ollama. |
| `PLNT_TEMPERATURE` | `0.2` | |
| `PLNT_MAX_TOKENS` | `2048` | Max completion tokens per call. |
| `PLNT_MODEL_TIMEOUT` | `120` | Seconds per model call (also capped by the bundle's wall budget). |
| `PLNT_NATIVE_TOOLS` | `auto` | `on`, `off` (use the JSON shim), or `auto` (native, falling back to the shim). |
| `PLNT_COST_IN_PER_M` / `PLNT_COST_OUT_PER_M` | `0` | USD per million prompt / completion tokens, for cost reporting. |

## Playground (`plnt serve --playground`)

| Variable | Default | |
| --- | --- | --- |
| `PLNT_PLAYGROUND` | unset | `1` is the same as `--playground`. |
| `PLNT_PLAYGROUND_SESSIONS_PER_10MIN` | `10` | New conversations per IP. |
| `PLNT_PLAYGROUND_MESSAGES_PER_10MIN` | `30` | Messages per IP. |
| `PLNT_PLAYGROUND_DAILY_TOKENS` | `2000000` | Total tokens per day across all visitors; then 503. |
| `PLNT_PLAYGROUND_ORIGINS` | `*` | Comma-separated CORS origins. |
| `PLNT_TRUST_PROXY` | unset | `1` to take the client IP from the first `X-Forwarded-For` entry. Only behind a proxy that sets that entry itself (Render does); otherwise visitors can spoof it. |

## Site build

| Variable | |
| --- | --- |
| `PUBLIC_PLNT_PLAYGROUND_URL` | The playground server the site's `/playground` page talks to. Visitors can override it with `?api=`. |
