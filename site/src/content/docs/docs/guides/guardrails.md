---
title: Guardrails and budgets
description: Limits the runtime enforces on every run, whatever the model does.
---

These limits are enforced by the runtime, not by the prompt. A model can ignore a prompt. It cannot ignore these.

## Required tool: look before you answer

Small models often answer from memory instead of looking. A reviewer that "finds" a bug in a file it never opened is worse than no reviewer. The shipped bundles all require a look first:

```toml
[runtime]
tools = ["list_files", "read_file", "search"]
require_tool = "read_file"
```

With `require_tool` set:

1. If the backend supports forced tool choice, the first model call is made with `tool_choice` set to that tool.
2. If the model still answers without calling it, the runtime **drops the answer**, records a `guardrail` event with `action: "reprompt"`, and tells the model to call the tool.
3. If the model skips it a second time, the runtime records `action: "refused"` and ends the run with an error. **No answer is sent.** The event includes the answer that was withheld, so you can see what it would have said.

In our CI a 1.5B local model skips the read on the first try more often than not; the reprompt fixes most of those, and the rest are withheld rather than sent. If you see many refusals, the model is too weak for the bundle: run `plnt models doctor` and try a larger one.

## Read-only mode

`PLNT_READ_ONLY=1` (on by default for the playground) removes `write_file` and `execute` from every agent, installed or invented, before the model sees its tools. `agent_spawned` events carry `read_only: true` so a run view can say so. Use it wherever people you do not know can start sessions.

## Budgets

Per agent, from its bundle (or the `PLNT_AGENT_*` defaults for invented roles):

```toml
[budget]
tokens = 30000       # prompt + completion tokens, per message
wall_seconds = 180   # per message
```

- **Tokens:** counted after every model call. Past the limit, the run is stopped (`killed` event, `run_error` with `stopped: "killed"`).
- **Wall time:** each model call's timeout is capped at the time left. When the time is up, the run stops with `stopped: "wall_budget"`.
- **Steps:** `[runtime] max_steps` caps model calls per message (`stopped: "max_steps"`).

## Loop detector

If a run makes the same tool call with the same arguments three times, it is stopped. This catches the most common way small models waste a budget.

## Kill switch

Stop a run in flight:

```bash
curl -X POST $API/tenants/acme/sessions/$SID/kill -H "$AUTH"
```

Running agents stop before their next model or tool call and record `killed`; agents the parent planned but had not started are recorded as `agent_finished` with `outcome: skipped`. The console and the [playground](/playground) have a **Kill run** button.

## The parent's limits

At most 4 agents per message, at most `PLNT_MAX_CONCURRENCY` (3) running at once, and only installed bundles unless invented roles are on. See [The parent and its agents](/docs/guides/parent/).

## Model errors are errors

If the model server is down, the model isn't pulled, or the API key is wrong, the run ends with a `model_error` event and a `run_error` carrying a `hint` with the fix. plnt never substitutes a canned reply.
