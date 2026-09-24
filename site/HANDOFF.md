# HANDOFF — plnt-site rebrand to plnt.work

Paste this into a fresh Claude Code session running in `/Users/dev16/Documents/den-agent/plnt-site`.

---

## Context (read this first)

**What the site used to be:** the marketing + docs surface for **plnt** as a "personal local native twin" — a local-first agent runtime. Astro + Starlight, terminal-green brand, mono typography, static + zero-JS landing. See `README.md`. Existing pages: `index.astro`, `architecture.astro`, `roadmap.astro`, `resources.astro`.

**What the site is becoming:** the marketing + docs surface for **plnt at plnt.work** — a **playground platform for deploying multiple ML inference models on Kubernetes** (Helm charts + Temporal workflow layer + `InferenceModel` CRD + operator). Sister platform repo at `/Users/dev16/Documents/den-agent/plnt`. Sister demo product at `/Users/dev16/Documents/den-agent/plnt-cloud`.

**Why the rebrand:** the site is being aimed as the presentable artifact for a **NVIDIA — Senior Software Engineer, NIM Factory Container and Cloud Infrastructure** interview (Santa Clara, JR2003580). Interviewer visits plnt.work → sees a platform pitch that maps 1:1 to the job description (container strategy for inference microservices, Python tooling for build orchestration, Helm/Operator automation, K8s GPU workloads, multi-tenant multi-cluster delivery).

## What to preserve

- **The aesthetic.** Terminal-green brand, mono-only typography, static-first, zero-JS landing. Do not add tracking, do not add fancy animations.
- **Astro + Starlight stack.** Not migrating frameworks.
- **The four-plane diagram concept**, but replace the *content* of the planes. It was Surface/Control/Execution/Compute for a local twin; the new mental model is CLI+API / Helm+Charts / Temporal workflows / K8s+Operators. Preserve the visual grammar (spawn-tree, ASCII texture, key choices, flow steps).

## What to change

**Landing (`src/pages/index.astro`):**
- New tagline. Suggested: *"plnt — deploy multi-model inference on Kubernetes. Helm charts. Temporal workflows. Zero orchestration overhead."*
- Sub-hero: three key primitives visible above the fold — Helm charts for runtimes (vLLM / TGI / TRT-LLM / SGLang), Temporal deploy sagas, `InferenceModel` CRD + operator.
- Kill the "runs on your laptop" framing. New framing is "runs on a Kubernetes cluster you already have — kind for demo, real GPU clusters for prod."
- Keep the install/quickstart section, but the quickstart is now `helm install` + `kubectl apply -f examples/llama-70b.yaml` instead of `plnt submit`.

**Architecture (`src/pages/architecture.astro`):**
- Replace the current 9-section deep dive with a new architecture story:
  1. **Why K8s + Helm** — declarative, versioned, reproducible; multi-tenant native.
  2. **Helm chart per runtime** — one chart per inference backend (vLLM, TGI, TRT-LLM, SGLang). Values.yaml controls model / GPU / replicas.
  3. **Temporal deploy saga** — validate → pull weights → helm install canary → smoke test → promote or rollback. Compensation on failure.
  4. **InferenceModel CRD + operator** — Kubebuilder-style; `kubectl apply -f llama-70b.yaml` is the entire deploy trigger.
  5. **RuntimeAdapter abstraction** — same interface across vLLM / TGI / TRT-LLM / SGLang so the Helm charts share a control API.
  6. **Retry + circuit breaker layer** — retry budgets at the edge (Envoy), NOT per hop. Google SRE playbook.
  7. **Model artifact registry** — safetensors + content-addressable storage; quantization variants (FP16 / FP8 / AWQ / GPTQ) tracked as peer registry entries.
  8. **Benchmarking** — TTFT p50/p95/p99, TPOT, tokens/sec/GPU, KV cache utilization %. The metrics that prove you operated the cluster.
  9. **plnt-cloud** — a bookings product built on plnt. The platform serves the LLM that powers the chat. Proof the platform works end-to-end.

**Roadmap (`src/pages/roadmap.astro`):**
- Replace with the 6-phase build plan from the platform HANDOFF (skeleton → first Helm chart → deploy saga → CRD+operator → CLI → benchmarking).
- Mark phases honestly: "shipped", "in progress", "planned".

**Resources (`src/pages/resources.astro`):**
- Repo links: platform at `github.com/devdattatalele/plnt` (rename if needed), demo product at `github.com/devdattatalele/google-business-microagent` (this is currently plnt-cloud).
- Reading list: vLLM paper, KServe docs, Temporal + K8s patterns, Google SRE cascading-failures chapter, MLflow model registry, NVIDIA container toolkit.

**Docs portal (`src/content/docs/docs/`):**
- Kill the personal-runtime docs. New Starlight docs sections:
  - **getting-started** — install plnt CLI, deploy your first model on kind, verify with a curl request.
  - **concepts** — Helm charts, Temporal workflows, InferenceModel CRD, RuntimeAdapter, benchmarking.
  - **reference** — CLI reference, chart values reference, CRD field reference.
- Preserve the Starlight styling / overrides (`starlight-overrides.css`).

## Copy voice

- Terse. No marketing fluff. Direct and technical.
- No fake stats ("10× faster") unless we have real benchmark numbers to back them.
- Terminal-shell mental model — the reader is a senior engineer, treat them like one.

## What NOT to touch

- `astro.config.mjs`, `astro.app.config.mjs`, `package.json` unless a real change is needed.
- The `dist/` directory (build artifact).
- The scripts/gen-ascii.mjs and the ASCII texture — keep the visual grammar.
- The Apache-2.0 license.

## First task in the new session

1. Read `src/pages/index.astro` fully.
2. Draft the new hero copy (tagline + sub-hero + three primitives) inline in a message BEFORE writing it. Get the user's sign-off on the copy.
3. Only then start editing the file. Preserve the component structure (SpawnTree, CreamCard, MetaRow, etc.) — reuse the existing components, replace only the content strings.
4. `npm run dev` and screenshot the result. Iterate.

## Domain

`plnt.work` — user owns it. When ready, wire `site:` in `astro.config.mjs` to `https://plnt.work`. Deploy target: Vercel / Netlify / Cloudflare Pages (any static host).
