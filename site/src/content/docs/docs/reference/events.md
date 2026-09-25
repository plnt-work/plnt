---
title: Events
description: What a run records, step by step.
---

Every event has this shape:

```json
{"seq": 12, "ts": 1758800000.12, "run_id": "r_…", "kind": "tool_call", "payload": {…}}
```

`seq` increases by one within a session. Use it as the `after` cursor.

| Kind | Payload | When |
| --- | --- | --- |
| `user_message` | `text` | A message was accepted. |
| `run_started` | `bundle`, `version`, `model` (`provider`, `base_url`, `model`, `source`, `reason`) | The model was resolved. Never contains an API key. |
| `model_call` | `step`, `provider`, `model` | Before each model request. |
| `model_result` | `step`, `decision_kind` (`tool_call`/`final`), `tokens`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, `provider`, `model`, `shimmed` | After each model response. |
| `tool_call` | `step`, `tool`, `args` | Before a tool runs. |
| `tool_result` | `step`, `tool`, `ok` | After it returns or raises. |
| `guardrail` | `step`, `rule` (`require_tool`), `tool`, `action` (`reprompt`/`refused`), `skipped_answer` | The model answered without the required tool. |
| `model_error` | `step`, `error`, `message`, `hint`, `provider`, `model` | The model call failed. |
| `killed` | `step`, `reason` | A kill request, the token budget, or the loop detector stopped the run. |
| `assistant_message` | `text`, `output` | The answer. `output` is the parsed object when the bundle sets `response_schema`. |
| `run_error` | `stopped` (`error`, `max_steps`, `wall_budget`, `killed`, `crash`), `error`, `hint` | The run ended without an answer. |
| `run_finished` | `outcome` (`ok` or the stop reason), `tokens`, `wall_seconds` | Always the last event of a run. |

Every run ends with exactly one `run_finished`, after either `assistant_message` or `run_error`.
