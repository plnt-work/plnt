"""A session's events, folded into turns.

This is the schema clients read instead of raw events when they want to show
a conversation: for every user message, what the parent decided, which agents
ran (with their spec and what they did), and the reply.

    {
      "session_id": "s_…", "mode": "parent" | "agent", "bundle": "…",
      "turns": [
        {
          "run_id": "r_…", "ts": 1758800000.1,
          "user": {"text": "table for 2 tonight?"},
          "parent": {"kind": "agents", "reason": "…", "reply": "", "plan": [...]},
          "agents": [
            {"id": "code-reviewer", "role": "code-reviewer", "bundle": "code-reviewer",
             "version": "0.1.0", "intent": "…", "depends_on": [], "tools": [...],
             "model": {...}, "status": "done" | "running" | "failed" | "killed",
             "steps": [{"kind": "tool_call", "tool": "read_file",
                        "args": {...}, "ok": true}, …],
             "files": [{"path": "app/store.py", "op": "read"}, …],
             "tokens": 1163, "wall_seconds": 2.5, "answer": "…", "error": null}
          ],
          "reply": {"text": "…", "source": "agent" | "synth" | "parent" | "clarify"},
          "outcome": "ok" | "error" | …, "tokens": 1163, "wall_seconds": 2.5
        }
      ]
    }

The same fold is done incrementally in the console and the site, event by
event, so a live view and this endpoint always agree.
"""

from __future__ import annotations

from typing import Any


_FILE_OPS = {"read_file": "read", "write_file": "write", "list_files": "list", "search": "search"}


def file_of(tool: str, args: Any) -> dict[str, str] | None:
    """The file (or folder / command) a built-in tool call touched, or None."""
    a = args if isinstance(args, dict) else {}
    if tool in ("read_file", "write_file", "list_files"):
        return {"path": str(a.get("path") or "."), "op": _FILE_OPS[tool]}
    if tool == "search":
        return {"path": str(a.get("root") or "."), "op": "search",
                "detail": str(a.get("pattern") or "")}
    if tool == "execute":
        argv = a.get("argv")
        cmd = " ".join(str(x) for x in argv) if isinstance(argv, list) else str(argv or "")
        return {"path": cmd[:120], "op": "run"}
    return None


def build_transcript(session: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    turns: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    agents: dict[str, dict[str, Any]] = {}

    def agent(aid: str) -> dict[str, Any]:
        if aid not in agents:
            agents[aid] = {
                "id": aid, "role": aid, "bundle": None, "version": None, "intent": "",
                "depends_on": [], "tools": [], "model": None, "status": "running",
                "steps": [], "files": [], "tokens": 0, "wall_seconds": None,
                "answer": None, "error": None,
            }
            if cur is not None:
                cur["agents"].append(agents[aid])
        return agents[aid]

    for e in events:
        k, p, aid = e["kind"], e.get("payload") or {}, e.get("agent_id") or ""
        if k == "user_message":
            cur = {
                "run_id": e.get("run_id", ""), "ts": e["ts"], "user": {"text": p.get("text", "")},
                "parent": None, "agents": [], "reply": None, "outcome": None,
                "tokens": 0, "wall_seconds": None,
            }
            agents = {}
            turns.append(cur)
            continue
        if cur is None:
            continue
        if k == "parent_decision":
            cur["parent"] = {
                "kind": p.get("decision"), "reason": p.get("reason", ""),
                "reply": p.get("reply", ""), "plan": p.get("agents", []),
            }
        elif k == "agent_spawned":
            a = agent(p.get("agent_id") or aid)
            a.update({
                "role": p.get("role", a["role"]), "bundle": p.get("bundle"),
                "version": p.get("version"), "intent": p.get("intent", ""),
                "depends_on": p.get("depends_on", []), "tools": p.get("tools", []),
                "model": p.get("model"), "status": "running",
            })
        elif k == "run_started" and not cur["agents"] and p.get("bundle"):
            # Single-agent session: the bundle itself is the one agent.
            a = agent(p["bundle"])
            a.update({"bundle": p["bundle"], "version": p.get("version"),
                      "tools": p.get("tools", []), "model": p.get("model")})
        elif aid and aid != "parent":
            a = agent(aid)
            if k == "tool_call":
                a["steps"].append({"kind": "tool_call", "step": p.get("step"),
                                   "tool": p.get("tool"), "args": p.get("args"), "ok": None})
                f = file_of(str(p.get("tool") or ""), p.get("args"))
                if f and f not in a["files"]:
                    a["files"].append(f)
            elif k == "tool_result":
                for s in reversed(a["steps"]):
                    if s["kind"] == "tool_call" and s["tool"] == p.get("tool") and s["ok"] is None:
                        s["ok"] = bool(p.get("ok"))
                        break
            elif k == "model_result":
                a["tokens"] += int(p.get("tokens") or 0)
            elif k == "guardrail":
                a["steps"].append({"kind": "guardrail", "tool": p.get("tool"),
                                   "action": p.get("action")})
            elif k == "killed":
                a["status"] = "killed"
                a["error"] = p.get("reason")
            elif k == "agent_finished":
                if p.get("outcome") == "ok":
                    a["status"] = "done"
                elif a["status"] != "killed":
                    a["status"] = "failed"
                a["answer"] = p.get("answer")
                a["error"] = p.get("error") or a["error"]
                a["tokens"] = int(p.get("tokens") or a["tokens"])
                a["wall_seconds"] = p.get("wall_seconds")
        if k == "assistant_message":
            cur["reply"] = {"text": p.get("text", ""), "source": p.get("source", "agent")}
            # Single-agent turns have no agent_finished; the reply closes the agent.
            for a in cur["agents"]:
                if a["status"] == "running":
                    a["status"] = "done"
                    a["answer"] = a["answer"] or p.get("text", "")
        elif k == "run_error":
            for a in cur["agents"]:
                if a["status"] == "running":
                    a["status"] = "failed"
                    a["error"] = a["error"] or p.get("error")
            cur["error"] = {
                "error": p.get("error"), "hint": p.get("hint", ""), "stopped": p.get("stopped")
            }
        elif k == "run_finished":
            cur["outcome"] = p.get("outcome")
            cur["tokens"] = int(p.get("tokens") or 0)
            cur["wall_seconds"] = p.get("wall_seconds")

    return {
        "session_id": session.get("id", ""),
        "mode": session.get("mode", "agent" if session.get("bundle") else "parent"),
        "bundle": session.get("bundle") or None,
        "user_id": session.get("user_id", ""),
        "title": session.get("title", ""),
        "workspace": session.get("workspace", ""),
        "turns": turns,
    }
