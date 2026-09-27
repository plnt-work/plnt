from __future__ import annotations

import pytest

from plnt.models import NoModelConfigured
from plnt.models.profiles import resolve_profile


def test_forced_cloud_names_the_missing_settings(monkeypatch):
    for n in ("PLNT_CLOUD_URL", "PLNT_CLOUD_API_KEY", "PLNT_CLOUD_SMALL_MODEL"):
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("PLNT_CLOUD_URL", "https://llm.test/v1")
    monkeypatch.setenv("PLNT_CLOUD_SMALL_MODEL", "m")
    with pytest.raises(NoModelConfigured) as ei:
        resolve_profile(force="cloud")
    assert ei.value.args[0] == "PLNT_FORCE=cloud but PLNT_CLOUD_API_KEY is not set"
