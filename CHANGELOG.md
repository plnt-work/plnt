# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Dates are ISO-8601, UTC.

## [Unreleased]

### Changed

- **Design pass on the site, playground and console** (lessons from a design teardown):
  - Contrast: every text colour now passes WCAG AA. Muted text, status colours and the
    primary button text were darkened, and a text-safe orange (`--accent-text`) is used for
    orange text; the bright orange is for shapes only. `scripts/check_contrast.py` enforces
    it in CI. Rules are written down in `design/README.md`.
  - One radius multiplier and an 11px type floor in `design/tokens.css`.
  - One brand mark everywhere (site, docs, favicon, console), plus a PNG OG image,
    apple-touch-icon, `theme-color`, and the right sitemap domain in `robots.txt`.
  - The home page replay renders the recorded run on the server, so it reads without
    JavaScript, and does not autoplay under reduced motion. The playground explains itself
    in a `<noscript>`. Section heads use numbered eyebrows; "How a run works" and the
    guardrails are hairline index rows.
  - Honest states: unknown values show "—" (never `undefined`, `?` or a fake 0); the
    console has loading states for the transcript, usage and sign-in, tells a server error
    from a logout, lists bundles that failed to load, and its event stream reconnects with
    a Live / Reconnecting status light (the playground has the same light). Rate limits and
    a spent daily budget get their own notice, and a failed kill is reported.
  - No dead controls: disabled buttons say why, deleting a secret says what breaks, the
    console's "clear view" button is gone, and agent specs open with a native disclosure.
  - Touch targets are 44px on coarse pointers, one focus ring style, plan pills carry a
    status mark (not colour alone), and every page and console tab fits 375px.
  - The PR template has a UI checklist.

### Added

- Sessions can be bound to a **workspace**: `demo:<name>`, a local folder, or a git URL.
  A private copy lands in the session's working folder and that is what the agents
  work on. `POST /v1/tenants/{t}/sessions` takes `workspace`; sessions carry `title`
  (the first message), `workspace` and `workspace_kind`.
- Built-in tools `list_files`, `read_file` and `write_file` next to `search` and
  `execute`; bundles name them in `[runtime] tools`. `ToolContext.workdir` gives a
  bundle's own tools the same folder.
- Four developer bundles: `code-reviewer`, `test-writer`, `repo-explainer`,
  `changelog-writer`.
- Executor policy: `read_only` (strips `write_file`/`execute`), `allow_local_paths`,
  `allow_git`, `dynamic_roles`; `plnt dev` turns invented roles on.
- Two demo workspaces (`demo/workspaces/notes-api`, `cli-tool`) shipped in the wheel and
  the image; the playground runs on them, read-only, one copy per visitor session.
- Design tokens (`design/tokens.css`) shared by the console and the site: warm off-white,
  one orange accent, mono uppercase labels.
- Console **Sessions** (was Conversations): titled sessions with a workspace, and a session
  view with Run / Agents / Files / Events tabs. The transcript records the files each agent
  touched.
- Playground rebuilt as a sessions app (sidebar, header with agents / messages / elapsed,
  the same four tabs); `?tenant=&task=` presets a session.
- Site: landing rebuilt around the parent and its micro-agents with a recorded real run
  replayed; a use-cases page; docs rewritten for developer tasks, with new Workspaces and
  shipped-bundles guides.

### Changed

- The parent's prompts talk about a user and a workspace, not a customer and a
  business. `decide()`/`synthesize()` take `context=` instead of `business=`.
- The bundle catalog no longer scans the legacy `skills/` folder.
- `booking-desk` and `support-desk` moved to `examples/booking/bundles/`; they are no longer
  in the shipped catalog (`PLNT_BUNDLE_PATH` makes them installable).
- The playground's demo tenants are `notes-api` and `cli-tool`; `MAX_MESSAGE_CHARS` is 1000.

### Fixed

- OpenAI-compatible calls retry temporary server errors (429, 500, 502, 503, 504) twice,
  with backoff, within the call's time budget. A server that keeps failing is still
  reported. Gemini occasionally returns `500 INTERNAL` on requests that succeed on retry.
- With `PLNT_FORCE=cloud`, the error names which `PLNT_CLOUD_*` settings are missing.

### Added

- `GET /` returns a map of the server's endpoints, not a 404.
- `plnt serve` logs whether playground mode is on and which origins it allows.
- The site's playground tells "server unreachable" apart from "server up but playground
  off or origin not allowed", and names the setting to fix.

### Added

- `render.yaml`: a Render Blueprint that hosts the public playground. It runs the
  Docker image with Gemini 2.5 Flash, a 1M-tokens-a-day cap, `plnt.work`-only CORS,
  no admin token, and deploys only after CI passes.
- `plnt serve` reads `PORT`, `PLNT_HOST` and `PLNT_PLAYGROUND` from the environment.
  The Docker image honours a platform-assigned `PORT`.

### Fixed

- OpenAI-compatible servers that accept tools but reject a named `tool_choice` now
  get one retry with `"auto"`, which is then remembered per endpoint and model. The
  `require_tool` guardrail still re-asks, or withholds the answer, if the model skips
  the tool.

## [0.1.0] — 2026-09-25

First release of plnt as a platform for shipping one agent to many customers.

### Added

- **Public playground API** (`plnt serve --playground`). It seeds two demo businesses
  and opens an anonymous API limited to them, with a per-session capability token,
  per-IP rate limits, a daily token cap, and CORS.
- **Website** rewritten for the platform. `/playground` talks to a real server,
  with a tenant switcher, a live event trace and a kill button. When the server
  is unreachable, the page says so.
- **Docs** at `/docs/`:
  - quickstart and concepts;
  - guides for bundles, tools, config and secrets, guardrails, local models,
    multi-tenant serving, the console, and deploy;
  - reference for the HTTP API, events, `skill.toml`, the CLI, and environment variables.
- **Packaging:**
  - the wheel includes the built console and the `support-desk` and `booking-desk`
    bundles (`plnt/_bundles`);
  - `scripts/check_dist.sh` installs the wheel in a clean venv and runs an agent.
- **`Dockerfile`** for `plnt serve` with the console. It runs as non-root, keeps its
  state in `/data`, and has a healthcheck.
- **`release.yml`**: a tag `vX.Y.Z` publishes to PyPI (trusted publishing), pushes a
  GHCR image, and creates a GitHub release.
- **CI:** browser end-to-end tests of the site playground, package checks (wheel and
  sdist), and a Docker image smoke test.

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

## [0.0.1] — 2026-07-14 (retired prototype, never published)

The earlier Kubernetes inference prototype. The package version was 0.0.1; this entry
was previously labelled 0.1.0. None of it is in the current release.

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
