# Speaking script — what to say

Rehearsed lines for different attention windows. Say the whole thing verbatim
the first two times you use it; after that you own it and can freestyle.

---

## 30-second elevator (for a hallway, a LinkedIn DM, a stranger at a meetup)

> "I'm building the orchestration runtime for small-team agent workflows on
> Kubernetes. Right now every SaaS company builds their own janky
> LLM plumbing — Helm, canary, rollback, GPU scheduling — from scratch. We
> ship it as a pluggable library. Pick a workflow recipe from an open S3
> registry, pick a K8s backend, and our runtime does the rest. There's a
> live playground at plnt.work — you can watch a workflow execute end to end
> in about 15 seconds."

**Beats:** who / what problem / what we ship / where to see it. Nothing else.

---

## 90-second demo intro (before you screenshare)

> "Quick context. Every small SaaS product needs a handful of narrow AI
> features — draft a Google review reply, generate a weekly post, triage a
> booking inquiry. Each one is a tiny agent workflow: three to five steps, a
> couple of tool calls, a GPU somewhere.
>
> Every team builds this bespoke, and none of them want to. There's no
> shared stack — no shared recipe format, no shared runtime.
>
> We're building that stack in three layers:
>
> One: **microagents**, an open registry of workflow recipes on S3 — versioned,
> hash-verified, anyone can pull.
>
> Two: **plnt**, an opinionated Helm-native runtime that takes a recipe plus
> a Kubernetes GPU backend and runs it as a durable Temporal saga — pull,
> resolve, install as a canary, smoke test, promote or rollback.
>
> Three: **the reference consumer** — a Google Business SaaS that uses the
> whole stack in production.
>
> I'll walk you through all three in about three minutes. The end state you'll
> see is a running workflow serving a live Google Business review reply."

**Beats:** the problem is universal → three layers → what you're about to see.

---

## 3-minute walkthrough (screenshare or in-person)

Rehearsed transitions. Rough word counts. Do not over-run.

### Beat 1 — problem (~30s)

> "Take one Google Business owner — a dentist, a plumber, whoever. They get
> reviews, they need to reply. They want AI to draft the reply. Simple
> feature. But under the hood, some engineer has to write: a prompt, a
> retry loop, a rate-limit budget, a container image, a Helm chart, a
> canary rollout, a rollback path, a GPU node request, a smoke test. For
> one feature. Then they're asked to do post generation. Same nine things,
> different prompt. That's the pain."

### Beat 2 — three-layer stack (~30s)

> "Our stack. Bottom to top:
>
> plnt — the runtime. WorkflowRun CRD. Temporal saga. Helm install. Canary.
>
> microagents — the recipe registry. S3 today, OCI tomorrow. Every recipe is
> a `workflow.yaml` plus prompts plus tool bindings. Versioned. Hash-verified.
>
> google-business — the reference SaaS consumer. Uses microagents recipes,
> calls plnt to run them, presents the UI to the end user."

### Beat 3 — kubectl demo (~45s)

> "Watch this. `kubectl apply -f review-responder.yaml`. This YAML says: pull
> the review-responder recipe at version 1.1, run it on the gpu-cluster-01
> backend, canary at 5% traffic, promote when TTFT p95 is under two and a
> half seconds.
>
> [wait for events]
>
> Operator sees the resource, kicks off the Temporal workflow. Pull step —
> hash checked against the registry entry. Helm install canary. [pods appear
> in the terminal.] Smoke test — ten prompts through the canary, latency
> measured. Passes. Promote to 100%. About fifteen seconds end to end on
> kind, faster on real hardware."

### Beat 4 — playground (~30s)

> "That workflow is now live at playground.plnt.work. Any client that speaks
> OpenAI chat completions can hit it. Here's the site — same page as the docs
> — and here I'm sending a real review reply request. Response streams in.
> That's the whole loop. Recipe pulled, runtime installed, canary promoted,
> playground surface serving traffic."

### Beat 5 — why this matters (~30s)

> "The bet: every small SaaS team is going to want AI features and none of
> them want to be K8s experts. We give them a runtime that turns recipes
> into services. They pull a recipe or write one, we handle the plumbing.
> That's the whole product."

### Beat 6 — what's next (~15s)

> "Live today: plnt runtime, playground, first-party charts, deploy runbook.
> Next: three more recipes, real GPU cluster, benchmark harness with
> tokens-per-second-per-GPU numbers you can point at."

---

## Q&A prep — the questions you'll get

### "How is this different from KServe?"

> "KServe is general — supports every backend, you write the YAML per model.
> Great for infra teams that already know K8s inside out. We trade
> KServe's generality for a sharper deploy saga and a shared runtime
> contract. Small teams don't want to write custom InferenceService YAML;
> they want to point at a recipe. That's what plnt is."

### "How is this different from LangChain / LangGraph / CrewAI?"

> "Different layer. Those are Python libraries for building agent logic.
> plnt is the K8s runtime that runs agent workflows in production. You
> could write a LangGraph agent, package it as a microagents recipe, and
> deploy it with plnt. We're the deploy layer, not the compose layer."

### "How is this different from BentoML / Modal / Replicate?"

> "Those are API-first, hosted-first. You upload code, they run it, you pay
> them per second. We're bring-your-own-cluster. You already have K8s, you
> want an opinionated runtime on top of it. Different customer, different
> price model."

### "Why S3 for the registry? Why not OCI?"

> "S3 is where teams already put stuff. Every cloud provider speaks S3.
> Zero new infra to learn. OCI is on the roadmap for teams that already
> operate a container registry, but S3 is the default because it's the
> path of least resistance."

### "How do you make money?"

> "Two paths. Cloud-hosted control plane for teams that don't want to run
> the operator themselves — usage-based pricing. And enterprise support for
> teams running plnt on-prem. The runtime itself is Apache-licensed and
> stays free."

### "What's the moat?"

> "The recipe registry. If microagents becomes the shared vocabulary for
> agent workflows — the way Helm charts became the shared vocabulary for
> K8s apps — then the runtime that ships with the best recipe pull path
> wins. That's the moat we're building toward."

### "What's the biggest risk?"

> "A hyperscaler ships an equivalent OSS product. Real risk. Our defense
> is being opinionated, small-team focused, and shipping the recipe
> registry the hyperscalers haven't bothered with."

### "What's not in the product yet?"

> "Multi-cluster failover. Real per-user auth. Rate limiting at the
> playground surface. A hosted control plane. All planned, none shipped."

### "Who's the team?"

> "Solo founder for now. Sagar. Ex-[whatever the founder wants to say].
> Playground and runtime are running against real code. Not a slide-deck
> company."

### "What do you need?"

> "Feedback on the recipe format from anyone running agent workflows in
> production. Design partners for the reference consumer. And when we're
> ready, seed capital to hire two more."

### "Show me a metric."

> "Fair. Right now the metrics we can point at are: playground time-to-first-
> token under two seconds on the mock backend, kind-to-running-workflow
> under three minutes end-to-end, and the contract test suite is 15/15
> passing on every commit. Real per-workflow metrics land with the
> benchmark harness in v0.4."

---

## Recovery lines — when something goes wrong on stage

- **Demo won't load:** "The playground is at playground.plnt.work and there's
  a static screenshot in the deck — let me pull that up. The mechanics are
  the same either way."
- **Question you can't answer:** "Good question, I don't know. Let me get
  back to you with the actual answer instead of guessing."
- **Someone challenges the positioning:** "That's a fair concern. My working
  answer is [X]. What would change your mind?"
- **Someone asks about revenue with no revenue yet:** "Zero. This is pre-revenue.
  The bet is the runtime becomes load-bearing infrastructure and then a hosted
  control plane is the money-making layer. Happy to walk through the numbers
  if useful."

---

## Do NOT say

- "Mini NIM Factory." Removed. Positioning is agent-workflow orchestration.
- "Multi-model inference platform." Also removed. This is not a model host.
- "AI-powered." Empty word. Say what it actually does.
- "Blazing fast." Empty word. Use measured numbers.
- "Enterprise-ready." Not until it is.
- Any variant of "we're building the future of." Just describe what we ship.

---

## The one sentence you should be able to say cold

> "plnt is the orchestration runtime for small-team agent workflows on Kubernetes."

If you cannot say that sentence at a party after two drinks, you have not
rehearsed enough.
