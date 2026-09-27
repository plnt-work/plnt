---
title: Tools and ToolContext
description: Give the model Python functions to call, scoped to one tenant and one workspace.
---

Put tools in `tools/*.py` and mark them with `@tool`:

```python
from plnt import ToolContext, tool
import httpx


@tool
def open_issues(label: str, ctx: ToolContext) -> list[dict]:
    """List open issues with a label from the project's tracker.

    Anything after the first paragraph is not shown to the model.
    """
    r = httpx.get(
        f"{ctx.config['tracker_url']}/issues",
        params={"label": label, "state": "open"},
        headers={"Authorization": f"Bearer {ctx.secret('TRACKER_TOKEN')}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()
```

- The function name is the tool name. Override it with `@tool(name="...", description="...")`.
- The JSON Schema the model sees is generated from the type hints (via Pydantic). Parameters without defaults are required.
- The first paragraph of the docstring is the description the model sees. Write it for the model.
- A parameter named `ctx` is filled in by the runtime and hidden from the model.
- Return anything JSON-serialisable. If the tool raises, the model sees the error and can recover; the event log records `ok: false`.
- List the tool in `skill.toml` under `[runtime] tools`, or it is not offered to the model.

## ToolContext

| Field | What it is |
| --- | --- |
| `ctx.tenant_id` | The tenant this call is for. |
| `ctx.session_id` | The session. |
| `ctx.bundle` | The bundle slug. |
| `ctx.config` | This tenant's install config, after validation and defaults. Read-only. |
| `ctx.secret(name)` | A secret the tenant set. Raises `KeyError` if it is not set. |
| `ctx.data_dir` | A private, persistent directory for this bundle's data for this tenant (`<tenant>/data/<slug>/`). |
| `ctx.workdir` | The session's workspace copy (`<tenant>/work/<session>/`), or `None` when the session has none. Same folder the built-in file tools use. |

## Built-in tools

`list_files`, `read_file`, `search`, `write_file` and `execute` are available by name and need no code; they work inside the session's workspace copy. See [Workspaces](/docs/guides/workspaces/#tools-over-the-workspace). Read-only servers remove `write_file` and `execute`.

## Trust

Tools run inside the server process with the server's permissions, and `execute` runs programs as the server user inside the workspace copy. The per-tenant scoping above is enforced by what the runtime hands the tool, not by an OS sandbox. **Only install bundles whose code you trust**, and keep `execute` off on servers that anonymous users can reach. Running untrusted bundles in a sandbox is on the roadmap.
