from __future__ import annotations

import json

import httpx

from plnt.models import ModelProfile
from plnt.models.doctor import diagnose


def _fake_ollama(*, pulled=True, tools=True, ctx=32768):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/tags":
            names = ["qwen2.5:7b"] if pulled else ["llama3.2:latest"]
            return httpx.Response(200, json={"models": [{"name": n} for n in names]})
        if req.url.path == "/api/show":
            return httpx.Response(200, json={"model_info": {"qwen2.context_length": ctx}})
        body = json.loads(req.content)
        if "tools" in body:
            if not tools:
                return httpx.Response(400, json={"error": "qwen2.5:7b does not support tools"})
            return httpx.Response(
                200,
                json={
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {"function": {"name": "get_weather", "arguments": {"city": "Paris"}}}
                        ],
                    }
                },
            )
        if (
            body.get("format")
            and "properties" in body["format"]
            and "answer" in body["format"]["properties"]
        ):
            return httpx.Response(200, json={"message": {"content": '{"answer": 42}'}})
        # shim path
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {"type": "tool_call", "name": "get_weather", "arguments": {"city": "Paris"}}
                    )
                }
            },
        )

    return httpx.MockTransport(handler)


PROFILE = ModelProfile(
    provider="ollama", base_url="http://o:11434", model="qwen2.5:7b", num_ctx=8192
)


def _by_name(rep):
    return {c.name: c for c in rep.checks}


def test_healthy_model_passes_all_checks():
    rep = diagnose(PROFILE, transport=_fake_ollama())
    checks = _by_name(rep)
    assert rep.ok, rep.checks
    assert "native" in checks["tool calling"].detail
    assert checks["JSON output"].ok
    assert checks["context window"].ok


def test_unpulled_model_stops_with_pull_hint():
    rep = diagnose(PROFILE, transport=_fake_ollama(pulled=False))
    checks = _by_name(rep)
    assert not rep.ok
    assert checks["model present"].hint == "run `ollama pull qwen2.5:7b`"
    assert "tool calling" not in checks


def test_model_without_native_tools_uses_shim():
    rep = diagnose(PROFILE, transport=_fake_ollama(tools=False))
    assert "JSON shim" in _by_name(rep)["tool calling"].detail


def test_small_context_is_flagged():
    rep = diagnose(PROFILE, transport=_fake_ollama(ctx=4096))
    c = _by_name(rep)["context window"]
    assert c.ok is False and c.hint == "set PLNT_NUM_CTX=4096"


def test_unreachable():
    def down(req):
        raise httpx.ConnectError("refused")

    rep = diagnose(PROFILE, transport=httpx.MockTransport(down))
    assert [c.name for c in rep.checks] == ["reachable"] and not rep.ok
