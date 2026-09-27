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


READ_FILE_MAX_BYTES = 64 * 1024
_SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
                        ".pytest_cache", "dist", "build", ".ruff_cache"})


def _inside(workdir: Path, allowed_roots: list[Path], raw: str) -> Path:
    """Resolve `raw` (relative to the workdir) and refuse anything outside the roots."""
    from plnt.execution.tools.search import _resolve_inside

    p = Path(str(raw or ".")).expanduser()
    if not p.is_absolute():
        p = workdir / p
    return _resolve_inside(p, allowed_roots)


def filesystem_tools(workdir: Path, allowed_roots: list[Path]) -> dict[str, ToolDef]:
    """The built-in tools every bundle may name: `search`, `list_files`,
    `read_file`, `write_file` and `execute`. All of them stay inside the
    allowed roots (the session's working folder, normally)."""
    from plnt.execution.tools import execute, search

    def _search(args: dict[str, Any]) -> Any:
        # Relative roots ("." / "src") mean the agent's workdir, not the
        # process cwd — the two differ when the loop runs in-process.
        root = Path(str(args.get("root") or ".")).expanduser()
        if not root.is_absolute():
            root = workdir / root
        hits = search(
            str(args.get("pattern", "")),
            root,
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

    def _list_files(args: dict[str, Any]) -> Any:
        root = _inside(workdir, allowed_roots, str(args.get("path") or "."))
        depth = max(1, min(int(args.get("depth", 2)), 6))
        if not root.is_dir():
            return {"error": f"{args.get('path') or '.'} is not a directory"}
        out: list[dict[str, Any]] = []
        base_depth = len(root.parts)

        def walk(d: Path) -> None:
            if len(out) >= 400:
                return
            try:
                entries = sorted(d.iterdir(), key=lambda e: (not e.is_dir(), e.name))
            except OSError:
                return
            for e in entries:
                if e.name in _SKIP_DIRS or e.name.startswith(".git"):
                    continue
                rel = e.relative_to(root).as_posix()
                if e.is_dir():
                    out.append({"path": rel + "/", "dir": True})
                    if len(e.parts) - base_depth < depth:
                        walk(e)
                else:
                    try:
                        size = e.stat().st_size
                    except OSError:
                        size = 0
                    out.append({"path": rel, "size": size})

        walk(root)
        return {"root": root.relative_to(workdir.resolve()).as_posix() if root != workdir.resolve()
                else ".", "entries": out, "truncated": len(out) >= 400}

    def _read_file(args: dict[str, Any]) -> Any:
        p = _inside(workdir, allowed_roots, str(args.get("path") or ""))
        if not p.is_file():
            return {"error": f"{args.get('path')} is not a file"}
        data = p.read_bytes()[: READ_FILE_MAX_BYTES + 1]
        truncated = len(data) > READ_FILE_MAX_BYTES
        text = data[:READ_FILE_MAX_BYTES].decode("utf-8", errors="replace")
        lines = text.splitlines()
        start = max(1, int(args.get("start") or 1))
        end = args.get("end")
        end_i = min(len(lines), int(end)) if end else len(lines)
        body = "\n".join(f"{i}: {ln}" for i, ln in enumerate(lines[start - 1:end_i], start))
        return {"path": args.get("path"), "lines": len(lines), "start": start, "end": end_i,
                "truncated": truncated, "content": body}

    def _write_file(args: dict[str, Any]) -> Any:
        p = _inside(workdir, allowed_roots, str(args.get("path") or ""))
        content = str(args.get("content") or "")
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content, encoding="utf-8")
        return {"path": args.get("path"), "bytes": len(content.encode()), "created": not existed}

    return {
        "list_files": ToolDef(
            name="list_files",
            description=(
                "List files and folders under a path in your workdir (default '.'), "
                "`depth` levels deep (default 2). Returns {entries: [{path, size|dir}]}."
            ),
            fn=_list_files,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Folder, relative. Default '.'."},
                    "depth": {"type": "integer", "description": "Levels to descend (1-6)."},
                },
            },
        ),
        "read_file": ToolDef(
            name="read_file",
            description=(
                "Read a text file in your workdir, numbered lines. Optional `start`/`end` "
                "line range. Files over 64 KB are cut."
            ),
            fn=_read_file,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path, relative."},
                    "start": {"type": "integer", "description": "First line (1-based)."},
                    "end": {"type": "integer", "description": "Last line, inclusive."},
                },
                "required": ["path"],
            },
        ),
        "write_file": ToolDef(
            name="write_file",
            description=(
                "Create or overwrite a text file in your workdir with `content`. "
                "Parent folders are created."
            ),
            fn=_write_file,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path, relative."},
                    "content": {"type": "string", "description": "Whole file content."},
                },
                "required": ["path", "content"],
            },
        ),
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
