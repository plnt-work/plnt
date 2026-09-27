---
title: Events
description: What a run records, step by step.
---

Every event has this shape:

```json
{"seq": 12, "ts": 1758800000.12, "run_id": "r_…", "agent_id": "code-reviewer", "kind": "tool_call", "payload": {…}}
```

`seq` increases by one within a session. Use it as the `after` cursor. `agent_id` names who produced the event: `parent` for the [parent](/docs/guides/parent/), an agent's id for its own steps, empty for session-level events.

| Kind | Payload | When |
| --- | --- | --- |
| `user_message` | `text` | A message was accepted. |
| `run_started` | `mode` (`agent`/`parent`), `workspace`, `bundle`, `version`, `model` (`provider`, `base_url`, `model`, `source`, `reason`); parent mode adds `specialists`, `dynamic_roles`, `read_only` | The model was resolved. Never contains an API key. In parent mode there is no `bundle`. |
| `parent_decision` | `decision` (`chat`/`clarify`/`agents`), `reason`, `reply`, `agents` (the plan: `id`, `role`, `bundle`, `intent`, `depends_on`) | The parent decided what the message needs. |
| `agent_spawned` | `parent_id`, `role`, `bundle` (null for an invented role), `version`, `intent`, `depends_on`, `tools` (after read-only stripping), `require_tool`, `model`, `budget`, `config`, `read_only` | An agent's spec, right before it runs. |
| `agent_finished` | `outcome` (`ok`, `skipped` or the stop reason), `answer`, `error`, `tokens`, `wall_seconds` | An agent ended. `skipped` when a kill stopped it before it started. |
| `model_call` | `step`, `provider`, `model`, `purpose` | Before each model request. `purpose` is `decide` or `synthesize` for the parent's calls. |
| `model_result` | `step`, `decision_kind` (`tool_call`/`final`), `tokens`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, `provider`, `model`, `shimmed` | After each model response. |
| `tool_call` | `step`, `tool`, `args` | Before a tool runs. For the built-ins, `args.path` / `args.root` / `args.argv` say what file, folder or command. |
| `tool_result` | `step`, `tool`, `ok` | After it returns or raises. |
| `guardrail` | `step`, `rule` (`require_tool`), `tool`, `action` (`reprompt`/`refused`), `skipped_answer` | The model answered without the required tool. |
| `model_error` | `step`, `error`, `message`, `hint`, `provider`, `model` | The model call failed. |
| `killed` | `step`, `reason` | A kill request, the token budget, or the loop detector stopped the run. |
| `assistant_message` | `text`, `output`, `source` | The reply. `output` is the parsed object when the bundle sets `response_schema`. `source` is `agent`, `synth`, `parent` or `clarify`. |
| `run_error` | `stopped` (`error`, `max_steps`, `wall_budget`, `killed`, `crash`), `error`, `hint` | The run ended without an answer. |
| `run_finished` | `outcome` (`ok` or the stop reason), `tokens`, `wall_seconds` | Always the last event of a run. |

Every run ends with exactly one `run_finished`, after either `assistant_message` or `run_error`.
