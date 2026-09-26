from __future__ import annotations

import socket

import pytest

from plnt.compute.backend_picker import BackendChoice, choose
from plnt.models import NoModelConfigured
from plnt.models.profiles import guess_local_provider, resolve_profile


@pytest.fixture
def listening_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    yield s.getsockname()[1]
    s.close()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in (
        "PLNT_FORCE",
        "PLNT_CLOUD_URL",
        "PLNT_CLOUD_API_KEY",
        "PLNT_CLOUD_SMALL_MODEL",
        "PLNT_CLOUD_DEEP_MODEL",
        "PLNT_REQUIRED_PATH",
        "PLNT_LOCAL_PROVIDER",
        "PLNT_COMPUTE_URL",
    ):
        monkeypatch.delenv(k, raising=False)


def _cloud(monkeypatch):
    monkeypatch.setenv("PLNT_CLOUD_URL", "https://api.example.com/v1")
    monkeypatch.setenv("PLNT_CLOUD_API_KEY", "sk-test")
    monkeypatch.setenv("PLNT_CLOUD_SMALL_MODEL", "small-1")
    monkeypatch.setenv("PLNT_CLOUD_DEEP_MODEL", "deep-1")


def test_force_offline_short_circuits():
    c = choose(force="offline")
    assert c.kind == "offline" and c.api_key == ""


def test_force_env_is_honoured(monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    assert resolve_profile().provider == "offline"


def test_local_chosen_when_reachable(monkeypatch, listening_port):
    monkeypatch.setenv("PLNT_LOCAL_URL", f"http://127.0.0.1:{listening_port}")
    p = resolve_profile("small")
    assert p.source == "local" and p.provider == "ollama"


def test_falls_back_to_cloud_when_local_down(monkeypatch):
    monkeypatch.setenv("PLNT_LOCAL_URL", "http://127.0.0.1:1")
    _cloud(monkeypatch)
    p = resolve_profile("deep")
    assert p.source == "cloud" and p.model == "deep-1" and p.api_key == "sk-test"


def test_required_path_missing_skips_local(monkeypatch, tmp_path, listening_port):
    monkeypatch.setenv("PLNT_LOCAL_URL", f"http://127.0.0.1:{listening_port}")
    monkeypatch.setenv("PLNT_REQUIRED_PATH", str(tmp_path / "missing"))
    _cloud(monkeypatch)
    assert resolve_profile().source == "cloud"


def test_nothing_available_raises_with_hint(monkeypatch):
    monkeypatch.setenv("PLNT_LOCAL_URL", "http://127.0.0.1:1")
    with pytest.raises(NoModelConfigured) as ei:
        resolve_profile()
    assert "ollama pull" in ei.value.hint


def test_force_cloud_without_config_raises(monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "cloud")
    with pytest.raises(NoModelConfigured):
        resolve_profile()


def test_provider_guess_from_url(monkeypatch):
    assert guess_local_provider("http://127.0.0.1:11434") == "ollama"
    assert guess_local_provider("http://127.0.0.1:8080/v1") == "openai"
    monkeypatch.setenv("PLNT_LOCAL_PROVIDER", "openai")
    assert guess_local_provider("http://127.0.0.1:11434") == "openai"


def test_event_payload_has_no_api_key(monkeypatch):
    bc = BackendChoice(kind="cloud", url="https://x", model="m", api_key="secret", reason="r")
    assert "api_key" not in bc.to_event()
    monkeypatch.setenv("PLNT_LOCAL_URL", "http://127.0.0.1:1")
    _cloud(monkeypatch)
    assert "sk-test" not in str(resolve_profile().to_event())
