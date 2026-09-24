"""Tool definitions for the agent loop.

A `ToolDef` pairs an OpenAI-style function schema with the Python callable
that implements it. The loop sends `spec()` to the model and calls `fn` with
the parsed arguments. Whatever `fn` returns is JSON-encoded back to the model;
exceptions become `{"error": ...}` results the model can react to.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolDef:
    name: str
    description: str
    fn: Callable[[dict[str, Any]], Any]
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def filesystem_tools(workdir: Path, allowed_roots: list[Path]) -> dict[str, ToolDef]:
    """The two built-in tools: `search` (grep) and `execute` (bounded argv)."""
    from plnt.execution.tools import execute, search

    def _search(args: dict[str, Any]) -> Any:
        hits = search(
            str(args.get("pattern", "")),
            args.get("root") or str(workdir),
            allowed_roots=allowed_roots,
            max_hits=int(args.get("max_hits", 50)),
        )
        return [h.__dict__ for h in hits]

    def _execute(args: dict[str, Any]) -> Any:
        argv = args.get("argv") or []
        if isinstance(argv, str):
            import shlex

            argv = shlex.split(argv)
        res = execute(
            [str(a) for a in argv],
            workdir=workdir,
            allowed_roots=allowed_roots,
            timeout_seconds=int(args.get("timeout", 30)),
        )
        return res.__dict__

    return {
        "search": ToolDef(
            name="search",
            description=(
                "Search file contents with a regex. Returns matching lines as "
                "{path, line, text}. `root` must be '.' (your workdir) or one of the allowed roots."
            ),
            fn=_search,
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regular expression to search for.",
                    },
                    "root": {"type": "string", "description": "Directory to search. Default '.'."},
                    "max_hits": {"type": "integer", "description": "Maximum matches (default 50)."},
                },
                "required": ["pattern"],
            },
        ),
        "execute": ToolDef(
            name="execute",
            description=(
                "Run one program in your workdir (no shell). Pass argv as a list, e.g. "
                '["ls", "-la"]. Returns {exit_code, stdout, stderr}. Use relative paths.'
            ),
            fn=_execute,
            parameters={
                "type": "object",
                "properties": {
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Program and arguments.",
                    },
                    "timeout": {"type": "integer", "description": "Seconds (default 30)."},
                },
                "required": ["argv"],
            },
        ),
    }
