from __future__ import annotations

import pytest

from plnt.compute.router import Decision, LLMRouter
from plnt.models import NoModelConfigured


def test_offline_raw_returns_empty_text_so_callers_fallback():
    d = LLMRouter(force="offline").step(system="sys", user="hi", raw=True)
    assert isinstance(d, Decision)
    assert d.kind == "final" and d.text == "" and d.backend == "offline"


def test_unconfigured_raises_instead_of_echo(monkeypatch):
    monkeypatch.delenv("PLNT_FORCE", raising=False)
    monkeypatch.delenv("PLNT_CLOUD_URL", raising=False)
    monkeypatch.setenv("PLNT_LOCAL_URL", "http://127.0.0.1:1")
    with pytest.raises(NoModelConfigured) as ei:
        LLMRouter().step(system="s", user="u", raw=True)
    assert "ollama serve" in ei.value.hint


def test_non_raw_is_rejected():
    with pytest.raises(NotImplementedError):
        LLMRouter(force="offline").step(system="s", user="u", raw=False)
