"""Provider wire tests against httpx.MockTransport — no network."""

from __future__ import annotations

import json

import httpx
import pytest

from plnt.models import (
    ModelBadResponse,
    ModelNotPulled,
    ModelProfile,
    ModelTimeout,
    ModelUnavailable,
    OllamaProvider,
    OpenAICompatProvider,
    ToolsUnsupported,
    chat,
)
from plnt.models.ollama import to_ollama_messages

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "grep",
            "parameters": {"type": "object", "properties": {}},
        },
    }
]


def _oa(handler, **kw) -> OpenAICompatProvider:
    prof = ModelProfile(
        provider="openai",
        base_url="http://llm.test/v1",
        model="m",
        api_key="k",
        cost_in_per_m=1.0,
        cost_out_per_m=2.0,
        **kw,
    )
    return OpenAICompatProvider(prof, transport=httpx.MockTransport(handler))


def _ol(handler, **kw) -> OllamaProvider:
    prof = ModelProfile(
        provider="ollama",
        base_url="http://ollama.test:11434",
        model="qwen2.5:3b",
        num_ctx=16384,
        **kw,
    )
    return OllamaProvider(prof, transport=httpx.MockTransport(handler))


# ------------------------------------------------------------------ openai


def test_openai_sends_tools_params_and_parses_tool_calls():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["auth"] = req.headers.get("authorization")
        seen["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "search",
                                        "arguments": '{"pattern": "TODO"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
            },
        )

    res = _oa(handler).chat([{"role": "user", "content": "hi"}], tools=TOOLS)
    assert seen["url"] == "http://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer k"
    assert seen["body"]["tools"] == TOOLS and seen["body"]["tool_choice"] == "auto"
    assert seen["body"]["temperature"] == 0.2 and seen["body"]["max_tokens"] == 2048
    assert res.tool_calls[0].name == "search" and res.tool_calls[0].arguments == {"pattern": "TODO"}
    assert res.usage.total_tokens == 1500
    assert res.cost_usd == pytest.approx((1000 * 1.0 + 500 * 2.0) / 1e6)


def test_openai_response_schema_when_no_tools():
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"a":1}'}}]})

    _oa(handler).chat([{"role": "user", "content": "x"}], response_schema={"type": "object"})
    assert seen["body"]["response_format"]["type"] == "json_schema"
    assert "tools" not in seen["body"]


def test_openai_bad_argument_json_is_reported_not_dropped():
    def handler(req):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "c",
                                    "function": {"name": "search", "arguments": "{not json"},
                                }
                            ]
                        }
                    }
                ]
            },
        )

    tc = _oa(handler).chat([], tools=TOOLS).tool_calls[0]
    assert tc.arguments == {} and "not valid JSON" in tc.parse_error


@pytest.mark.parametrize(
    "exc,err",
    [
        (httpx.ConnectError("refused"), ModelUnavailable),
        (httpx.ReadTimeout("slow"), ModelTimeout),
    ],
)
def test_openai_transport_errors_raise(exc, err):
    def handler(req):
        raise exc

    with pytest.raises(err):
        _oa(handler).chat([{"role": "user", "content": "x"}])


def test_openai_http_errors_raise():
    with pytest.raises(ModelNotPulled):
        _oa(lambda r: httpx.Response(404, text='{"error":"model m not found"}')).chat([])
    with pytest.raises(ModelBadResponse) as ei:
        _oa(lambda r: httpx.Response(401, text="bad key")).chat([])
    assert "API key" in ei.value.hint
    with pytest.raises(ModelBadResponse):
        _oa(lambda r: httpx.Response(200, text="<html>")).chat([])


def test_openai_tools_rejected_raises_tools_unsupported():
    def handler(req):
        return httpx.Response(400, text="this model does not support tools")

    with pytest.raises(ToolsUnsupported):
        _oa(handler).chat([], tools=TOOLS)


def test_openai_health_reports_missing_model():
    def handler(req):
        assert req.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "other"}]})

    rep = _oa(handler).health()
    assert rep.reachable and rep.model_present is False and not rep.ok and "other" in rep.hint


# ------------------------------------------------------------------ ollama


def test_ollama_native_chat_sends_num_ctx_and_parses_tool_calls():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": "search", "arguments": {"pattern": "x"}}}],
                },
                "prompt_eval_count": 42,
                "eval_count": 7,
            },
        )

    res = _ol(handler).chat([{"role": "user", "content": "hi"}], tools=TOOLS)
    assert seen["url"] == "http://ollama.test:11434/api/chat"
    assert seen["body"]["options"]["num_ctx"] == 16384
    assert seen["body"]["tools"] == TOOLS and seen["body"]["stream"] is False
    assert res.tool_calls[0].arguments == {"pattern": "x"}
    assert res.usage.prompt_tokens == 42 and res.usage.completion_tokens == 7


def test_ollama_schema_goes_in_format():
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"message": {"content": "{}"}})

    _ol(handler).chat([], response_schema={"type": "object"})
    assert seen["body"]["format"] == {"type": "object"}


def test_ollama_missing_model_raises_with_pull_hint():
    def handler(req):
        return httpx.Response(404, json={"error": "model 'qwen2.5:3b' not found"})

    with pytest.raises(ModelNotPulled) as ei:
        _ol(handler).chat([])
    assert ei.value.hint == "run `ollama pull qwen2.5:3b`"


def test_ollama_down_raises_unavailable():
    def handler(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(ModelUnavailable) as ei:
        _ol(handler).chat([])
    assert "ollama serve" in ei.value.hint


def test_ollama_health_checks_model_is_pulled():
    def handler(req):
        assert req.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "llama3.2:latest"}]})

    rep = _ol(handler).health()
    assert (
        rep.reachable and rep.model_present is False and rep.hint == "run `ollama pull qwen2.5:3b`"
    )

    prof = ModelProfile(provider="ollama", base_url="http://o:11434", model="llama3.2")
    assert OllamaProvider(prof, transport=httpx.MockTransport(handler)).health().ok


def test_ollama_message_conversion():
    msgs = [
        {"role": "system", "content": "s"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"pattern":"x"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "[]"},
    ]
    out = to_ollama_messages(msgs)
    assert out[1]["tool_calls"][0]["function"]["arguments"] == {"pattern": "x"}
    assert out[2] == {"role": "tool", "content": "[]", "tool_name": "search"}


# ------------------------------------------------------------------ shim fallback


def test_chat_falls_back_to_shim_when_tools_unsupported():
    calls = []

    def handler(req):
        body = json.loads(req.content)
        calls.append(body)
        if "tools" in body:
            return httpx.Response(400, json={"error": "gemma does not support tools"})
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {"type": "tool_call", "name": "search", "arguments": {"pattern": "x"}}
                    )
                }
            },
        )

    res = chat(
        _ol(handler),
        [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
        tools=TOOLS,
    )
    assert len(calls) == 2 and "format" in calls[1]
    assert "search" in calls[1]["messages"][0]["content"]  # tools described in system prompt
    assert res.shimmed and res.tool_calls[0].name == "search"


def test_native_tools_on_does_not_fall_back():
    def handler(req):
        return httpx.Response(400, json={"error": "does not support tools"})

    with pytest.raises(ToolsUnsupported):
        chat(_ol(handler), [], tools=TOOLS, native_tools="on")
