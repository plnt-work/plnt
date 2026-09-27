---
title: Transcript
description: A session's events folded into turns, for a run view.
---

`GET /tenants/{t}/sessions/{sid}/transcript` (and `/playground/sessions/{sid}/transcript?token=`) returns the session's events grouped by user message. It is what a run view renders; the console and the playground build the same structure event by event from the stream, so a live view and this endpoint always agree.

```json
{
  "session_id": "s_…", "mode": "parent", "bundle": null, "user_id": "web",
  "turns": [
    {
      "run_id": "r_…", "ts": 1758800000.1,
      "user": {"text": "Are you open on Saturday, and can I get a table for 2?"},
      "parent": {
        "kind": "agents",
        "reason": "the message needs support-desk and booking-desk",
        "reply": "",
        "plan": [
          {"id": "support-desk", "role": "support-desk", "bundle": "support-desk",
           "intent": "answer the opening-hours question", "depends_on": []},
          {"id": "booking-desk", "role": "booking-desk", "bundle": "booking-desk",
           "intent": "check a table for 2 on Saturday", "depends_on": []}
        ]
      },
      "agents": [
        {"id": "support-desk", "role": "support-desk", "bundle": "support-desk", "version": "0.1.0",
         "intent": "answer the opening-hours question", "depends_on": [],
         "tools": ["lookup_faq"], "model": {"provider": "ollama", "model": "qwen2.5:7b", "source": "server"},
         "status": "done",
         "steps": [{"kind": "tool_call", "step": 1, "tool": "lookup_faq", "args": {"question": "…"}, "ok": true}],
         "tokens": 280, "wall_seconds": 1.2, "answer": "Tuesday to Saturday …", "error": null}
      ],
      "reply": {"text": "…", "source": "synth"},
      "outcome": "ok", "tokens": 840, "wall_seconds": 3.4
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `mode` | `parent` when the session has no bundle, `agent` when every message goes to one bundle. |
| `turns[].parent` | The parent's decision, or `null` in agent mode. `kind` is `chat`, `clarify` or `agents`. |
| `turns[].agents[]` | One entry per agent that ran. In agent mode there is exactly one: the bundle itself. |
| `agents[].status` | `running`, `done`, `failed` or `killed`. |
| `agents[].steps[]` | `tool_call` entries (`ok` is `null` until the result arrives) and `guardrail` entries. |
| `turns[].reply.source` | `agent` (relayed verbatim), `synth` (merged by the parent), `parent` (chat) or `clarify`. |
| `turns[].outcome` | `null` while the turn is open; then `ok` or the stop reason. |
| `turns[].error` | Present when the turn ended without a reply: `error`, `hint`, `stopped`. |
