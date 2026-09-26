---
title: What plnt is
description: An open-source runtime for shipping one AI agent to many customers, each isolated, on any model.
---

plnt runs **one agent for many customers** and keeps each customer separate.

You write the agent once, as a **bundle**: a prompt, a settings schema, and Python tools. Then you install it for each customer (a **tenant**) with that customer's own settings. Every tenant gets its own:

- **install and config**: a frozen copy of the bundle, validated against its JSON Schema
- **model**: the server default, a hosted API, or the customer's own Ollama/vLLM box
- **secrets**: write-only; your tools can read them, the API never returns them
- **data**: a private directory per bundle, plus its own sessions, event log and usage in its own SQLite database
- **limits**: token and wall-clock budgets per message, a loop detector, and a kill switch
- **audit log**: append-only record of installs, config changes, model changes and runs

One HTTP API serves all tenants. A web console lets you, or each customer with their own key, see conversations, usage and cost.

## Who it's for

Agencies and SaaS teams who build an agent (support desk, booking desk, intake form, order status) and then need to run it for dozens or thousands of businesses. The agent logic is the same for each business; the settings, credentials, data and bill differ. plnt handles the second part.

## What it is not

- **Not a framework for one agent.** If you have one agent for one company, a library like the OpenAI Agents SDK or LangGraph is simpler.
- **Not a sandbox for untrusted code, yet.** Bundle tools run inside the server process. Only install bundles you trust. Sandboxed third-party tools are on the [roadmap](https://github.com/plnt-work/plnt/blob/main/ROADMAP.md).
- **Not production-proven.** This is version 0.1, pre-alpha. The storage is SQLite and files on one machine.

## Next

- [Quickstart](/docs/getting-started/quickstart/): run an agent in five minutes.
- [Concepts](/docs/getting-started/concepts/): bundles, tenants, installs, sessions, runs.
- [Playground](/playground): chat with two demo customers running the same agent.
