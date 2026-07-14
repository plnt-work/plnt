"""microagents SDK — the minimal surface a workflow module imports.

Runtimes (plnt, others) implement the actual dispatch. This SDK provides
decorators + tool proxies so workflow code has a stable authoring interface.
"""

from .decorators import step, workflow
from . import tools

__all__ = ["step", "workflow", "tools"]
