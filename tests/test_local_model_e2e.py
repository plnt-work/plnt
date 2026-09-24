"""End-to-end: orchestrator → sandboxed runner subprocess → a local Ollama-shaped server.

A tiny HTTP server stands in for Ollama so the whole path runs for real
(process sandbox, env passthrough, native /api/chat, tool dispatch, events)
without downloading a model. `test_real_ollama` below runs against an actual
Ollama when PLNT_TEST_OLLAMA_MODEL is set (CI's `local-models` job does this).
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from plnt.control.orchestrator import Orchestrator
from plnt.control.skills import SkillRegistry


class _FakeOllama(BaseHTTPRequestHandler):
    requests: list[dict] = []

    def log_message(self, *a):  # silence
        pass

    def _send(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"models": [{"name": "fake:1b"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append(body)
        if any(m.get("role") == "tool" for m in body["messages"]):
            self._send(
                {
                    "message": {"role": "assistant", "content": "Found the marker in notes.txt."},
                    "prompt_eval_count": 50,
                    "eval_count": 9,
                }
            )
        else:
            self._send(
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "search",
                                    "arguments": {"pattern": "PLNT_MARKER", "root": "."},
                                }
                            }
                        ],
                    },
                    "prompt_eval_count": 40,
                    "eval_count": 6,
                }
            )


@pytest.fixture
def fake_ollama():
    _FakeOllama.requests = []
    srv = HTTPServer(("127.0.0.1", 0), _FakeOllama)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _skill_registry(tmp_path):
    from plnt.config import paths

    sk = paths().skills
    (sk / "general-helper.md").write_text(
        "---\nmodel_hint: small\ntokens: 5000\nwall_seconds: 60\n---\nYou are the general helper."
    )
    return SkillRegistry(sk)


def test_runner_uses_native_tools_against_local_server(
    isolated_home, tmp_path, monkeypatch, fake_ollama
):
    monkeypatch.delenv("PLNT_FORCE", raising=False)
    monkeypatch.delenv("PLNT_CLOUD_URL", raising=False)
    monkeypatch.setenv("PLNT_LOCAL_URL", fake_ollama)
    monkeypatch.setenv("PLNT_PLANNER_MODEL", "fake:1b")
    monkeypatch.setenv("PLNT_NUM_CTX", "4096")

    orch = Orchestrator(skill_registry=_skill_registry(tmp_path), runs_root=tmp_path / "runs")
    handle = orch.start_run("find the marker")
    events = handle.blackboard.read_all()
    kinds = [e["kind"] for e in events]

    assert "model_error" not in kinds, [e for e in events if e["kind"] == "model_error"]
    assert "tool_call" in kinds and "tool_result" in kinds
    tool_call = next(e for e in events if e["kind"] == "tool_call")
    assert tool_call["payload"]["tool"] == "search"
    result = next(e for e in events if e["kind"] == "result")["payload"]["output"]
    assert result["answer"] == "Found the marker in notes.txt."
    assert result["usage"]["prompt_tokens"] == 90

    agent_calls = [r for r in _FakeOllama.requests if r.get("tools")]
    assert agent_calls, "runner never sent native tools"
    assert agent_calls[0]["options"]["num_ctx"] == 4096
    # Second agent turn must carry the protocol-correct transcript.
    roles = [m["role"] for m in agent_calls[-1]["messages"]]
    assert roles[-2:] == ["assistant", "tool"]


@pytest.mark.skipif(
    not os.environ.get("PLNT_TEST_OLLAMA_MODEL"), reason="set PLNT_TEST_OLLAMA_MODEL to run"
)
def test_real_ollama(isolated_home, tmp_path, monkeypatch):
    model = os.environ["PLNT_TEST_OLLAMA_MODEL"]
    monkeypatch.delenv("PLNT_FORCE", raising=False)
    monkeypatch.setenv("PLNT_PLANNER_MODEL", model)

    from plnt.agent import filesystem_tools, run_agent
    from plnt.models import get_provider, resolve_profile

    (tmp_path / "notes.txt").write_text("the secret word is PLNT_MARKER\n")
    tools = filesystem_tools(tmp_path, [tmp_path])
    res = run_agent(
        system="You are a helpful agent. Use the search tool to look inside files first.",
        user="Search the files in '.' for the text PLNT_MARKER and tell me which file contains it.",
        tools=[tools["search"]],
        provider=get_provider(resolve_profile("small")),
        max_steps=4,
    )
    assert res.stopped == "final", (res.error, res.transcript)
    assert res.transcript and res.transcript[0]["tool"] == "search"
    assert "notes.txt" in res.answer
