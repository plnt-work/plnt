"""plnt.executors — how tenant sessions are run."""

from plnt.executors.local import LocalExecutor, SessionError

__all__ = ["LocalExecutor", "SessionError"]
