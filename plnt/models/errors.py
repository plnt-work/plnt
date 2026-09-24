"""Model-call errors.

Every failure talking to a model raises one of these. Nothing in plnt turns a
failed model call into a fabricated answer — callers either handle the error
or surface it to the user with the `hint`.
"""

from __future__ import annotations


class ModelError(RuntimeError):
    """Base class. `hint` is a one-line, user-actionable fix."""

    def __init__(self, message: str, *, hint: str = "", provider: str = "", model: str = ""):
        super().__init__(message)
        self.hint = hint
        self.provider = provider
        self.model = model

    def to_event(self) -> dict:
        return {
            "error": type(self).__name__,
            "message": str(self),
            "hint": self.hint,
            "provider": self.provider,
            "model": self.model,
        }

    def __str__(self) -> str:  # include the hint so logs are actionable
        base = super().__str__()
        return f"{base} — {self.hint}" if self.hint else base


class NoModelConfigured(ModelError):  # noqa: N818
    """No local model is reachable and no cloud model is configured."""


class ModelUnavailable(ModelError):  # noqa: N818
    """The endpoint could not be reached (connection refused, DNS, TLS)."""


class ModelNotPulled(ModelError):  # noqa: N818
    """The endpoint is up but does not have the requested model."""


class ModelTimeout(ModelError):  # noqa: N818
    """The call exceeded its timeout (profile timeout or remaining wall budget)."""


class ModelBadResponse(ModelError):  # noqa: N818
    """Non-2xx status or a response body that is not a chat completion."""

    def __init__(self, message: str, *, status: int = 0, **kw):
        super().__init__(message, **kw)
        self.status = status


class ToolsUnsupported(ModelError):  # noqa: N818
    """The model rejected native tool calling; callers may retry via the JSON shim."""
