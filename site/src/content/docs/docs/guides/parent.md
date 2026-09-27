---
title: The parent and its agents
description: One conversation, many agents. The parent decides per message which agents run, and a run view shows what each did.
---

A session started **without a bundle** is a parent session. The tenant's parent reads each message and decides, in one model call, what it needs:

| Decision | What happens |
| --- | --- |
| `chat` | The parent answers itself. Only for small talk and "what can you do?". |
| `clarify` | The parent asks one pointed question before doing anything. |
| `agents` | The parent spawns 1 to 4 agents, each with an intent in the customer's words. |

The agents are the tenant's **installed bundles** ("specialists"): the parent is told each one's description and tools, and it never answers a question a specialist exists for. Agents without dependencies run in parallel; an agent with `depends_on` waits and gets the upstream results in its prompt. When more than one agent ran, a second model call merges their answers into the single reply the customer sees. One agent's answer is relayed verbatim.

```bash
# a session with no bundle: the parent decides
curl -X POST http://127.0.0.1:8787/v1/tenants/luigis/sessions \
  -H "authorization: Bearer $KEY" -H 'content-type: application/json' -d '{}'
```

Everything the parent does is recorded as events with `agent_id = "parent"`; everything an agent does carries that agent's id. [Events](/docs/reference/events/) lists the kinds. The [transcript](/docs/reference/transcript/) endpoint folds them into turns for a run view: the decision and its reason, the plan, one card per agent (spec, tool calls, tokens, status, answer) and the reply.

## What the customer sees

Only the reply. The decision, the plan and the agent cards are for the operator: the console's **Conversations** tab and the [playground](/playground) show them under each message, and the playground's live trace shows the raw events as they happen.

## Invented roles

By default the parent may only run installed bundles. If nothing fits, it answers with `chat` and says what the installed agents can help with. Set `PLNT_PARENT_DYNAMIC_ROLES=1` to let it invent a single-purpose role (`bundle: null`) for the gap; such a role runs with only the built-in `search` and `execute` tools, inside the conversation's working folder.

## Limits

- At most 4 agents per message (`MAX_AGENTS`), at most `PLNT_MAX_CONCURRENCY` (default 3) running at once.
- Each agent keeps its bundle's own budget, guardrails and `require_tool`.
- Usage is attributed per agent: the parent's two calls under `parent`, each bundle under its slug, an invented role under `role:<name>`.
- Kill stops the running agents and skips the ones not started yet; the turn ends with `run_error` (`stopped: killed`).
