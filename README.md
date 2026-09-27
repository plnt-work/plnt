# plnt

**A task in. Micro-agents out.**

plnt is an open-source runtime where a **parent agent** takes a task on a
repository, decides which **micro-agents** to create and what each should do,
runs them isolated on a private copy of the **workspace**, and merges the result
into one reply. Every decision, spec, file read, model call and token is on the
record, streamed live and folded into a transcript. It serves many tenants from
one process, each with its own installs, secrets, model, sessions, usage and
audit log, on a hosted model or one running on the tenant's own hardware.

> **Status: pre-alpha (0.1).** The parent, the four developer bundles,
> workspaces, the multi-tenant API, the console and the playground are built and
> tested in CI, including against a real local model. Bundle tool code runs in
> the server process, so only install bundles you trust. What is next is in
> [ROADMAP.md](ROADMAP.md).

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Site and docs: **https://plnt.work** · try it on a demo repo: **https://plnt.work/playground**

## How a run works

1. **A task on a workspace.** `demo:notes-api`, a local folder, or a git URL. A private copy is made per session.
2. **The parent decides.** One structured model call: answer, ask, or spawn 1 to 4 agents, each with a bundle, an intent in your words, and what it depends on. Recorded with its reason.
3. **Agents run isolated.** Independent agents in parallel, dependent ones after their inputs. Each with its own tools, budget and `require_tool`, on the session's copy. Read-only mode strips `write_file` and `execute`.
4. **One reply, full trace.** The parent merges the answers. The console and the playground show the plan, every agent's spec, steps, files and tokens.

## Quickstart

```bash
pip install "git+https://github.com/plnt-work/plnt"   # `pip install plnt` once v0.1.0 is on PyPI
ollama pull qwen2.5:7b && export PLNT_PLANNER_MODEL=qwen2.5:7b   # or PLNT_CLOUD_URL / _API_KEY / _SMALL_MODEL
plnt models doctor                                    # reachable? pulled? tool calling? JSON? context?

# one agent on your repo
plnt run code-reviewer "review src/auth.py for bugs" --workspace ~/src/my-project

# a parent session: the parent picks among the installed bundles
plnt install code-reviewer --tenant dev && plnt install test-writer --tenant dev
plnt dev repo-explainer --workspace ~/src/my-project
# open http://127.0.0.1:8787/console → Sessions → New session → "Audit src/auth.py and write tests for it"
```

Over HTTP:

```bash
API=http://127.0.0.1:8787/v1
SID=$(curl -s -X POST $API/tenants/dev/sessions -H 'content-type: application/json' \
  -d '{"workspace":"'$HOME'/src/my-project"}' | jq -r .session_id)
curl -s -X POST $API/tenants/dev/sessions/$SID/messages -H 'content-type: application/json' \
  -d '{"text":"Audit src/auth.py for bugs and write tests for it."}'
curl -N "$API/tenants/dev/sessions/$SID/stream?until_idle=1"        # live events (SSE)
curl -s $API/tenants/dev/sessions/$SID/transcript | jq .turns[0]    # folded into turns
```

`plnt serve` is the same API with auth on (`PLNT_ADMIN_TOKEN`, per-tenant `pk_…` keys), invented roles off and local folders allowed as workspaces. `python scripts/smoke_platform.py` runs two tenants on two workspaces end to end against a fake model.

## The shipped bundles

| Bundle | Tools | Must call first | Config |
|---|---|---|---|
| `code-reviewer` | list_files, read_file, search | read_file | focus, max_findings, language_hint |
| `test-writer` | + write_file, execute | read_file | framework, test_dir |
| `repo-explainer` | list_files, read_file, search | list_files | audience, max_words |
| `changelog-writer` | + execute | — | style, since |

A bundle is a folder (`skill.toml`, `prompt.md`, `config_schema.json`, optional `tools/*.py` with `@tool` functions that get a `ToolContext`: config, secrets, `data_dir`, `workdir`). `plnt init my-agent` scaffolds one.

## What the runtime enforces

- A private workspace copy per session; the built-in file tools cannot leave it.
- Tools by policy: `PLNT_READ_ONLY=1` strips `write_file`/`execute`; the public playground runs that way.
- `require_tool`: an answer given before the required tool ran is withheld, not sent.
- Token, wall-clock and step budgets per agent, a loop detector, and `POST …/sessions/{sid}/kill`.
- Usage and cost per agent (`parent`, each bundle, `role:<name>` for invented roles); an append-only audit log per tenant.
- A model per tenant: `PUT /v1/tenants/{t}/model {"provider":"ollama","base_url":"http://gpu-box:11434","model":"qwen2.5:7b"}`.

## Repository layout

```
plnt/                 the runtime (Python package `plnt`)
  agent/              the tool-calling loop, the parent (decide / synthesize), built-in file tools
  bundles/            bundle format, @tool SDK, catalog
  tenancy/            tenants, keys, secrets, per-tenant model, installs, sessions, workspaces, usage, audit, transcript
  executors/          runs tenant sessions: parent mode, agents in dependency order, SQLite event log
  server/             multi-tenant HTTP API (`plnt serve`), the console at /console, the playground
  models/             model providers: Ollama (native), OpenAI-compatible, JSON tool shim, doctor
  control/, execution/  the earlier single-user swarm runtime (budgets, ACC kill switch, sandboxes)
registry/bundles/     the four shipped developer bundles
demo/workspaces/      the two sample projects the playground runs on
console/              web console (React): Sessions with Run / Agents / Files / Events, agents, settings, usage, audit
site/                 plnt.work: landing, use cases, playground (Preact), docs (Starlight)
design/tokens.css     the design tokens both apps copy
examples/booking/     the legacy booking app and its bundles (booking-desk, support-desk), kept as an example
tests/, scripts/      runtime tests, smoke, replay recorder, dist check
```

## Developing

```bash
pip install -e ".[dev]"
ruff check plnt && pytest -q
cd console && npm ci && npm run build     # writes plnt/server/console
cd site && npm ci && npm run build
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

## The booking example

`examples/booking` is the earlier booking app (Temporal workflow, map UI) and its two bundles, kept as an example of a domain bundle with its own tools and data. It is not part of the shipped catalog; `PLNT_BUNDLE_PATH=examples/booking/bundles` makes it installable.

```bash
pip install -e . -e "examples/booking[dev]"
cd examples/booking && PLNT_BUNDLE_PATH=$PWD/bundles pytest -q
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). CI (`.github/workflows/ci.yml`) runs the
runtime tests, the reference app's tests, the console build/lint, and the site
build on every push.

## License

Apache-2.0.
