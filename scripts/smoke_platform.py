"""End-to-end smoke for the platform: two tenants, the same developer bundle,
different workspaces, isolated data.

Runs `plnt serve` against a fake Ollama (or a real model with
PLNT_SMOKE_MODEL=<name>), then checks the guarantees that hold for any model:

  - a tenant's session works on its own copy of its workspace;
  - an answer only reaches the user after the agent listed the workspace
    (require_tool guardrail);
  - usage is booked per tenant;
  - one tenant's key is refused on another's routes.

Usage: python scripts/smoke_platform.py
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx

ADMIN = "smoke-admin-token"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeOllama(BaseHTTPRequestHandler):
    """Lists the workspace, reads its README, then answers from what it read.
    As the parent, spawns repo-explainer for every task."""

    def log_message(self, *a):
        pass

    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"models": [{"name": "fake:1b"}]})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = req["messages"]
        usage = {"prompt_eval_count": 120, "eval_count": 20}
        system = "\n".join(m["content"] for m in msgs if m["role"] == "system")
        question = [m for m in msgs if m["role"] == "user"][-1]["content"]
        if "You are the parent agent" in system:
            dec = {
                "kind": "agents",
                "reason": "the user asked about the workspace",
                "agents": [
                    {
                        "id": "repo-explainer",
                        "role": "repo-explainer",
                        "bundle": "repo-explainer",
                        "intent": question.rsplit("User: ", 1)[-1],
                        "depends_on": [],
                    }
                ],
            }
            self._send({"message": {"role": "assistant", "content": json.dumps(dec)}, **usage})
            return
        tool_msgs = [m for m in msgs if m["role"] == "tool"]
        if not tool_msgs:
            call = {"name": "list_files", "arguments": {"path": ".", "depth": 2}}
        elif len(tool_msgs) == 1:
            call = {"name": "read_file", "arguments": {"path": "README.md"}}
        else:
            content = json.loads(tool_msgs[-1]["content"]).get("content", "")
            first = next((ln.split(": ", 1)[1] for ln in content.splitlines() if ": " in ln), "")
            self._send(
                {"message": {"role": "assistant", "content": f"This project: {first}"}, **usage}
            )
            return
        self._send(
            {
                "message": {"role": "assistant", "content": "", "tool_calls": [{"function": call}]},
                **usage,
            }
        )


def main() -> int:
    home = tempfile.mkdtemp(prefix="plnt-smoke-")
    env = {**os.environ, "PLNT_HOME": home, "PLNT_ADMIN_TOKEN": ADMIN}
    env.pop("PLNT_FORCE", None)
    fake = None
    if os.environ.get("PLNT_SMOKE_MODEL"):
        env["PLNT_PLANNER_MODEL"] = os.environ["PLNT_SMOKE_MODEL"]
    else:
        fake = HTTPServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=fake.serve_forever, daemon=True).start()
        env["PLNT_LOCAL_URL"] = f"http://127.0.0.1:{fake.server_address[1]}"
        env["PLNT_PLANNER_MODEL"] = "fake:1b"

    # Two workspaces that differ in one line each tenant should answer from.
    work = Path(tempfile.mkdtemp(prefix="plnt-smoke-ws-"))
    readmes = {
        "acme": "# acme-billing\n\nInvoices and dunning for Acme.\n",
        "globex": "# globex-inventory\n\nWarehouse stock levels for Globex.\n",
    }
    for tid, text in readmes.items():
        (work / tid / "src").mkdir(parents=True)
        (work / tid / "README.md").write_text(text)
        (work / tid / "src" / "main.py").write_text("print('hi')\n")

    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "plnt.cli", "serve", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}/v1"
    c = httpx.Client(base_url=base, timeout=120)
    try:
        for _ in range(100):
            try:
                if c.get("/health").status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            raise SystemExit("server did not start")

        admin = {"Authorization": f"Bearer {ADMIN}"}
        keys = {}
        for tid in readmes:
            r = c.post("/tenants", json={"id": tid}, headers=admin)
            r.raise_for_status()
            keys[tid] = {"Authorization": f"Bearer {r.json()['api_key']}"}
            r = c.post(
                f"/tenants/{tid}/installs",
                json={"bundle": "repo-explainer", "config": {"audience": "reviewer"}},
                headers=keys[tid],
            )
            r.raise_for_status()
            print(f"✓ {tid}: repo-explainer installed")

        answers: dict[str, str] = {}
        real_model = bool(os.environ.get("PLNT_SMOKE_MODEL"))
        for tid in readmes:
            h = keys[tid]
            r = c.post(
                f"/tenants/{tid}/sessions",
                json={"bundle": "repo-explainer", "workspace": str(work / tid)},
                headers=h,
            )
            r.raise_for_status()
            sid = r.json()["session_id"]
            c.post(
                f"/tenants/{tid}/sessions/{sid}/messages",
                json={"text": "What is this project?"},
                headers=h,
            ).raise_for_status()
            kinds = []
            refused = None
            with c.stream(
                "GET", f"/tenants/{tid}/sessions/{sid}/stream?until_idle=1", headers=h
            ) as s:
                for line in s.iter_lines():
                    if line.startswith("data: "):
                        evt = json.loads(line[6:])
                        kinds.append(evt["kind"])
                        if evt["kind"] == "assistant_message":
                            answers[tid] = evt["payload"]["text"]
                        if evt["kind"] == "run_error":
                            refused = evt["payload"]
            assert kinds[-1] == "run_finished", (tid, kinds)
            # The guarantee that holds for ANY model: an answer only reaches the
            # user after the agent looked at the workspace (require_tool).
            if tid in answers:
                assert "tool_call" in kinds[: kinds.index("assistant_message")], (tid, kinds)
                print(f"✓ {tid}: looked at the workspace, then answered → {answers[tid]!r}")
            else:
                assert refused and "withheld" in refused["error"], (tid, refused, kinds)
                assert real_model, "the fake model always uses the tool"
                print(f"✓ {tid}: model skipped the lookup twice; guardrail withheld its answer")
            row = c.get(f"/tenants/{tid}/sessions", headers=h).json()["sessions"][0]
            assert row["title"] == "What is this project?" and row["workspace"] == tid, row

        # Each tenant answered from its own workspace copy, never the other's.
        if not real_model:
            assert "acme-billing" in answers["acme"] and "globex-inventory" in answers["globex"]
            print("✓ each tenant answered from its own workspace only")
        assert "globex" not in answers.get("acme", "").lower(), answers
        assert "acme" not in answers.get("globex", "").lower(), answers

        for tid in readmes:
            u = c.get(f"/tenants/{tid}/usage", headers=keys[tid]).json()
            assert u["model_calls"] >= (1 if real_model else 3), u
            print(
                f"✓ {tid}: usage {u['model_calls']} calls, "
                f"{u['prompt_tokens']}+{u['completion_tokens']} tokens"
            )
        assert c.get("/tenants/acme", headers=keys["globex"]).status_code == 401
        print("✓ globex's key is refused on acme's routes")
        return 0
    finally:
        server.terminate()
        server.wait(10)
        if fake:
            fake.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
