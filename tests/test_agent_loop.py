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


def test_filesystem_search_resolves_relative_root_against_workdir(tmp_path, monkeypatch):
    from plnt.agent import filesystem_tools

    (tmp_path / "notes.txt").write_text("the word is PLNT_MARKER\n")
    monkeypatch.chdir("/")  # process cwd deliberately differs from the workdir
    search = filesystem_tools(tmp_path, [tmp_path])["search"]
    hits = search.fn({"pattern": "PLNT_MARKER", "root": "."})
    assert hits and hits[0]["path"].endswith("notes.txt")
    assert search.fn({"pattern": "PLNT_MARKER"})  # root omitted → workdir


def _lookup_tool(calls: list) -> ToolDef:
    return ToolDef(name="lookup", description="look up facts",
                   fn=lambda a: calls.append(a) or {"fact": "open 5-11pm"})


def test_require_tool_forces_choice_then_releases_it():
    seen: list = []
    prov = ScriptedProvider([
        ChatResult(tool_calls=[ToolCall("c1", "lookup", {"q": "hours"})]),
        ChatResult(content="We're open 5-11pm."),
    ])
    res = run_agent(system="s", user="hours?", tools=[_lookup_tool(seen)], provider=prov,
                    require_tool="lookup")
    assert res.stopped == "final" and res.answer == "We're open 5-11pm."
    assert prov.calls[0]["tool_choice"] == "lookup"
    assert prov.calls[1]["tool_choice"] is None  # released once the tool ran


def test_require_tool_reprompts_once_when_skipped():
    events: list = []
    prov = ScriptedProvider([
        ChatResult(content="We're open 9-5 daily."),  # invented, no lookup
        ChatResult(tool_calls=[ToolCall("c1", "lookup", {"q": "hours"})]),
        ChatResult(content="We're open 5-11pm."),
    ])
    res = run_agent(system="s", user="hours?", tools=[_lookup_tool([])], provider=prov,
                    require_tool="lookup", emit=lambda k, **p: events.append((k, p)))
    assert res.answer == "We're open 5-11pm."
    guard = [p for k, p in events if k == "guardrail"]
    assert guard == [{"step": 1, "rule": "require_tool", "tool": "lookup", "action": "reprompt",
                      "skipped_answer": "We're open 9-5 daily."}]
    assert "You have not called `lookup`" in prov.calls[1]["messages"][-1]["content"]


def test_require_tool_refuses_unverified_answer():
    prov = ScriptedProvider(lambda m, t: ChatResult(content="We're open 9-5 daily."))
    res = run_agent(system="s", user="hours?", tools=[_lookup_tool([])], provider=prov,
                    require_tool="lookup")
    assert res.stopped == "error" and res.output is None
    assert "withheld" in res.error and "stronger model" in res.error_hint
    assert len(prov.calls) == 2


def test_require_tool_must_be_available():
    import pytest

    with pytest.raises(ValueError):
        run_agent(system="s", user="u", tools=[], provider=ScriptedProvider([]),
                  require_tool="lookup")


def test_forced_tool_choice_reaches_openai_payload():
    import json as _json

    import httpx

    from plnt.models import ModelProfile, OpenAICompatProvider

    seen = {}

    def handler(req):
        seen["body"] = _json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    prov = OpenAICompatProvider(ModelProfile(provider="openai", base_url="http://x/v1", model="m"),
                                transport=httpx.MockTransport(handler))
    prov.chat([], tools=[_lookup_tool([]).spec()], tool_choice="lookup")
    assert seen["body"]["tool_choice"] == {"type": "function", "function": {"name": "lookup"}}
