"""The bundle-author SDK: `@tool` and `ToolContext`.

A bundle's `tools/*.py` files define tools with a decorator:

    from plnt import tool, ToolContext

    @tool
    def lookup_order(order_id: str, ctx: ToolContext) -> dict:
        '''Look up an order by id.'''
        key = ctx.secret("SHOP_API_KEY")        # tenant's own secret
        base = ctx.config["shop_url"]           # tenant's install config
        ...

The JSON schema the model sees is generated from the type hints; the first
docstring paragraph becomes the description. A parameter named `ctx` is
injected by the runtime and hidden from the model.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import TypeAdapter

TOOL_ATTR = "__plnt_tool__"


@dataclass(frozen=True)
class ToolContext:
    """What a tool may know about the call it serves."""

    tenant_id: str
    session_id: str
    bundle: str
    config: Mapping[str, Any] = field(default_factory=dict)
    _secrets: Mapping[str, str] = field(default_factory=dict, repr=False)

    def secret(self, name: str) -> str:
        """A secret the tenant set for this bundle. Raises KeyError when unset."""
        if name not in self._secrets:
            raise KeyError(f"secret {name!r} is not set for tenant {self.tenant_id!r}")
        return self._secrets[name]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]
    wants_ctx: bool

    def call(self, args: dict[str, Any], ctx: ToolContext) -> Any:
        return self.fn(**args, ctx=ctx) if self.wants_ctx else self.fn(**args)


def _schema_for(fn: Callable[..., Any]) -> tuple[dict[str, Any], bool]:
    sig = inspect.signature(fn)
    hints = inspect.get_annotations(fn, eval_str=True)
    props: dict[str, Any] = {}
    required: list[str] = []
    wants_ctx = False
    for name, p in sig.parameters.items():
        if name == "ctx":
            wants_ctx = True
            continue
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            raise TypeError(f"@tool {fn.__name__}: *args/**kwargs are not supported")
        ann = hints.get(name, Any)
        schema = TypeAdapter(ann).json_schema()
        schema.pop("title", None)
        if p.default is inspect.Parameter.empty:
            required.append(name)
        else:
            schema["default"] = p.default
        props[name] = schema
    params: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        params["required"] = required
    return params, wants_ctx


def tool(
    fn: Callable[..., Any] | None = None, *, name: str | None = None, description: str | None = None
):
    """Mark a function as a tool. Usable as `@tool` or `@tool(name=...)`."""

    def wrap(f: Callable[..., Any]) -> Callable[..., Any]:
        params, wants_ctx = _schema_for(f)
        doc = inspect.getdoc(f) or ""
        spec = ToolSpec(
            name=name or f.__name__,
            description=description or doc.split("\n\n")[0].strip(),
            parameters=params,
            fn=f,
            wants_ctx=wants_ctx,
        )
        setattr(f, TOOL_ATTR, spec)
        return f

    return wrap(fn) if fn is not None else wrap
