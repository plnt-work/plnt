"""What a session works on: a copy of a folder, a shallow clone, or a demo.

A workspace spec is one of

    demo:<name>          a sample project shipped with plnt (demo/workspaces/<name>)
    /abs/path or ~/path  a folder on this machine (needs allow_paths)
    https://… or git@…   a git repository (needs allow_git; shallow clone)

`materialize()` puts a private copy into the session's working folder, so the
agents that run in the session read and change that copy and never the source.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_DEMO_DIRS = [_REPO / "demo" / "workspaces", Path(__file__).resolve().parents[1] / "_demo"]
_IGNORE = shutil.ignore_patterns(
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "dist", "build", "*.pyc",
)
_GIT_RE = re.compile(r"^(https?://|git@|ssh://|git://|file://)")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")


class WorkspaceError(ValueError):
    """The workspace spec is invalid, refused by policy, or could not be copied."""


@dataclass(frozen=True)
class WorkspaceInfo:
    name: str
    kind: str  # demo | path | git
    source: str
    file_count: int


def demo_root(name: str) -> Path:
    if not _NAME_RE.match(name):
        raise WorkspaceError(f"invalid demo workspace name {name!r}")
    for d in _DEMO_DIRS:
        if (d / name).is_dir():
            return d / name
    raise WorkspaceError(f"no demo workspace {name!r} (have: {', '.join(list_demos()) or 'none'})")


def list_demos() -> list[str]:
    names: set[str] = set()
    for d in _DEMO_DIRS:
        if d.is_dir():
            names |= {p.name for p in d.iterdir() if p.is_dir() and not p.name.startswith(".")}
    return sorted(names)


def parse(spec: str) -> tuple[str, str]:
    """-> (kind, value). Raises WorkspaceError for anything else."""
    s = (spec or "").strip()
    if not s:
        raise WorkspaceError("empty workspace spec")
    if s.startswith("demo:"):
        return "demo", s[5:].strip()
    if _GIT_RE.match(s):
        return "git", s
    if s.startswith(("/", "~", ".")):
        return "path", s
    raise WorkspaceError(
        f"workspace {s!r} is not a demo (demo:<name>), a path (/… or ~/…) or a git URL"
    )


def _count_files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.is_file() and ".git" not in p.parts)


def _dir_size_mb(root: Path) -> float:
    total = 0
    for p in root.rglob("*"):
        if p.is_file() and not any(part in {".git", "node_modules", ".venv"} for part in p.parts):
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def materialize(
    spec: str,
    dest: Path,
    *,
    allow_paths: bool = False,
    allow_git: bool = False,
    max_mb: float | None = None,
) -> WorkspaceInfo:
    """Copy or clone `spec` into `dest` (which may exist and be empty)."""
    kind, value = parse(spec)
    limit = float(max_mb if max_mb is not None else os.environ.get("PLNT_WORKSPACE_MAX_MB", "50"))
    dest.mkdir(parents=True, exist_ok=True)
    if kind == "demo":
        src = demo_root(value)
        shutil.copytree(src, dest, dirs_exist_ok=True, ignore=_IGNORE)
        return WorkspaceInfo(name=value, kind=kind, source=f"demo:{value}",
                             file_count=_count_files(dest))
    if kind == "path":
        if not allow_paths:
            raise WorkspaceError("local paths are not allowed as workspaces on this server")
        src = Path(value).expanduser().resolve()
        if not src.is_dir():
            raise WorkspaceError(f"{value} is not a directory")
        if src == dest.resolve() or dest.resolve() in src.parents:
            raise WorkspaceError("workspace source must not contain the session folder")
        size = _dir_size_mb(src)
        if size > limit:
            raise WorkspaceError(f"{value} is {size:.0f} MB; the limit is {limit:.0f} MB")
        shutil.copytree(src, dest, dirs_exist_ok=True, ignore=_IGNORE)
        return WorkspaceInfo(name=src.name, kind=kind, source=str(src),
                             file_count=_count_files(dest))
    # git
    if not allow_git:
        raise WorkspaceError("git URLs are not allowed as workspaces on this server")
    from plnt.execution.tools.execute import _safe_env

    env = _safe_env(dest)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", value, str(dest)],
            capture_output=True, text=True, timeout=60, env=env,
        )
    except FileNotFoundError as e:
        raise WorkspaceError("git is not installed on this server") from e
    except subprocess.TimeoutExpired as e:
        raise WorkspaceError(f"cloning {value} took longer than 60s") from e
    if r.returncode != 0:
        raise WorkspaceError(f"git clone failed: {(r.stderr or r.stdout).strip()[:300]}")
    size = _dir_size_mb(dest)
    if size > limit:
        shutil.rmtree(dest, ignore_errors=True)
        raise WorkspaceError(f"{value} is {size:.0f} MB; the limit is {limit:.0f} MB")
    name = value.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    return WorkspaceInfo(name=name, kind=kind, source=value, file_count=_count_files(dest))
