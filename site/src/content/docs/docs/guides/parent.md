---
title: The parent and its agents
description: One session, many agents. The parent decides per message which agents run on the workspace, and a run view shows what each did.
---

A session started **without a bundle** is a parent session. The tenant's parent reads each message and decides, in one model call, what it needs:

| Decision | What happens |
| --- | --- |
| `chat` | The parent answers itself. Only for small talk and "what can you do?". |
| `clarify` | The parent asks one pointed question before doing anything. |
| `agents` | The parent spawns 1 to 4 agents, each with an intent in the user's words and, where one needs another's result, a `depends_on`. |

The agents are the tenant's **installed bundles** ("specialists"): the parent is told the tenant, the workspace, and each bundle's description and tools, and it never does work a specialist exists for. Agents without dependencies run in parallel; an agent with `depends_on` waits and gets the upstream results in its prompt. When more than one agent ran, a second model call merges their answers into the single reply the user sees. One agent's answer is relayed verbatim.

```bash
# a session with no bundle, on a workspace: the parent decides
curl -X POST http://127.0.0.1:8787/v1/tenants/acme/sessions \
  -H "authorization: Bearer $KEY" -H 'content-type: application/json' \
  -d '{"workspace": "~/src/api"}'
```

A typical plan for "audit app/store.py for bugs and write tests for it":

```json
{"kind": "agents", "reason": "a review, then tests that depend on it",
 "agents": [
   {"id": "review", "role": "code-reviewer", "bundle": "code-reviewer",
    "intent": "find bugs in app/store.py", "depends_on": []},
   {"id": "tests", "role": "test-writer", "bundle": "test-writer",
    "intent": "write tests for app/store.py", "depends_on": ["review"]}
 ]}
```

Everything the parent does is recorded as events with `agent_id = "parent"`; everything an agent does carries that agent's id. [Events](/docs/reference/events/) lists the kinds. The [transcript](/docs/reference/transcript/) endpoint folds them into turns for a run view: the decision and its reason, the plan, one card per agent (spec, tool calls, tokens, status, answer) and the reply.

## The run view

The console's **Sessions** tab and the [playground](/playground) render each turn from the transcript: the task, the parent's decision and reason, the plan as dependency layers, one card per agent (bundle and version, intent, spec, tool calls with the files they touched, tokens, status, answer) and the reply with its source. The **Agents**, **Files** and **Events** tabs show the same run by agent, by file, and as the raw stream.

## Invented roles

By default `plnt serve` lets the parent run installed bundles only. If nothing fits, it answers with `chat` and says what the installed agents can help with. `plnt dev` and the playground turn invented roles on (`PLNT_PARENT_DYNAMIC_ROLES=1` elsewhere): the parent may then create a single-purpose role (`bundle: null`) for the gap. Such a role gets the built-in file tools over the session's workspace and the `PLNT_AGENT_*` default budget, and nothing else. The parent is told to split by concern (one agent per module, per question, per deliverable), not by step.

## Limits

- At most 4 agents per message (`MAX_AGENTS`), at most `PLNT_MAX_CONCURRENCY` (default 3) running at once.
- Each agent keeps its bundle's own budget, guardrails and `require_tool`.
- Usage is attributed per agent: the parent's calls under `parent`, each bundle under its slug, an invented role under `role:<name>`.
- Kill stops the running agents and skips the ones not started yet; the turn ends with `run_error` (`stopped: killed`).
