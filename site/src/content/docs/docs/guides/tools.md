---
title: Tools and ToolContext
description: Give the model Python functions to call, scoped to one tenant.
---

Put tools in `tools/*.py` and mark them with `@tool`:

```python
from plnt import ToolContext, tool
import httpx


@tool
def lookup_order(order_id: str, ctx: ToolContext) -> dict:
    """Look up an order's status by id.

    Anything after the first paragraph is not shown to the model.
    """
    r = httpx.get(
        f"{ctx.config['shop_url']}/api/orders/{order_id}",
        headers={"Authorization": f"Bearer {ctx.secret('SHOP_API_KEY')}"},
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
| `ctx.session_id` | The conversation. |
| `ctx.bundle` | The bundle slug. |
| `ctx.config` | This tenant's install config, after validation and defaults. Read-only. |
| `ctx.secret(name)` | A secret the tenant set. Raises `KeyError` if it is not set. |
| `ctx.data_dir` | A private, persistent directory for this bundle's data for this tenant (`<tenant>/data/<slug>/`). No other tenant or bundle gets the same path. |

`data_dir` is where a bundle keeps state. `booking-desk` keeps its bookings ledger there in SQLite:

```python
def _db(ctx: ToolContext) -> sqlite3.Connection:
    conn = sqlite3.connect(ctx.data_dir / "bookings.db", isolation_level=None)
    ...
```

## Built-in tools

Two built-ins are available by name: `search` (regex search over files) and `execute` (run one program, no shell). Both work inside the session's scratch directory under the tenant (`<tenant>/work/<session>/`). Most customer-facing agents should not list them.

## Trust

Tools run inside the server process with the server's permissions. The per-tenant scoping above is enforced by what the runtime hands the tool, not by an OS sandbox. **Only install bundles whose code you trust.** Running untrusted bundles in a sandbox is on the roadmap.
