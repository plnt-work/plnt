from __future__ import annotations

from plnt.execution.sandbox.docker import DockerSandbox, container_url
from plnt.execution.spec import AgentSpec


def test_container_url_rewrites_loopback_only():
    assert container_url("http://127.0.0.1:11434") == "http://host.docker.internal:11434"
    assert container_url("http://localhost:8080/v1") == "http://host.docker.internal:8080/v1"
    assert container_url("https://api.example.com/v1") == "https://api.example.com/v1"


def test_env_points_local_model_at_host_gateway(monkeypatch, isolated_home):
    monkeypatch.setenv("PLNT_LOCAL_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("PLNT_REQUIRED_PATH", "/Volumes/models")
    monkeypatch.setenv("PLNT_CLOUD_API_KEY", "sk")
    sb = DockerSandbox.__new__(DockerSandbox)
    env = sb._env_for(AgentSpec(role="general-helper", run_id="r1"))
    assert env["PLNT_LOCAL_URL"] == "http://host.docker.internal:11434"
    assert "PLNT_COMPUTE_URL" not in env
    assert "PLNT_REQUIRED_PATH" not in env
    assert env["PLNT_CLOUD_API_KEY"] == "sk"
