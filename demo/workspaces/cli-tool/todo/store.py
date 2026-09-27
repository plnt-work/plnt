"""JSON-file storage for tasks."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Task:
    id: int
    text: str
    due: str | None = None  # ISO date
    done: bool = False
    tags: list[str] = field(default_factory=list)


def path() -> Path:
    return Path(os.environ.get("TODO_FILE") or Path.home() / ".todo.json")


def load() -> list[Task]:
    p = path()
    if not p.exists():
        return []
    raw = json.loads(p.read_text() or "[]")
    return [Task(**t) for t in raw]


def save(tasks: list[Task]) -> None:
    path().write_text(json.dumps([asdict(t) for t in tasks], indent=2))


def add(text: str, due: str | None = None, tags: list[str] | None = None) -> Task:
    tasks = load()
    next_id = max((t.id for t in tasks), default=0) + 1
    task = Task(id=next_id, text=text, due=due, tags=tags or [])
    tasks.append(task)
    save(tasks)
    return task


def mark_done(task_id: int) -> Task:
    tasks = load()
    for t in tasks:
        if t.id == task_id:
            t.done = True
            save(tasks)
            return t
    raise KeyError(task_id)


def remove(task_id: int) -> None:
    tasks = [t for t in load() if t.id != task_id]
    save(tasks)
