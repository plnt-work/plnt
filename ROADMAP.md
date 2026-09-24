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

## Phase 1 — Model layer: local models that actually work  `[next]`

- Provider interface (`plnt/models/`): OpenAI-compatible + native Ollama
- Native tool calling (`tools` / `tool_calls`); JSON-schema shim for models without it
- Fail loudly: no silent "echo" fallback when a model call fails
- Health check that the model is actually pulled; `num_ctx` / temperature / max_tokens sent
- `plnt models doctor`
- Token + cost accounting on every call
- Published turn-latency numbers from `bench/turn_latency.py`

## Phase 2 — Bundles, tenancy, API core  `[planned]`

- One bundle format: `skill.toml` + `prompt.md` + `config_schema.json` + tools
- Tenancy in the core: per-tenant store, audit, memory, secrets, usage
- Per-tenant bundle loader (shadowing, semver, disable) and installer with config validation
- In-process executor with a durable SQLite event log; Temporal as an optional extra
- HTTP API: tenants, installs, sessions (SSE), runs, kill, audit, usage
- CLI: `plnt init | dev | run | install | serve | tenants`

## Phase 3 — Console + reference app on the public API  `[planned]`

- Generic console: usage/cost overview, live runs with kill, transcripts, installs with generated config forms, models/secrets/keys
- `examples/booking` uses only public APIs; merchant-configured availability replaces LLM-generated slots

## Phase 4 — Site, real playground, docs, v0.1.0 on PyPI  `[planned]`

- Site rewritten for the platform
- Playground runs real bundles on a hosted `plnt serve`: tenant switcher, live event trace, kill button, isolation demo
- Docs: quickstart, bundle spec, local models guide, deploy guide

## Phase 5 — Registry  `[planned]`

- `registry/index.json` generated in CI; `plnt install <slug>` with sha256 verification; `plnt publish`
- OpenTelemetry traces; Postgres store

## Phase 6 — Hardening  `[planned]`

- Per-tenant Docker rung by default, egress allowlists, rate limits, gVisor rung, eval harness
