# plnt

**Ship one agent to 1,000 customers — each isolated, any model, local or cloud.**

plnt is an open-source runtime for teams that build an AI agent once and
deploy it to many customers (tenants). Package the agent as a **bundle**,
install it into each tenant with that tenant's own config, and plnt keeps every
tenant's sandbox, budget, memory, secrets, audit log and usage separate — on a
hosted model or a model running on the tenant's own hardware.

> **Status: pre-alpha, mid-consolidation.** This repository now holds the whole
> project (runtime, reference app, site, registry). The runtime rework that
> makes the above sentence fully true is sequenced in [ROADMAP.md](ROADMAP.md).
> Anything not marked `[done]` there is not shipped.

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

## What is different

| | plnt |
|---|---|
| **Bundles installed per tenant** | One agent package (`skill.toml` + `prompt.md` + `config_schema.json` + tools), installed N times with N validated configs. An app-store model for agents. |
| **Hard guardrails per tenant** | Process / Docker sandbox rungs with rlimits, token + wall-clock budgets, a live kill switch that terminates runaway agents mid-run, append-only audit log. |
| **Bring your own model, per tenant** | Hosted models (Gemini, OpenAI-compatible) or local ones (Ollama, llama.cpp, vLLM, LM Studio) — chosen per tenant, so a customer that needs on-prem can have it. |

## Repository layout

```
plnt/                 the runtime (Python package `plnt`)
  control/            planner, budgets, streaming kill switch (ACC), DAG, skill schema
  execution/          sandbox rungs (process, docker), agent runner, blackboard audit log
  models/             model providers: Ollama (native), OpenAI-compatible, JSON tool shim, doctor
  agent/              the tool-calling agent loop
  bundles/            bundle format, @tool SDK, catalog
  tenancy/            tenants, keys, secrets, per-tenant model, installs, sessions, usage, audit
  executors/          runs tenant sessions (in-process, durable SQLite event log)
  server/             multi-tenant HTTP API (`plnt serve`), hosts the console at /console
console/              web console (React) for operators and tenants
  surface/            local HTTP server + CLI surface
skills/               built-in agent bundles
tests/                runtime tests
examples/booking/     legacy booking app (Temporal, map UI; formerly plnt-work/maps-micro-saas),
                      being replaced by registry/bundles/booking-desk
site/                 plnt.work marketing site + docs (formerly devdattatalele/plnt-site)
registry/             agent bundles: support-desk, booking-desk (formerly plnt-work/microagents)
bench/                runtime overhead benchmark
```

All four former repositories were imported with full git history
(`git log -- examples/booking`, `git log -- site`, `git log -- registry`).

## Quickstart: one agent, many tenants

Docs: **https://plnt.work/docs/** · try it without installing: **https://plnt.work/playground**

```bash
pip install "git+https://github.com/plnt-work/plnt"   # `pip install plnt` once v0.1.0 is on PyPI
# or: docker build -t plnt . && docker run -p 8787:8787 -v plnt-data:/data -e PLNT_ADMIN_TOKEN=... plnt

plnt init hello-desk                     # scaffold a bundle: skill.toml, prompt.md,
                                         # config_schema.json, tools/hours.py
plnt run ./hello-desk "when are you open?" --config business_name=Acme
```

Serve it to many customers, each with its own config, secrets, model and data:

```bash
export PLNT_ADMIN_TOKEN=$(openssl rand -hex 16)
plnt serve --port 8787 &

H="Authorization: Bearer $PLNT_ADMIN_TOKEN"
curl -s -X POST localhost:8787/v1/tenants -H "$H" -d '{"id":"bistro"}' -H 'content-type: application/json'
#  -> {"tenant": {...}, "api_key": "pk_..."}   the tenant's own key, shown once

K="Authorization: Bearer pk_..."
curl -s -X POST localhost:8787/v1/tenants/bistro/installs -H "$K" -H 'content-type: application/json' \
  -d '{"bundle":"support-desk","config":{"business_name":"Luigi'"'"'s","handoff_contact":"hi@luigis.example",
       "faq":[{"q":"When are you open?","a":"Tue-Sun 5-11pm"}]}}'
curl -s -X POST localhost:8787/v1/tenants/bistro/sessions -H "$K" -H 'content-type: application/json' \
  -d '{"bundle":"support-desk"}'                                   # -> {"session_id": "s_..."}
curl -s -X POST localhost:8787/v1/tenants/bistro/sessions/s_.../messages -H "$K" \
  -H 'content-type: application/json' -d '{"text":"When are you open?"}'
curl -N localhost:8787/v1/tenants/bistro/sessions/s_.../stream -H "$K"   # live events (SSE)
```

Open `http://localhost:8787/console` for the web console (build it once with
`cd console && npm ci && npm run build`). Every route is listed in
[`plnt/server/app.py`](plnt/server/app.py). `plnt dev [bundle]`
runs the same API on loopback with auth disabled. `python scripts/smoke_platform.py`
runs the whole flow for two tenants end to end.

### Bundles

```
my-agent/
  skill.toml           [meta] name/version · [runtime] tools, max_steps, model_hint ·
                       [budget] tokens, wall_seconds · [secrets] required
  prompt.md            system prompt; {{config.key}} is filled per tenant
  config_schema.json   JSON Schema each tenant's config is validated against
  tools/*.py           @tool functions; a `ctx: ToolContext` parameter gives the tool
                       that tenant's config and secrets
```

```python
from plnt import ToolContext, tool

@tool
def lookup_order(order_id: str, ctx: ToolContext) -> dict:
    """Look up an order by id."""
    return shop_api(ctx.config["shop_url"], ctx.secret("SHOP_API_KEY")).order(order_id)
```

### What each tenant gets

- Its own installed copy of the bundle (pinned version and digest) and validated config.
- Its own secrets (write-only over the API) and, optionally, its own model:
  `PUT /v1/tenants/{t}/model {"provider":"ollama","base_url":"http://gpu-box:11434","model":"qwen2.5:7b"}`.
- Its own sessions, event log, usage/cost ledger (`data.db`) and audit log.
- Filesystem tools confined to its own workdir.
- Runs stopped by the bundle's token and wall-clock budgets, the loop detector, or
  `POST .../sessions/{sid}/kill`.
- Answers that must be grounded stay grounded: with `[runtime] require_tool`, the runtime
  withholds any answer the model gives before calling that tool.
- A private data directory per bundle (`ctx.data_dir`), e.g. booking-desk's ledger.

Custom `tools/*.py` code runs in the server process, so for now install only
bundles you trust. Sandboxed third-party tools are roadmap Phase 6.

## Quickstart (runtime)

```bash
pip install -e ".[dev]"
pytest -q

# Local model (Ollama):
ollama pull qwen2.5:7b
export PLNT_PLANNER_MODEL=qwen2.5:7b
plnt models doctor                        # reachable? pulled? tool calling? JSON? context?
plnt submit "summarise the TODOs in this repo"
```

## Models

plnt picks a model per call: the local endpoint if it is reachable, otherwise the
configured cloud model, otherwise it **fails with a fix-it message**. It never
invents an answer when a model call fails.

| Variable | Meaning |
|---|---|
| `PLNT_LOCAL_URL` | Local server. `http://127.0.0.1:11434` → Ollama native API; a URL ending in `/v1` → OpenAI-compatible (llama.cpp, vLLM, LM Studio) |
| `PLNT_PLANNER_MODEL` / `PLNT_DEEP_MODEL` | Local small / deep model |
| `PLNT_CLOUD_URL`, `PLNT_CLOUD_API_KEY`, `PLNT_CLOUD_SMALL_MODEL`, `PLNT_CLOUD_DEEP_MODEL` | Hosted fallback (any OpenAI-compatible API, e.g. Gemini) |
| `PLNT_FORCE` | `local`, `cloud`, or `offline` (deterministic stub for tests) |
| `PLNT_NUM_CTX` | Context window requested from Ollama (default 8192; Ollama's own default silently truncates agent prompts) |
| `PLNT_NATIVE_TOOLS` | `auto` (default: native tool calling, JSON-schema shim if the model rejects tools), `1`, `0` |
| `PLNT_MODEL_TIMEOUT`, `PLNT_TEMPERATURE`, `PLNT_MAX_TOKENS` | Per-call settings; the timeout is also capped by the agent's remaining wall budget |
| `PLNT_COST_IN_PER_M` / `PLNT_COST_OUT_PER_M` | USD per 1M tokens, for cost accounting in run events |

Tool-calling quality varies a lot between local models, and small ones are
often unreliable. Before relying on one, run `plnt models doctor --model <name>`. It runs
a tool-call probe and a JSON probe against the model you have.

## Quickstart (reference app)

```bash
pip install -e . -e "examples/booking[dev]"
cd examples/booking && pytest -q          # in-process Temporal, no Docker needed
docker compose up -d --build              # full stack; see examples/booking/README.md
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). CI (`.github/workflows/ci.yml`) runs the
runtime tests, the reference app's tests, the console build/lint, and the site
build on every push.

## License

Apache-2.0.
