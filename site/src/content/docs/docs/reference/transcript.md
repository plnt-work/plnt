---
title: Transcript
description: A session's events folded into turns, for a run view.
---

`GET /tenants/{t}/sessions/{sid}/transcript` (and `/playground/sessions/{sid}/transcript?token=`) returns the session's events grouped by user message. It is what a run view renders; the console and the playground build the same structure event by event from the stream, so a live view and this endpoint always agree.

```json
{
  "session_id": "s_…", "mode": "parent", "bundle": null, "user_id": "web",
  "title": "Audit app/store.py for bugs and write tests for it.", "workspace": "notes-api",
  "turns": [
    {
      "run_id": "r_…", "ts": 1758800000.1,
      "user": {"text": "Audit app/store.py for bugs and write tests for it."},
      "parent": {
        "kind": "agents",
        "reason": "a review, then tests that depend on it",
        "reply": "",
        "plan": [
          {"id": "review", "role": "code-reviewer", "bundle": "code-reviewer",
           "intent": "find bugs in app/store.py", "depends_on": []},
          {"id": "tests", "role": "test-writer", "bundle": "test-writer",
           "intent": "write tests for app/store.py", "depends_on": ["review"]}
        ]
      },
      "agents": [
        {"id": "review", "role": "code-reviewer", "bundle": "code-reviewer", "version": "0.1.0",
         "intent": "find bugs in app/store.py", "depends_on": [],
         "tools": ["list_files", "read_file", "search"],
         "model": {"provider": "ollama", "model": "qwen2.5:7b", "source": "server"},
         "status": "done",
         "steps": [{"kind": "tool_call", "step": 1, "tool": "read_file", "args": {"path": "app/store.py"}, "ok": true}],
         "files": [{"path": "app/store.py", "op": "read"}],
         "tokens": 2076, "wall_seconds": 4.1, "answer": "## Findings\n1. …", "error": null}
      ],
      "reply": {"text": "…", "source": "synth"},
      "outcome": "ok", "tokens": 840, "wall_seconds": 3.4
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `title`, `workspace` | The first message (shortened) and the workspace name. |
| `mode` | `parent` when the session has no bundle, `agent` when every message goes to one bundle. |
| `turns[].parent` | The parent's decision, or `null` in agent mode. `kind` is `chat`, `clarify` or `agents`. |
| `turns[].agents[]` | One entry per agent that ran. In agent mode there is exactly one: the bundle itself. |
| `agents[].status` | `running`, `done`, `failed` or `killed`. |
| `agents[].steps[]` | `tool_call` entries (`ok` is `null` until the result arrives) and `guardrail` entries. |
| `agents[].files[]` | What the built-in tools touched: `{path, op}` with `op` in `list`, `read`, `search` (with `detail` = the pattern), `write`, `run` (path is the command). |
| `turns[].reply.source` | `agent` (relayed verbatim), `synth` (merged by the parent), `parent` (chat) or `clarify`. |
| `turns[].outcome` | `null` while the turn is open; then `ok` or the stop reason. |
| `turns[].error` | Present when the turn ended without a reply: `error`, `hint`, `stopped`. |
