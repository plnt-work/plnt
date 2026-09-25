# Roadmap

**Direction:** an open-source runtime for shipping one agent to many isolated
tenants, on any model — local or cloud. Audience: SaaS builders and AI
automation agencies who build an agent once and deploy it to many customers.

**Legend:** `[done]` merged and green in CI · `[wip]` in progress ·
`[next]` starts after the current phase · `[planned]` sequenced, not started

The previous roadmap (Kubernetes inference playground) is retired; it is in
git history.

## Phase 0 — Consolidate  `[done]`

- `[done]` Import maps-micro-saas → `examples/booking`, plnt-site → `site`, microagents → `registry`, history preserved
- `[done]` Reference app builds from the monorepo root (Dockerfile, compose)
- `[done]` One CI for runtime, reference app, console and site
- `[done]` Remove retired code: K8s operator/charts/deploy, mock inference playground, Go TUI, Expo app

## Phase 1 — Model layer: local models that actually work  `[done]`

- `[done]` Provider interface (`plnt/models/`): OpenAI-compatible + native Ollama (`/api/chat`)
- `[done]` Native tool calling (`tools` / `tool_calls`); JSON-schema shim when a model rejects tools
- `[done]` Fail loudly: no silent "echo" fallback; errors carry a fix-it hint
- `[done]` Model-pulled check; `num_ctx` / temperature / max_tokens sent; timeout capped by wall budget
- `[done]` `plnt models doctor` and `plnt models list`
- `[done]` Token + cost accounting on every model call (`model_result` events, run `usage`)
- `[done]` Docker sandbox reaches a host-local model (`host.docker.internal` rewrite)
- `[done]` CI job running a real Ollama model (`.github/workflows/local-models.yml`)
- `[done]` Runtime overhead measured: p50 256 ms / p95 284 ms per single-agent run, no model (`bench/turn_latency.py`, 4 vCPU)

## Phase 2 — Bundles, tenancy, API core  `[done]`

- `[done]` One bundle format: `skill.toml` + `prompt.md` (`{{config.x}}`) + `config_schema.json` + `tools/*.py` (`@tool` SDK with `ToolContext`)
- `[done]` Tenancy in the core: tenants, hashed API keys, secrets (0600, write-only API), per-tenant model (BYO), audit
- `[done]` Per-tenant installs: frozen copy with digest, config validated by JSON Schema, highest enabled semver wins, enable/disable/update/uninstall
- `[done]` In-process executor with a durable per-tenant SQLite event log; token/wall budgets, loop detector and manual kill stop runs
- `[done]` Usage and cost ledger per tenant (every model call)
- `[done]` HTTP API: tenants, keys, installs, secrets, model, sessions, SSE stream, kill, usage, audit; fail-closed auth
- `[done]` CLI: `plnt init | run | install | tenants | serve | dev`
- `[done]` Example bundle `registry/bundles/support-desk`; `scripts/smoke_platform.py` (two tenants, real HTTP, runs in CI and against a real Ollama model)

## Phase 3 — Guardrail, console, booking on the platform  `[done]`

- `[done]` `[runtime] require_tool`: the runtime forces the grounding tool (tool_choice where supported), re-asks once, then withholds the answer. Added after a real 1.5B model invented opening hours in CI
- `[done]` Web console (`console/`, served at `/console`): operator and tenant sign-in; overview with 30-day usage and cost; live conversations over SSE with tool calls, guardrail notes and kill; agents with install and settings forms generated from each bundle's JSON Schema; per-tenant model with health check, secrets, key rotation; audit log
- `[done]` Browser end-to-end test of the console in CI (Playwright), including mobile width
- `[done]` `registry/bundles/booking-desk`: restaurant bookings on the public platform. Availability comes from the merchant's configured hours and capacity (no LLM-made slots); per-tenant ledger via `ctx.data_dir`; atomic, idempotent booking; cancel with contact check
- `[next]` Merchant views of bundle data in the console (e.g. today's bookings)
- `[next]` Retire `examples/booking` (legacy Temporal app) once booking-desk covers it; salon mode
- `[planned]` Temporal executor behind the same interface (`plnt[temporal]`)
- `[planned]` Per-tenant long-term memory

## Phase 4 — Site, real playground, docs, v0.1.0 on PyPI  `[planned]`

- Site rewritten for the platform
- Playground runs real bundles on a hosted `plnt serve`: tenant switcher, live event trace, kill button, isolation demo
- Docs: quickstart, bundle spec, local models guide, deploy guide

## Phase 5 — Registry  `[planned]`

- `registry/index.json` generated in CI; `plnt install <slug>` with sha256 verification; `plnt publish`
- OpenTelemetry traces; Postgres store

## Phase 6 — Hardening  `[planned]`

- Per-tenant Docker rung by default, egress allowlists, rate limits, gVisor rung, eval harness
