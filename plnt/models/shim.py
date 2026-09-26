"""JSON tool-call shim for models without native tool calling.

Many small local models (and some older chat templates) reject `tools`. The
shim describes the tools in the system prompt and constrains the reply to
one JSON object via the provider's structured-output mode:

    {"type": "tool_call", "name": "<tool>", "arguments": {...}}
    {"type": "final", "output": <answer>}

It replaces the old free-text `TOOL:` / `FINAL:` protocol: the format is
enforced by the server (JSON schema / Ollama `format`), not by regexes.
"""

from __future__ import annotations

import json
from typing import Any

from plnt.models.openai_compat import strip_code_fence
from plnt.models.types import ChatResult, ModelProvider, ToolCall

SHIM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["tool_call", "final"]},
        "name": {"type": "string"},
        "arguments": {"type": "object"},
        "output": {},
    },
    "required": ["type"],
}


def _describe(tools: list[dict[str, Any]]) -> str:
    lines = []
    for t in tools:
        fn = t.get("function") or {}
        params = json.dumps(fn.get("parameters") or {}, separators=(",", ":"))
        lines.append(
            f"- {fn.get('name')}: {fn.get('description', '').strip()}\n  parameters: {params}"
        )
    return "\n".join(lines)


def shim_instructions(tools: list[dict[str, Any]]) -> str:
    return (
        "You can call these tools:\n"
        f"{_describe(tools)}\n\n"
        "Reply with exactly one JSON object and nothing else:\n"
        '  to call a tool:  {"type": "tool_call", "name": "<tool name>", "arguments": {...}}\n'
        '  when finished:   {"type": "final", "output": <your answer>}\n'
        "Call one tool at a time. After each call you will receive its result."
    )


def to_shim_messages(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Rewrite a native-tools transcript into plain system/user/assistant turns."""
    out: list[dict[str, Any]] = []
    added = False
    for m in messages:
        role = m.get("role")
        if role == "system" and not added:
            out.append(
                {
                    "role": "system",
                    "content": (m.get("content") or "") + "\n\n" + shim_instructions(tools),
                }
            )
            added = True
        elif role == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                fn = tc.get("function") or {}
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                out.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {"type": "tool_call", "name": fn.get("name"), "arguments": args or {}}
                        ),
                    }
                )
        elif role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": f"Result of tool {m.get('name', '')}:\n{m.get('content', '')}",
                }
            )
        else:
            out.append({"role": role, "content": m.get("content") or ""})
    if not added:
        out.insert(0, {"role": "system", "content": shim_instructions(tools)})
    return out


def parse_shim_reply(res: ChatResult) -> ChatResult:
    text = strip_code_fence(res.content or "")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        obj = None
    res.shimmed = True
    if not isinstance(obj, dict):
        # Model ignored the format; treat its text as the final answer.
        return res
    if obj.get("type") == "tool_call" and obj.get("name"):
        args = obj.get("arguments")
        err = None if isinstance(args, dict) else "arguments must be a JSON object"
        res.tool_calls = [
            ToolCall(
                id="shim_0",
                name=str(obj["name"]),
                arguments=args if isinstance(args, dict) else {},
                parse_error=err,
            )
        ]
        res.content = ""
        return res
    output = obj.get("output", "")
    res.content = output if isinstance(output, str) else json.dumps(output)
    return res


def chat_via_shim(
    provider: ModelProvider,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    timeout: float | None = None,
    tool_choice: str | None = None,
) -> ChatResult:
    msgs = to_shim_messages(messages, tools)
    if tool_choice:
        msgs.append({"role": "user", "content": f"Call the `{tool_choice}` tool now."})
    res = provider.chat(msgs, response_schema=SHIM_SCHEMA, timeout=timeout)
    return parse_shim_reply(res)
