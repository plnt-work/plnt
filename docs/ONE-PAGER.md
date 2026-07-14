---
title: "plnt"
subtitle: "Orchestration runtime for small-team agent workflows on Kubernetes"
date: "2026-07-15"
author: "Sagar Bonde"
---

# plnt

**Orchestration runtime for small-team agent workflows on Kubernetes.**

Live: [plnt.work](https://plnt.work) · [plnt.work/playground](https://plnt.work/playground)
· [github.com/plnt-work](https://github.com/plnt-work)

## Problem

Every small SaaS product needs a handful of narrow AI features: draft a Google
review reply, generate a weekly post, triage a booking inquiry. Each one is a
tiny agent workflow — 3-5 steps, a couple of tool calls, a GPU somewhere.

Every team builds it bespoke. Nine hidden pieces per feature: prompt, retry
loop, rate limit, container image, Helm chart, canary rollout, rollback path,
GPU node request, smoke test. There is no shared recipe format. No shared
runtime. So the same nine things get reinvented for every feature, at every
team. It is the K8s equivalent of pre-Rails web development.

## Solution — three layers

1. **microagents** ([github.com/plnt-work/microagents](https://github.com/plnt-work/microagents))
   — an open registry of workflow recipes on S3. Versioned, hash-verified,
   anyone can pull. Each recipe is a `workflow.yaml` plus prompts plus tool
   bindings.
2. **plnt** ([github.com/plnt-work/plnt](https://github.com/plnt-work/plnt))
   — the Helm-native runtime. Reads a `WorkflowRun` CRD, kicks off a Temporal
   saga: pull recipe -> resolve backend -> Helm install as canary -> smoke
   test -> promote or rollback.
3. **google-business** ([github.com/plnt-work/google-business](https://github.com/plnt-work/google-business))
   — the reference SaaS consumer. Google Business owner-facing product. Uses
   microagents recipes, calls plnt to run them, ships the UI.

## Why now

- Every product team is building AI features. Every one of them is stuck at
  the deploy layer.
- vLLM, TGI, SGLang, llama.cpp-server all speak the same wire format
  (OpenAI-compat) as of the last 18 months. The runtime contract is finally
  stable enough to abstract over.
- Kubernetes is the terminal state for infra in most teams that need GPUs.
  Anything not K8s-native is a temporary bet.
- Small teams cannot afford dedicated MLOps hires. They need an opinionated
  runtime that just works.

## Traction

- **v0.1 shipped.** Playground API + Helm chart + DigitalOcean deploy path
  + Fly.io alt + CLI + 15 passing contract tests.
- **Live playground** at `plnt.work/playground` — real chat surface, real
  streaming, real deploys.
- **4 repos live** under [github.com/plnt-work](https://github.com/plnt-work):
  runtime, site, reference SaaS, recipe registry.
- **Full 12-doc portal** — PRD, ERD, architecture, threat model, runbook.
  Enterprise-shape documentation on day one.

## What's next (v0.2 — next 2 weeks)

- vLLM runtime chart green on a real single-GPU cluster.
- First 3 shipping recipes: `review-responder`, `post-generator`,
  `booking-triage`.
- Bench harness — TTFT p95, tokens/sec/GPU numbers you can point at.
- Single-tenant DigitalOcean K8s deploy for the initial customer cohort;
  multi-tenant is a v1.0 concern.

## Market

- **Direct competition:** KServe (too general, no recipe layer), BentoML /
  Modal / Replicate (API-first, hosted-first, wrong deployment model for
  BYO-cluster teams).
- **Adjacent tools:** LangChain / LangGraph / CrewAI compose agent logic
  in Python; plnt is the K8s runtime that runs those agents in production.
  Complementary, not competitive.
- **TAM signal:** every SaaS team building AI features is in the market.

## Business model

- Apache-2.0 runtime, forever free.
- Hosted control plane for teams that want plnt without operating the
  operator themselves — usage-based pricing.
- Enterprise support for on-prem deployments.

## Team

- **Sagar Bonde** — Founder. [github.com/sagarb27](https://github.com/sagarb27)

## Ask

- **Design partners** running agent workflows in production — feedback on
  the recipe format.
- **Seed capital** when we're ready to hire two more, for the reference
  consumer buildout and the hosted control plane.

## One sentence

> plnt is the orchestration runtime for small-team agent workflows on Kubernetes.
