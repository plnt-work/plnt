# microagents

**Pluggable workflow recipes for the [plnt](https://github.com/plnt-work/plnt)
runtime.**

An open registry of narrow, reusable agent workflows — 3-5 steps each,
versioned, hostable on any S3-compatible bucket or OCI registry.
`plnt` pulls a recipe by name and runs it as a durable Temporal saga on a
Kubernetes GPU backend.

> Status: placeholder. Recipes and the S3 layout land in v0.2.

---

## Idea

Every small-business SaaS surface needs a handful of narrow AI features —
draft a review reply, generate a weekly post, triage a booking inquiry.
Building each one bespoke is what most teams do and none of them want to.

microagents is the recipe registry side of that stack:

```
storefront-ai  ->  microagents  ->  plnt
end-user           workflow           orchestration
SaaS               recipes            runtime
                   (this repo)
```

- **[storefront-ai](https://github.com/plnt-work/google-business)** —
  reference end-user consumer.
- **microagents** (this repo) — the workflow recipes.
- **[plnt](https://github.com/plnt-work/plnt)** — the runtime that
  pulls a recipe + K8s backend and orchestrates the deploy saga.

## Registry shape (planned)

```
s3://microagents/
  review-responder/
    1.0.0/
      workflow.yaml         # step DAG
      prompts/              # per-step system prompts
      tools.yaml            # tool bindings (HTTP endpoints, function schemas)
      README.md
      LICENSE
    1.1.0/
      ...
  post-generator/
    1.0.0/
      ...
  booking-triage/
    1.0.0/
      ...
```

Each recipe is a self-describing bundle with a `workflow.yaml`:

```yaml
apiVersion: microagents.plnt.work/v1
kind: Workflow
metadata:
  name: review-responder
  version: 1.0.0
  description: Draft a professional reply to a Google Business review
spec:
  steps:
    - id: classify
      model: llama-3.1-70b-instruct
      prompt_ref: prompts/classify.md
    - id: draft
      model: llama-3.1-70b-instruct
      prompt_ref: prompts/draft.md
      depends_on: [classify]
    - id: refine
      model: llama-3.1-70b-instruct
      prompt_ref: prompts/refine.md
      depends_on: [draft]
  gates:
    p95_latency_ms: 2500
    max_cost_usd: 0.02
```

## Consumed by plnt

```yaml
apiVersion: plnt.work/v1
kind: WorkflowRun
metadata:
  name: review-responder-prod
spec:
  workflow:
    ref: review-responder@1.1.0
    registry: s3://microagents
  backend:
    cluster: gpu-cluster-01
    gpuClass: nvidia.com/h100
    gpuCount: 2
```

`plnt` pulls the referenced version, hash-verifies the bundle, Helm-installs
the runtime, canary-tests it, and promotes.

## Roadmap

- v0.1 — this placeholder. Registry format proposal.
- v0.2 — first 3 recipes: `review-responder`, `post-generator`,
  `booking-triage`.
- v0.3 — S3 uploader CLI: `microagents publish ./review-responder`.
- v0.4 — OCI registry backend (Harbor / GHCR).
- v0.5 — hash-attestation via cosign.

## License

Apache-2.0. See [LICENSE](LICENSE).
