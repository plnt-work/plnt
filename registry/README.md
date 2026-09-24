# microagents

**Pluggable agentic workflows. Pull, plug, deploy.**

microagents is a public registry of small, well-scoped agentic workflow
recipes. Each recipe is a versioned spec + code that any runtime can pull,
mount, and run. Think npm — but the payload is an agent DAG, not a JavaScript
package.

> **Status: alpha.** The pull path (S3 + OCI clients) is spec-defined and
> partially implemented. Publishing is currently a git push + a manual S3
> sync. A proper `microagents publish` CLI is planned Q1 2026.

---

## Why microagents

Every product needs a handful of narrow, reliable AI workflows. If every team
writes those from scratch, we get:

- **Duplicate work** — the 100th team writing a "draft a review reply"
  workflow is not writing anything the previous 99 haven't.
- **Zero reusability** — one team's improvements can't reach any other
  product.
- **No shared safety layer** — every workflow re-implements moderation, PII
  scrubbing, prompt injection defense.

microagents is the shared surface: workflow recipes that anyone can pull,
inspect, fork, and improve. Runtimes like
[plnt](https://github.com/plnt-work/plnt) pull from here and deploy the
recipe to their Kubernetes GPU backend.

## What a workflow looks like

A workflow is a directory with a spec and a runnable module.

```
microagents/workflows/review-responder/
  workflow.yaml     # the spec — steps, tool bindings, GPU requirements
  handler.py        # the actual code the runtime executes
  tests/            # golden inputs + expected outputs
  README.md         # what this workflow does, how to invoke it
```

The spec:

```yaml
apiVersion: microagents.dev/v1
kind: Workflow
metadata:
  name: review-responder
  version: 1.2.0
spec:
  description: Draft an on-brand reply to a Google Business review.
  runtime:
    image: ghcr.io/microagents/runner:0.4.0
    entrypoint: python -m review_responder
  steps:
    - id: classify_intent
      tool: llm.classify
    - id: retrieve_brand_voice
      tool: rag.query
      deps: [classify_intent]
    - id: draft_reply
      tool: llm.generate
      deps: [retrieve_brand_voice]
    - id: safety_check
      tool: policy.moderate
      deps: [draft_reply]
  requirements:
    gpuClass: nvidia.com/h100
    gpuCount: 2
    memoryGiB: 40
```

## Pulling a workflow

Runtimes pull by ref + version, optionally pinning by hash:

```bash
# S3 (default backend)
microagents pull review-responder@1.2.0

# OCI (mirror)
microagents pull oci://ghcr.io/microagents/review-responder:1.2.0

# Verify integrity
microagents verify review-responder@1.2.0 \
  --hash sha256:9a1b3f...
```

The pull path writes the workflow into the caller's working directory. Runtimes
then load `workflow.yaml`, mount the tool bindings, and start the runner
container.

## Workflows in this registry

| Name | Version | Category | Steps |
|------|---------|----------|-------|
| `review-responder` | 1.2.0 | Reviews | 4 |
| `post-generator` | 0.9.1 | Content | 3 |
| `booking-triage` | 0.7.3 | Bookings | 3 |
| `competitor-monitor` | 0.5.2 | Analytics | 4 |

All four are consumed by
[google-business](https://github.com/plnt-work/google-business), the
reference product on top of the plnt stack.

## Publishing a workflow

Today: `git push` + a manual S3 sync (invoked from CI on merge to `main`).

Planned (Q1 2026): `microagents publish` — validates the spec, signs the
tarball, uploads to the S3 backend, and emits an integrity manifest.

## Runtimes

Any runtime that speaks the microagents pull path can use these recipes. The
reference runtime is [plnt](https://github.com/plnt-work/plnt), which
turns a `WorkflowRun` CRD into a running service on Kubernetes.

## Related repos

- [plnt](https://github.com/plnt-work/plnt) — the reference runtime
- [google-business](https://github.com/plnt-work/google-business) — reference
  consumer
- [plnt-site](https://github.com/plnt-work/plnt-site) — marketing site
  for the platform

## License

Apache-2.0.
