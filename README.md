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
  compute/            model backend selection  (being replaced in roadmap Phase 1)
  surface/            local HTTP server + CLI surface
skills/               built-in agent bundles
tests/                runtime tests
examples/booking/     reference multi-tenant app: bookings + Q&A agents, React console,
                      Temporal sessions (formerly github.com/plnt-work/maps-micro-saas)
site/                 plnt.work marketing site + docs (formerly devdattatalele/plnt-site)
registry/             agent bundle registry (formerly github.com/plnt-work/microagents)
bench/                runtime overhead benchmark
```

All four former repositories were imported with full git history
(`git log -- examples/booking`, `git log -- site`, `git log -- registry`).

## Quickstart (runtime)

```bash
pip install -e ".[dev]"
pytest -q

# Local model (Ollama):
ollama pull llama3.2:3b
plnt up                                   # local surface on 127.0.0.1:7777
plnt submit "summarise the TODOs in this repo"
```

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
