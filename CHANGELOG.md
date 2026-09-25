# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Dates are ISO-8601, UTC.

## [Unreleased]

### Changed

- **Direction:** plnt is now an open-source runtime for shipping one agent to many
  isolated tenants. The repository is a monorepo: `examples/booking`
  (was maps-micro-saas), `site` (was plnt-site), and `registry` (was microagents),
  each imported with full history.
- **Model layer rewritten** (`plnt/models/`). There are native Ollama (`/api/chat`, with
  `num_ctx`) and OpenAI-compatible providers. Tools use native calling, with a
  JSON-schema shim for models that reject tools. Errors are typed and carry a fix-it hint.
  Every call records tokens and cost.
- **Agent loop** (`plnt/agent/`) follows the tool-calling message protocol and
  caps each model call by the remaining wall budget. `execution/runner.py` uses it.
- Model selection honours `PLNT_FORCE`. The Docker sandbox rewrites loopback model
  URLs to `host.docker.internal`.

### Added

- **Guardrail `[runtime] require_tool`.** The model must call the named tool before it
  answers. The runtime forces the call where the backend supports it, otherwise
  re-asks once, then withholds the answer. Added `tool_choice` to providers.
- **Web console** (`console/`, served at `/console`) and `GET /v1/whoami`, with a Playwright
  end-to-end test in CI.
- **`booking-desk` bundle.** Schedule-driven availability, a per-tenant bookings ledger, and
  atomic, idempotent booking. `ToolContext.data_dir` gives each tenant and bundle
  private storage.
- **Multi-tenant platform core.**
  - Bundles (`plnt/bundles`): manifest, JSON-Schema tenant config, `{{config.x}}` prompts, and an
    `@tool` SDK with `ToolContext` for config and secrets.
  - Tenancy (`plnt/tenancy`): tenants, hashed API keys, secrets, per-tenant model, installs,
    SQLite sessions, event log, usage ledger, and audit.
  - `LocalExecutor`: budgets, loop detector and kill.
  - HTTP API (`plnt serve`) with fail-closed auth and SSE.
- CLI: `plnt init`, `plnt run`, `plnt install`, `plnt tenants`, `plnt serve`, `plnt dev`.
- Example bundle `registry/bundles/support-desk`, and an end-to-end check `scripts/smoke_platform.py`.
- `plnt models doctor` and `plnt models list`.
- CI (`ci.yml`), and a real-Ollama job (`local-models.yml`).

### Removed

- The silent "echo" fallback when a model call fails. With no model configured,
  runs now emit `model_error`. `PLNT_FORCE=offline` selects the deterministic stub
  explicitly.
- The free-text `TOOL:` / `FINAL:` tool protocol.
- The K8s inference playground, operator, Helm charts, deploy overlays, Fly config,
  Go TUI, Expo app, and `plnt deploy` / `plnt playground` commands (recoverable from git history).

## [0.1.0] — 2026-07-14

Initial platform release. Ships the playground surface end-to-end and
scaffolds the runtime, workflow, and operator layers so v0.2 can iterate
in-place.

### Added

- **Playground API** (`plnt/playground/`) — FastAPI, OpenAI-compat
 `GET /v1/models` + `POST /v1/chat/completions` (streaming + non-streaming),
 `/healthz`, `/readyz`.
- **Backends** — `MockBackend` (deterministic echo, SSE streaming) and
 `HTTPBackend` (proxies to any OpenAI-compat upstream: vLLM, TGI,
 SGLang, llama.cpp server).
- **Registry** — ConfigMap-driven model list; env vars
 `PLNT_PLAYGROUND_MODELS` (inline JSON) and `PLNT_PLAYGROUND_CONFIG`
 (path).
- **CORS** — env-driven allowlist via `PLNT_PLAYGROUND_CORS_ORIGINS`;
 defaults cover plnt.work + playground.plnt.work + local Astro/React dev ports.
- **Container image** — `docker/playground-api.Dockerfile`, non-root,
 read-only rootfs, healthcheck. ~150 MB.
- **Helm chart** — `plnt/charts/playground-api` with Deployment, Service,
 ConfigMap, Ingress (SSE-safe nginx annotations), HPA, imagePullSecrets.
- **DigitalOcean K8s deploy overlay** — `deploy/do-k8s/{values-do.yaml,cert-issuer.yaml}`.
- **Deploy runbook** — `deploy/RUNBOOK-do-k8s.md`, 11 steps, ~40 min, ~$24/mo.
- **Fly.io deploy path** — `fly.toml`, `.dockerignore`; alternative to K8s.
- **CLI subcommands** — `plnt playground {up, models, chat, curl}` +
 `plnt deploy <name> --model <ref>` (renders InferenceModel manifest,
 optional `--apply`).
- **Contract test** — `tests/test_site_contract.py` pins the exact wire
 shapes plnt-site's `api.ts` consumes (CORS preflight + SSE frame shape).
- **Docs** — README rewrite; docs/{getting-started, api-contract,
 local-dev, architecture, PRD, PRD-playground, ERD}.
- **Scaffolds for v0.2+** — `plnt/charts/vllm-runtime/`,
 `plnt/operators/` (CRD + controller), `plnt/workflows/` (Temporal
 deploy saga + activities + worker), `examples/llama-3.1-70b-instruct.yaml`.

### Origin story

The pre-existing personal-runtime code under
`plnt/{surface, control, execution, compute, memory}` and `plnt-tui/`
still builds and runs. `plnt up`, `plnt submit`, `plnt runs`, etc. still
work. It is frozen as origin story — see [`ARCHITECTURE.md`](ARCHITECTURE.md).

[Unreleased]: https://github.com/plnt-work/plnt/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/plnt-work/plnt/releases/tag/v0.1.0
