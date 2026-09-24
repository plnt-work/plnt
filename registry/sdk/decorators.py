"""Workflow + step decorators. The runtime introspects these at load time."""

from __future__ import annotations

from typing import Callable, Optional


def workflow(*, name: str, version: str) -> Callable:
    """Marks a class as a workflow entrypoint.

    The runtime discovers workflow classes by scanning modules for this
    decorator and matches them to the ref in the workflow spec.
    """

    def _wrap(cls):
        cls.__microagents_workflow__ = {"name": name, "version": version}
        return cls

    return _wrap


def step(*, id: str, deps: Optional[list[str]] = None) -> Callable:
    """Marks a method as a workflow step.

    Runtimes build a DAG from the deps declarations and execute steps in
    topological order, running independent branches in parallel.
    """

    def _wrap(fn):
        fn.__microagents_step__ = {"id": id, "deps": deps or []}
        return fn

    return _wrap
