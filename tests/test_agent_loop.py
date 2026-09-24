from __future__ import annotations

import json
import time

from plnt.agent import ToolDef, run_agent
from plnt.models import ChatResult, ModelUnavailable, ScriptedProvider, ToolCall, Usage
from plnt.models.shim import parse_shim_reply, to_shim_messages


def _echo_tool(calls: list) -> ToolDef:
    def fn(args):
        calls.append(args)
        return {"echo": args.get("text")}

    return ToolDef(
        name="echo",
        description="echo text",
        fn=fn,
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
    )


def test_tool_call_then_final_follows_protocol():
    seen: list = []
    prov = ScriptedProvider(
        [
            ChatResult(
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "hi"})],
                usage=Usage(10, 5),
            ),
            ChatResult(content="done", usage=Usage(20, 3)),
        ]
    )
    events: list = []
    res = run_agent(
        system="s",
        user="u",
        tools=[_echo_tool(seen)],
        provider=prov,
        emit=lambda k, **p: events.append((k, p)),
    )

    assert res.stopped == "final" and res.answer == "done" and res.steps == 2
    assert seen == [{"text": "hi"}]
    assert res.usage.total_tokens == 38

    second_call_msgs = prov.calls[1]["messages"]
    assert [m["role"] for m in second_call_msgs] == ["system", "user", "assistant", "tool"]
    assert second_call_msgs[2]["tool_calls"][0]["id"] == "c1"
    assert second_call_msgs[3]["tool_call_id"] == "c1"
    assert json.loads(second_call_msgs[3]["content"]) == {"echo": "hi"}

    kinds = [k for k, _ in events]
    assert kinds == [
        "model_call",
        "model_result",
        "tool_call",
        "tool_result",
        "model_call",
        "model_result",
    ]
    assert events[1][1]["tokens"] == 15  # budget governor reads this field


def test_unknown_tool_and_bad_args_go_back_to_model():
    prov = ScriptedProvider(
        [
            ChatResult(
                tool_calls=[
                    ToolCall(id="a", name="nope", arguments={}),
                    ToolCall(id="b", name="echo", arguments={}, parse_error="bad json"),
                ]
            ),
            ChatResult(content="ok"),
        ]
    )
    res = run_agent(system="s", user="u", tools=[_echo_tool([])], provider=prov)
    assert "unknown tool" in res.transcript[0]["result"]["error"]
    assert res.transcript[1]["result"] == {"error": "bad json"}
    assert res.answer == "ok"


def test_tool_exception_is_reported_to_model():
    def boom(args):
        raise ValueError("kaput")

    prov = ScriptedProvider(
        [
            ChatResult(tool_calls=[ToolCall(id="a", name="boom", arguments={})]),
            ChatResult(content="recovered"),
        ]
    )
    res = run_agent(system="s", user="u", tools=[ToolDef("boom", "", boom)], provider=prov)
    assert res.transcript[0]["result"] == {"error": "ValueError: kaput"}
    assert res.answer == "recovered"


def test_model_error_stops_loop_with_hint():
    def fail(messages, tools):
        raise ModelUnavailable("down", hint="start it")

    events: list = []
    res = run_agent(
        system="s", user="u", provider=ScriptedProvider(fail), emit=lambda k, **p: events.append(k)
    )
    assert res.stopped == "error" and res.error_hint == "start it" and res.output is None
    assert "model_error" in events


def test_max_steps():
    prov = ScriptedProvider(
        lambda m, t: ChatResult(
            tool_calls=[ToolCall(id="x", name="echo", arguments={"text": "again"})]
        )
    )
    res = run_agent(system="s", user="u", tools=[_echo_tool([])], provider=prov, max_steps=3)
    assert res.stopped == "max_steps" and res.steps == 3 and len(res.transcript) == 3


def test_timeout_is_capped_by_wall_budget():
    prov = ScriptedProvider([ChatResult(content="x")])
    run_agent(system="s", user="u", provider=prov, deadline=time.monotonic() + 5)
    assert prov.calls[0]["timeout"] <= 5


def test_exhausted_wall_budget_stops_before_calling():
    prov = ScriptedProvider([])
    res = run_agent(system="s", user="u", provider=prov, deadline=time.monotonic() - 1)
    assert res.stopped == "wall_budget" and not prov.calls


def test_response_schema_parses_json():
    prov = ScriptedProvider([ChatResult(content='```json\n{"kind": "chat"}\n```')])
    res = run_agent(system="s", user="u", provider=prov, response_schema={"type": "object"})
    assert res.output == {"kind": "chat"} and res.error is None
    assert prov.calls[0]["response_schema"] == {"type": "object"}


def test_shim_roundtrip():
    tools = [ToolDef("echo", "echo", lambda a: a).spec()]
    msgs = to_shim_messages(
        [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "u"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [ToolCall("c", "echo", {"t": 1}).to_openai()],
            },
            {"role": "tool", "tool_call_id": "c", "name": "echo", "content": "{}"},
        ],
        tools,
    )
    assert "echo" in msgs[0]["content"] and msgs[3]["role"] == "user"
    assert json.loads(msgs[2]["content"])["type"] == "tool_call"

    call = parse_shim_reply(
        ChatResult(content='{"type":"tool_call","name":"echo","arguments":{"t":2}}')
    )
    assert call.tool_calls[0].arguments == {"t": 2} and call.shimmed
    final = parse_shim_reply(ChatResult(content='{"type":"final","output":"answer"}'))
    assert final.content == "answer" and not final.tool_calls
    prose = parse_shim_reply(ChatResult(content="just text"))
    assert prose.content == "just text"
