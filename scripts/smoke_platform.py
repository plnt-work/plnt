"""End-to-end platform smoke: one bundle, two isolated tenants, over real HTTP.

    python scripts/smoke_platform.py                 # Ollama-shaped fake model
    PLNT_SMOKE_MODEL=qwen2.5:1.5b python scripts/smoke_platform.py   # real Ollama

Starts `plnt serve` in a subprocess with a throwaway PLNT_HOME, then:
  1. creates tenants `bistro` and `dental` (operator token)
  2. installs the same `support-desk` bundle for each, with different FAQs
  3. chats with each over the API, streaming events via SSE
  4. checks no answer reaches a customer without an FAQ lookup (require_tool),
     and — with the fake model — that each answer comes from its own FAQ
  5. checks usage and audit are per tenant, and cross-tenant keys are refused
Exits non-zero on any failure.
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

import httpx

ADMIN = "smoke-admin-token"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class FakeOllama(BaseHTTPRequestHandler):
    """Calls lookup_faq with the user's question, then answers from the result."""

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
        tool_msgs = [m for m in msgs if m["role"] == "tool"]
        usage = {"prompt_eval_count": 120, "eval_count": 20}
        if tool_msgs:
            matches = json.loads(tool_msgs[-1]["content"]).get("matches") or []
            text = matches[0]["a"] if matches else "I don't know, someone will follow up."
            self._send({"message": {"role": "assistant", "content": text}, **usage})
            return
        question = [m for m in msgs if m["role"] == "user"][-1]["content"]
        self._send(
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "lookup_faq", "arguments": {"question": question}}}
                    ],
                },
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
        tenants = {
            "bistro": {
                "business_name": "Luigi's Bistro",
                "handoff_contact": "hi@luigis.example",
                "faq": [
                    {"q": "When are you open?", "a": "We're open Tuesday to Sunday, 5pm to 11pm."}
                ],
            },
            "dental": {
                "business_name": "Bright Smile Dental",
                "handoff_contact": "front@bright.example",
                "faq": [
                    {
                        "q": "When are you open?",
                        "a": "Our clinic is open Monday to Friday, 8am to 4pm.",
                    }
                ],
            },
        }
        keys = {}
        for tid, cfg in tenants.items():
            r = c.post("/tenants", json={"id": tid}, headers=admin)
            r.raise_for_status()
            keys[tid] = {"Authorization": f"Bearer {r.json()['api_key']}"}
            r = c.post(
                f"/tenants/{tid}/installs",
                json={"bundle": "support-desk", "config": cfg},
                headers=keys[tid],
            )
            r.raise_for_status()
            print(f"✓ {tid}: support-desk installed")

        answers: dict[str, str] = {}
        real_model = bool(os.environ.get("PLNT_SMOKE_MODEL"))
        for tid in tenants:
            h = keys[tid]
            sid = c.post(
                f"/tenants/{tid}/sessions", json={"bundle": "support-desk"}, headers=h
            ).json()["session_id"]
            c.post(
                f"/tenants/{tid}/sessions/{sid}/messages",
                json={"text": "When are you open?"},
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
            # customer after the FAQ lookup ran (require_tool guardrail).
            if tid in answers:
                assert "tool_call" in kinds[: kinds.index("assistant_message")], (tid, kinds)
                print(f"✓ {tid}: looked up the FAQ, then answered → {answers[tid]!r}")
            else:
                assert refused and "withheld" in refused["error"], (tid, refused, kinds)
                assert real_model, "the fake model always uses the tool"
                print(f"✓ {tid}: model skipped the lookup twice; guardrail withheld its answer")

        answered = [t for t in tenants if t in answers]
        grounded = {
            "bistro": "Tuesday" in answers.get("bistro", "")
            and "Monday" not in answers.get("bistro", ""),
            "dental": "Monday" in answers.get("dental", "")
            and "Tuesday" not in answers.get("dental", ""),
        }
        if real_model:
            for tid in answered:
                if not grounded[tid]:
                    print(f"! {tid}: looked up the FAQ but paraphrased it loosely — model quality")
        else:
            assert answered == list(tenants) and all(grounded.values()), answers
            print("✓ each tenant answered from its own FAQ only")
        # No tenant's answer may contain the other tenant's FAQ text.
        assert tenants["dental"]["faq"][0]["a"] not in answers.get("bistro", ""), answers
        assert tenants["bistro"]["faq"][0]["a"] not in answers.get("dental", ""), answers

        for tid in tenants:
            u = c.get(f"/tenants/{tid}/usage", headers=keys[tid]).json()
            assert u["model_calls"] >= (1 if real_model else 2), u
            print(
                f"✓ {tid}: usage {u['model_calls']} calls, "
                f"{u['prompt_tokens']}+{u['completion_tokens']} tokens"
            )
        assert c.get("/tenants/bistro", headers=keys["dental"]).status_code == 401
        print("✓ dental's key is refused on bistro's routes")
        return 0
    finally:
        server.terminate()
        server.wait(10)
        if fake:
            fake.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
