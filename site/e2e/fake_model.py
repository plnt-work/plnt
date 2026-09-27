"""Fake Ollama for the site e2e and check_dist: as the parent it spawns the
right developer agents; as an agent it lists the workspace, reads a file, then
answers from what it read. A message containing "slow" takes 4s, so the kill
button can be tested."""
import json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SPECIALISTS = ("repo-explainer", "code-reviewer", "test-writer", "changelog-writer")

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200); self.send_header("Content-Type","application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._send({"models": [{"name": "fake:1b"}]})
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = req["messages"]; usage = {"prompt_eval_count": 120, "eval_count": 20}
        q = [m for m in msgs if m["role"] == "user"][-1]["content"]
        system = "\n".join(m["content"] for m in msgs if m["role"] == "system")
        if "You are the parent agent" in system:
            task = q.rsplit("User: ", 1)[-1].lower()
            agents = []
            def spawn(slug, intent, deps=()):
                if slug in system:
                    agents.append({"id": slug, "role": slug, "bundle": slug, "intent": intent,
                                   "depends_on": list(deps)})
            if any(w in task for w in ("explain", "what does", "what is", "how do", "slow")):
                spawn("repo-explainer", "explain the project")
            if any(w in task for w in ("audit", "review", "bug")):
                spawn("code-reviewer", "review the code for bugs")
            if "test" in task:
                spawn("test-writer", "write tests", ["code-reviewer"] if any(a["id"] == "code-reviewer" for a in agents) else [])
            if any(w in task for w in ("changelog", "release")):
                spawn("changelog-writer", "write the changelog entry")
            dec = ({"kind": "agents", "reason": "the task needs " + " and ".join(a["role"] for a in agents),
                    "agents": agents} if agents else
                   {"kind": "chat", "reason": "small talk", "reply": "Hello! Give me a task on this workspace."})
            return self._send({"message": {"role": "assistant", "content": json.dumps(dec)}, **usage})
        if system.startswith("You write the single reply"):
            results = json.loads(q.split("Agent results:\n", 1)[-1])
            text = "\n\n".join(f"## {r['agent']}\n{r['answer']}" for r in results if r.get("answer"))
            return self._send({"message": {"role": "assistant", "content": text}, **usage})
        if "slow" in q: time.sleep(4)
        tools = {t["function"]["name"] for t in req.get("tools") or []}
        done = [m for m in msgs if m["role"] == "tool"]
        if not done and "list_files" in tools:
            call = {"name": "list_files", "arguments": {"path": ".", "depth": 2}}
        elif len(done) < 2 and "read_file" in tools:
            call = {"name": "read_file", "arguments": {"path": "README.md"}}
        else:
            last = json.loads(done[-1]["content"]) if done else {}
            content = last.get("content", "")
            first = next((ln.split(": ", 1)[1] for ln in content.splitlines() if ": " in ln), "")
            who = "test-writer" if "test-writer" in system else "code-reviewer" if "code-reviewer" in system else "changelog-writer" if "changelog-writer" in system else "repo-explainer"
            text = {
                "repo-explainer": f"This project is {first}. Entry point: see README.md:1.",
                "code-reviewer": "## Findings\n1. medium `app/store.py:36` — the page slice drops the last item (end is exclusive).",
                "test-writer": "## Tests\n- `tests/test_store.py`: paging and delete (3 tests)\n## Result\n- not run: execute is not available here",
                "changelog-writer": "## [Unreleased]\n### Fixed\n- Paging no longer drops the last note.",
            }[who]
            return self._send({"message": {"role": "assistant", "content": text}, **usage})
        self._send({"message": {"role": "assistant", "content": "", "tool_calls": [{"function": call}]}, **usage})

ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
