---
title: CLI
description: plnt commands.
---

`BUNDLE` is either a path to a bundle directory or a catalog slug. `--config key=value` sets a string; `--config-json key=<json>` sets any JSON value. Both can be repeated.

## Build and try

| Command | |
| --- | --- |
| `plnt init SLUG [--dir DIR]` | Scaffold a working bundle in `DIR/SLUG`. |
| `plnt run BUNDLE MESSAGE… [--tenant local] [--config …] [--config-json …] [--secret NAME=value]` | Install BUNDLE for the tenant (created if missing), send one message, and print every event. Exit code 0 only if the run answered. |
| `plnt dev [BUNDLE] [--port 8787] [--config …]` | API server on `127.0.0.1` with auth off, tenant `dev`. Optionally installs BUNDLE first. |

## Models

| Command | |
| --- | --- |
| `plnt models doctor [--model M] [--url U] [--provider ollama\|openai] [--force local\|cloud] [--no-probe]` | Check reachability, pulled model, tool calling, JSON output and context size. Prints the fix for each failure. Exit code 1 if any check fails. |
| `plnt models list [--url U] [--provider …]` | Models the endpoint serves. |

## Operate

| Command | |
| --- | --- |
| `plnt serve [--host 127.0.0.1] [--port 8787] [--playground]` | The multi-tenant API and console. Set `PLNT_ADMIN_TOKEN`. `--playground` also seeds demo tenants and opens the anonymous playground API. Don't use it with real customers. |
| `plnt tenants create ID [--name NAME]` | Prints the tenant's API key once. |
| `plnt tenants list` | Tenants and their installs. |
| `plnt tenants delete ID` | Deletes the tenant and all its data (asks first). |
| `plnt install BUNDLE --tenant ID [--config …]` | Install or reinstall with new config. |

The CLI acts directly on `$PLNT_HOME`, not over HTTP, so run it on the server machine (or use the HTTP API).

## Older commands

`plnt up`, `submit`, `runs`, `tail`, `monitor`, `skills`, `auth` and `vendor-chat` belong to plnt's earlier single-user runtime. They still work but are not part of the platform and may be removed.
