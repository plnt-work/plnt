---
title: Guardrails and budgets
description: Limits the runtime enforces on every run, whatever the model does.
---

These limits are enforced by the runtime, not by the prompt. A model can ignore a prompt. It cannot ignore these.

## Required tool: no ungrounded answers

Small models often answer from memory instead of looking things up. In our CI, a 1.5B model asked a dental clinic's opening hours answered "8am to 5pm". The clinic's FAQ says 4pm.

```toml
[runtime]
tools = ["lookup_faq"]
require_tool = "lookup_faq"
```

With `require_tool` set:

1. If the backend supports forced tool choice, the first model call is made with `tool_choice` set to that tool.
2. If the model still answers without calling it, the runtime **drops the answer**, records a `guardrail` event with `action: "reprompt"`, and tells the model to call the tool.
3. If the model skips it a second time, the runtime records `action: "refused"` and ends the run with an error. **No answer is sent.** The event includes the answer that was withheld, so you can see what it would have said.

In the same CI run, the reprompt fixed the dental answer ("8 AM to 4 PM"). For the restaurant, the model skipped the lookup twice and the answer was withheld. If you see many refusals, the model is too weak for the bundle: run `plnt models doctor` and try a larger one.

## Budgets

```toml
[budget]
tokens = 8000        # prompt + completion tokens, per message
wall_seconds = 60    # per message
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

The run stops before its next model or tool call and records `killed`. The console has a **Kill** button on live conversations, and the [playground](/playground) has one too.

## Model errors are errors

If the model server is down, the model isn't pulled, or the API key is wrong, the run ends with a `model_error` event and a `run_error` carrying a `hint` with the fix. plnt never substitutes a canned reply.
