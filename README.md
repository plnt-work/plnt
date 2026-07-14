# plnt

**The orchestration runtime for micro-agent workflows.** Pick a workflow spec
from a registry (S3 or OCI), pick a Kubernetes GPU backend, and plnt handles
the Helm deploy, the canary, the smoke test, and the promote-or-rollback — as
a durable Temporal saga.

The live playground is at [plnt.work/playground](https://plnt.work/playground)
— pick a workflow, watch the step DAG execute, invoke it against a live model
endpoint.

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Contract tests](https://img.shields.io/badge/contract%20tests-15%2F15-brightgreen.svg)](tests/test_site_contract.py)
[![Roadmap](https://img.shields.io/badge/roadmap-v0.1--v1.0-informational.svg)](ROADMAP.md)

---

## Why plnt

Every small-business SaaS surface needs a handful of narrow, reliable AI
features — draft a review reply, generate a weekly post, triage a booking
inquiry. Each one is a tiny agent workflow: 3–5 steps, a couple of tool calls,
a GPU somewhere.

Building each one bespoke is what most teams do and none of them want to. The
fix is a stack:

1. A **registry** of workflow recipes anyone can pull —
   [microagents](https://github.com/plnt-work/microagents).
2. A **runtime** that turns a recipe + a backend into a running service — this
   repo.
3. A **product** that consumes the runtime — the reference consumer is
   [storefront-ai](https://github.com/plnt-work/storefront-ai).

plnt is the middle layer. It is the load-bearing infra piece.

## The stack

```
┌────────────────────────────────────┐
│  storefront-ai   (end-user SaaS)   │  reviews · posts · bookings
└───────────────────┬────────────────┘
                    │  invokes
                    ▼
┌────────────────────────────────────┐
│  microagents  (workflow registry)  │  pluggable recipes on S3
│  review-responder · post-generator │
│  booking-triage  · trend-monitor   │
└───────────────────┬────────────────┘
                    │  pulls spec
                    ▼
┌────────────────────────────────────┐
│  plnt  (this repo — runtime)       │  ← you are here
│  WorkflowRun CRD · Temporal saga   │
│  Helm install · canary · rollback  │
└───────────────────┬────────────────┘
                    │  helm install
                    ▼
┌────────────────────────────────────┐
│  Kubernetes GPU backends           │  kind · GKE · EKS · on-prem
│  scheduler · nvidia.com/gpu        │
└────────────────────────────────────┘
```

## What's in this repo

```
plnt/
  playground/      # FastAPI wrapper — /v1/workflows + /v1/chat/completions (live surface)
  charts/          # Helm charts:
                   #   plnt (operator + CRDs), workflow-runner (per-workflow template),
                   #   playground-api (shipped)
  operators/       # kopf controller + WorkflowRun CRD
  workflows/       # Temporal orchestration saga
                   #   OrchestrateWorkflow: pull → resolve → helm → smoke → promote
  registry/        # microagents pull path (S3 + OCI clients, integrity checks)
  runtime/         # RuntimeAdapter Protocol + reference implementations
  cli.py           # `plnt` CLI: run, list, scale, rollback, bench, playground
docker/            # container images (playground API, runner base)
deploy/            # DigitalOcean K8s overlay + cert-manager + runbook; Fly.io alt
docs/              # architecture, PRD, ERD, api-contract, local-dev, observability
tests/             # pytest: playground behavior + contract test vs plnt-site
examples/          # sample WorkflowRun resources + Helm values
```

## 60-second quickstart

```bash
git clone https://github.com/plnt-work/plnt && cd plnt
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
plnt playground up
```

In another terminal:

```bash
plnt list                                   # list registered workflows
plnt run review-responder --backend kind    # orchestrate on local kind
plnt logs review-responder --follow         # tail the Temporal saga
```

Full walkthrough: [docs/getting-started.md](docs/getting-started.md).

## Declarative — one CRD

```yaml
apiVersion: plnt.work/v1
kind: WorkflowRun
metadata:
  name: review-responder
spec:
  workflow:
    ref: review-responder@1.2.0
    registry: s3://microagents
  backend:
    cluster: gpu-cluster-01
    gpuClass: nvidia.com/h100
    gpuCount: 2
  replicas: { min: 1, max: 4 }
  canary:
    trafficPercent: 5
    smokeTest: { invocations: 10, p95BudgetMs: 2500 }
```

```bash
kubectl apply -f review-responder.yaml
```

The operator watches the resource, starts a Temporal workflow, and the saga
takes it from there: pull the spec, resolve the backend, `helm install` a
canary, smoke-test it, promote to stable or roll back. Every state transition
emits a Kubernetes event.

## The saga

```
   pull_spec         resolve_backend       helm_install_canary
       │                    │                        │
       └────────────────────┴────────────────────────┴──▶ run_smoke_test
                                                              │
                                                     pass │      │ fail
                                                          ▼      ▼
                                              promote_to_stable  helm_rollback
```

Every activity has its own retry policy. Non-retryable error types
(`SpecInvalid`, `BackendUnavailable`) short-circuit obvious dead-ends.
Restarts resume from the last completed step.

## Deploy

Reference deployment on DigitalOcean Kubernetes: [deploy/do-k8s/](deploy/do-k8s/).
Fly.io alt for the playground API: [fly.toml](fly.toml).

## Docs

- [Architecture](docs/architecture.md) — the 4-layer stack, saga, CRD, adapter
- [Getting started](docs/getting-started.md) — kind demo end-to-end
- [API contract](docs/api-contract.md) — invocation shape + streaming
- [WorkflowRun CRD reference](docs/workflowrun-crd.md) — full schema
- [Observability](docs/observability.md) — metrics, traces, dashboards

## Related repos

- [microagents](https://github.com/plnt-work/microagents) — the workflow
  registry
- [storefront-ai](https://github.com/plnt-work/storefront-ai) — reference
  consumer (Google Business Profile copilot)
- [plnt-site](https://github.com/plnt-work/plnt-site) — marketing site +
  playground UI at [plnt.work](https://plnt.work)

## License

Apache-2.0. See [LICENSE](LICENSE).
