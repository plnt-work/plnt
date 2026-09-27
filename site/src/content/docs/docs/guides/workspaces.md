---
title: Workspaces
description: What a session works on, how the copy is made, and what the server allows.
---

A session can be bound to a **workspace** when it starts. The runtime makes a private copy in the session's working directory (`<tenant>/work/<session>/`), and that copy is the only thing the session's agents can list, read, search, write or run in. The source is never touched; a session never sees another session's copy.

## Specs

| Spec | Example | What happens |
| --- | --- | --- |
| `demo:<name>` | `demo:notes-api` | One of the sample projects that ship with plnt (`plnt/_demo`, or `demo/workspaces` in a checkout). |
| a folder | `/home/me/src/api`, `~/src/api` | Copied, skipping `.git`, `node_modules`, `__pycache__`, `.venv`, `dist`, `build`. |
| a git URL | `https://github.com/o/r.git`, `git@…` | `git clone --depth 1`, 60 s timeout, no prompts. |

Copies are capped at `PLNT_WORKSPACE_MAX_MB` (50) and refused above it.

```bash
# CLI: one agent, one message
plnt run code-reviewer "review src/auth.py" --workspace ~/src/api

# HTTP: a parent session
curl -X POST $API/tenants/acme/sessions -H "$AUTH" -H 'content-type: application/json' \
  -d '{"workspace": "https://github.com/acme/api.git"}'
```

The session row and the transcript carry `workspace` (the name) and `workspace_kind`. `run_started` events carry the workspace too.

## Policy

Which specs a server accepts is set on the executor, by constructor or environment:

| | `plnt dev` | `plnt serve` | playground |
| --- | --- | --- | --- |
| demos | yes | yes | only the tenant's own |
| local folders (`PLNT_WORKSPACE_PATHS`) | yes | yes | no |
| git URLs (`PLNT_WORKSPACE_GIT`) | no | no (set to `1`) | no |
| read-only tools (`PLNT_READ_ONLY`) | no | no | yes unless `PLNT_PLAYGROUND_EXECUTE=1` |
| invented roles (`PLNT_PARENT_DYNAMIC_ROLES`) | yes | no | yes |

A refused spec fails the session before it is created (HTTP 422 with the reason).

## Tools over the workspace

The built-ins a bundle may name in `[runtime] tools`:

| Tool | Does | Read-only |
| --- | --- | --- |
| `list_files(path=".", depth=2)` | Folder listing, skipping junk folders. | yes |
| `read_file(path, start?, end?)` | Numbered lines; 64 KB cap. | yes |
| `search(pattern, root=".")` | Regex search, `{path, line, text}` hits. | yes |
| `write_file(path, content)` | Create or overwrite; parents created. | no |
| `execute(argv, timeout=30)` | One program, no shell, in the workspace. | no |

Every path is resolved inside the workspace; `../` and absolute paths outside it are refused with a hint the model can act on. A bundle's own `tools/*.py` get the same folder as `ctx.workdir`.

## Cleanup

Copies stay until the tenant is deleted, except on the playground, where copies older than 24 hours are removed when a new session starts.
