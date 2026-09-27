"""Command-line interface."""

from __future__ import annotations

import argparse
import sys

from todo import store
from todo.dates import is_overdue, parse_due


def _print(tasks: list[store.Task]) -> None:
    for t in tasks:
        mark = "x" if t.done else " "
        late = " (overdue)" if not t.done and is_overdue(t.due) else ""
        due = f" due {t.due}" if t.due else ""
        print(f"[{mark}] {t.id}: {t.text}{due}{late}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="todo")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("text")
    a.add_argument("--due")
    a.add_argument("--tag", action="append", default=[])
    sub.add_parser("list").add_argument("--all", action="store_true")
    sub.add_parser("done").add_argument("id", type=int)
    sub.add_parser("rm").add_argument("id", type=int)
    args = p.parse_args(argv)

    if args.cmd == "add":
        due = parse_due(args.due).isoformat() if args.due else None
        t = store.add(args.text, due=due, tags=args.tag)
        print(f"added {t.id}")
    elif args.cmd == "list":
        tasks = store.load()
        if not args.all:
            tasks = [t for t in tasks if not t.done]
        _print(tasks)
    elif args.cmd == "done":
        try:
            store.mark_done(args.id)
        except KeyError:
            print(f"no task {args.id}", file=sys.stderr)
            return 1
    elif args.cmd == "rm":
        store.remove(args.id)
    return 0
