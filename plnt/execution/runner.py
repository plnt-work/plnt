"""Agent runner — PID 1 of a micro-agent process.

Boots from one AgentSpec on stdin. Streams events on stdout. Calls the model
chosen by `plnt.models.resolve_profile` and gives it the tools the spec
declares (search / execute). Returns a `result` event, or an `error` event.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from plnt.execution.spec import AgentSpec


def _emit(kind: str, **payload) -> None:
    """Emit one JSONL event to stdout (read by ProcessSandbox)."""
    evt = {"ts": time.time(), "kind": kind, "agent_id": os.environ.get("PLNT_AGENT_ID", "")}
    if payload:
        evt["payload"] = payload
    print(json.dumps(evt, default=str), flush=True)


@dataclass
class _Run:
    """Per-invocation runner state — replaces the old _RUNNER_STATE module dict.

    Held as a fresh instance per `run_spec()` call so concurrent invocations
    (e.g. inside Temporal Activity workers) never share transcript or spec
    with each other.
    """

    spec: AgentSpec
    transcript: list[dict[str, Any]] = field(default_factory=list)
    started: float = field(default_factory=time.monotonic)


def _read_spec() -> AgentSpec:
    raw = sys.stdin.readline()
    if not raw:
        raise RuntimeError("no AgentSpec on stdin")
    data = json.loads(raw)
    return AgentSpec.model_validate(data)


def _allowed_roots(spec: AgentSpec) -> list[Path]:
    """Where the agent is allowed to search/execute."""
    workdir = Path(os.environ.get("PLNT_WORKDIR", os.getcwd()))
    roots: list[Path] = [workdir]
    # Inputs may include explicit search_roots (e.g. ~/Documents). The planner
    # decides; we only enforce that they exist.
    extra = spec.inputs.get("search_roots", [])
    if isinstance(extra, list):
        for r in extra:
            p = Path(str(r)).expanduser()
            if p.exists():
                roots.append(p)
    return roots


def _run_skill(run: _Run, allowed_roots: list[Path]) -> dict[str, Any]:
    """Execute the agent's skill against the configured model.

    The skill markdown is the system prompt; the intent (wrapped with the
    workdir + allow-list) is the user message. The model calls `search` /
    `execute` through native tool calling (or the JSON shim for models
    without it) until it answers, runs out of steps, or hits the wall budget.

    Model failures are reported as errors with a fix-it hint. They are never
    replaced with a fabricated answer.
    """
    from plnt.agent import filesystem_tools, run_agent
    from plnt.models import ModelError, get_provider, resolve_profile

    spec = run.spec
    max_steps = int(spec.inputs.get("max_steps", 6))
    workdir = Path(os.environ.get("PLNT_WORKDIR", os.getcwd()))
    # Leave a little headroom so we answer before the sandbox watchdog fires.
    deadline = run.started + max(1.0, spec.budget.wall_seconds - 2)

    try:
        profile = resolve_profile(spec.model_hint)  # type: ignore[arg-type]
    except ModelError as e:
        _emit("model_error", **e.to_event())
        return {"answer": f"[{spec.role}] {e}", "error": str(e), "error_hint": e.hint,
                "transcript": run.transcript}
    _emit("model_selected", **profile.to_event())
    provider = get_provider(profile)

    available = filesystem_tools(workdir, allowed_roots)
    tools = [available[name] for name in spec.tools if name in available]

    skill_md = spec.inputs.get("skill_prompt") or _default_skill_prompt(spec.role)
    user_msg = _wrap_user_message(
        spec.inputs.get("intent") or json.dumps(spec.inputs),
        workdir,
        allowed_roots,
    )

    before_files = _scan_workdir(workdir)

    def emit(kind: str, **payload: Any) -> None:
        nonlocal before_files
        if kind == "tool_call":
            payload["workdir"] = str(workdir)
        _emit(kind, **payload)
        if kind == "tool_result":
            # Filesystem-change visibility: what did this tool call create?
            after = _scan_workdir(workdir)
            added = sorted(after - before_files)
            if added:
                _emit("fs_change", step=payload.get("step"), workdir=str(workdir),
                      added=added[:20], total=len(after))
            before_files = after

    result = run_agent(
        system=skill_md,
        user=user_msg,
        tools=tools,
        provider=provider,
        max_steps=max_steps,
        response_schema=spec.output_schema,
        deadline=deadline,
        emit=emit,
    )
    run.transcript[:] = result.transcript
    out: dict[str, Any] = {
        "steps": result.steps,
        "transcript": result.transcript,
        "usage": {
            "prompt_tokens": result.usage.prompt_tokens,
            "completion_tokens": result.usage.completion_tokens,
            "cost_usd": round(result.cost_usd, 6),
        },
        "model": profile.to_event(),
    }
    if result.stopped == "error":
        out["answer"] = f"[{spec.role}] model error: {result.error}"
        out["error"] = result.error
        out["error_hint"] = result.error_hint
        return out
    if result.stopped in ("max_steps", "wall_budget"):
        out["answer"] = _summarise_transcript(spec, result.transcript, workdir, reason=result.error or "")
        out["error"] = result.error
        out["error_hint"] = result.error_hint
        return out
    if not result.answer.strip():
        out["answer"] = _summarise_transcript(spec, result.transcript, workdir,
                                              reason="model returned an empty answer")
        return out
    out["answer"] = result.answer
    if isinstance(result.output, dict):
        out["output"] = result.output
    if result.error:
        out["error"] = result.error
    return out


def _summarise_transcript(spec: "AgentSpec", transcript: list[dict], workdir: Path, reason: str) -> str:
    """When the model doesn't produce a clean FINAL, build a useful answer
    from what we ACTUALLY did. The user should always see something concrete."""
    role = spec.role
    intent = spec.inputs.get("intent", "") if isinstance(spec.inputs, dict) else ""

    # Tool-call stats.
    tools_used: dict[str, int] = {}
    last_tool = None
    last_args = None
    files_created: list[str] = []
    errors: list[str] = []
    for t in transcript:
        name = t.get("tool", "?")
        tools_used[name] = tools_used.get(name, 0) + 1
        last_tool = name
        last_args = t.get("args", {})
        res = t.get("result")
        if isinstance(res, dict):
            if "error" in res:
                errors.append(str(res["error"])[:120])
            # execute result
            if "stdout" in res and isinstance(res.get("stdout"), str) and res["stdout"].strip():
                files_created.append(f"{name}({last_args}) stdout: {res['stdout'][:200]}")

    # Files on disk now.
    try:
        on_disk = sorted(str(p.relative_to(workdir)) for p in workdir.rglob("*") if p.is_file())
    except Exception:
        on_disk = []

    bits = [f"[{role}] {reason}."]
    if intent:
        bits.append(f"Asked: {intent[:200]}")
    if tools_used:
        summary = ", ".join(f"{k}×{v}" for k, v in tools_used.items())
        bits.append(f"Did {len(transcript)} tool call(s): {summary}.")
    else:
        bits.append("Made no tool calls.")
    if last_tool:
        bits.append(f"Last: {last_tool}({_truncate_args(last_args)}).")
    if on_disk:
        sample = ", ".join(on_disk[:5])
        bits.append(f"Files in workdir ({len(on_disk)}): {sample}.")
    if errors:
        bits.append(f"Errors: {errors[0]}")
    return " ".join(bits)


def _truncate_args(a):
    s = repr(a)
    return s if len(s) <= 80 else s[:77] + "…"


def _scan_workdir(workdir: Path) -> set[str]:
    """Return relative paths of all files currently in the workdir."""
    try:
        return {str(p.relative_to(workdir)) for p in workdir.rglob("*") if p.is_file()}
    except Exception:
        return set()


def _default_skill_prompt(role: str) -> str:
    return (
        f"You are the {role} agent. Use the `search` tool to find things in files and "
        "the `execute` tool to run programs in your workdir. Call tools as needed, then "
        "reply with a short plain-text answer describing what you found or did."
    )


def _wrap_user_message(intent: str, workdir: Path, allowed_roots: list[Path]) -> str:
    """Prepend cwd + allow-list so the model stops hallucinating paths.

    The repeating failure mode without this: model guesses an absolute path,
    search() rejects it as out-of-root, agent gives up. Telling the model
    exactly what's reachable kills that loop.
    """
    roots = ", ".join(str(r.resolve()) for r in (allowed_roots or [workdir]))
    workdir_str = str(workdir.resolve())
    # List a few existing entries in the workdir so the model can see what
    # work is already in progress (and not re-scaffold over it).
    try:
        listing = sorted(p.name for p in workdir.iterdir() if not p.name.startswith("."))[:20]
    except OSError:
        listing = []
    listing_str = ", ".join(listing) if listing else "(empty)"
    header = (
        f"WORKDIR (your cwd; every execute() runs here): {workdir_str}\n"
        f"WORKDIR contents: {listing_str}\n"
        f"ALLOWED SEARCH ROOTS: {roots}\n"
        f"RULES:\n"
        f"- For execute(): use relative paths like \".\" or \"./src\". "
        f"Never pass absolute paths in argv.\n"
        f"- For search(): the root MUST be one of the ALLOWED SEARCH ROOTS "
        f"above (or '.' for the workdir). Don't invent paths.\n\n"
        f"TASK: {intent}"
    )
    return header


def run_spec(spec: AgentSpec, *, install_sigterm: bool = False) -> dict[str, Any]:
    """Run a single AgentSpec to completion and return its output dict.

    This is the public, in-process callable form of the runner. Use it from:
      * `main()` — the stdin shim that wraps it with event emission + SIGTERM.
      * Temporal Activities (plnt-cloud) — call directly; transcripts and spec
        live on the per-invocation `_Run` instance, so concurrent Activities
        in the same worker process never share state.

    `install_sigterm=True` installs a process-wide SIGTERM handler that emits
    a `result` event from the current transcript before exit. Use this only
    when this process owns the signal (the CLI shim does; a Temporal worker
    does NOT, because signal handlers are process-wide and Activities run
    concurrently).
    """
    run = _Run(spec=spec)

    if install_sigterm:
        import signal

        def _on_sigterm(signum, frame):
            workdir = Path(os.environ.get("PLNT_WORKDIR", os.getcwd()))
            ans = _summarise_transcript(
                run.spec, run.transcript, workdir,
                reason=f"killed by signal {signum}",
            )
            _emit("result", output={"answer": ans, "transcript": run.transcript, "killed": True})
            _emit("finished")
            sys.exit(143)

        try:
            signal.signal(signal.SIGTERM, _on_sigterm)
        except (ValueError, OSError):
            pass

    result = _run_skill(run, _allowed_roots(spec))
    # Last-resort guard: result must always have a non-empty `answer`.
    if not isinstance(result, dict) or not (result.get("answer") or "").strip():
        workdir = Path(os.environ.get("PLNT_WORKDIR", os.getcwd()))
        result = result if isinstance(result, dict) else {}
        result["answer"] = _summarise_transcript(
            run.spec, result.get("transcript", run.transcript), workdir,
            reason="no answer from skill loop",
        )
    return result


def main() -> int:
    try:
        spec = _read_spec()
    except Exception as e:
        _emit("error", reason=f"bad spec: {e}", trace=traceback.format_exc())
        _emit("finished")
        return 2

    _emit("started", role=spec.role, depth=spec.depth)
    try:
        result = run_spec(spec, install_sigterm=True)
        _emit("result", output=result)
        return 0
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — runner is the outermost catch
        workdir = Path(os.environ.get("PLNT_WORKDIR", os.getcwd()))
        ans = f"[{spec.role}] crashed: {e}"
        _emit("error", reason=str(e), trace=traceback.format_exc())
        _emit("result", output={"answer": ans, "error": str(e)})
        return 1
    finally:
        _emit("finished")


if __name__ == "__main__":
    raise SystemExit(main())
