"""Fake Ollama for the site e2e: calls the bundle's lookup tool, then answers
from its result. A message containing "slow" takes 4s, so the kill button
can be tested."""
import json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
        if "slow" in q: time.sleep(4)
        tools = {t["function"]["name"] for t in req.get("tools") or []}
        if any(m["role"] == "tool" for m in msgs):
            r = json.loads([m for m in msgs if m["role"] == "tool"][-1]["content"])
            if "matches" in r:
                text = r["matches"][0]["a"] if r["matches"] else "I don't know."
            else:
                text = "Availability: " + json.dumps(r)[:200]
            return self._send({"message": {"role": "assistant", "content": text}, **usage})
        if "lookup_faq" in tools:
            call = {"name": "lookup_faq", "arguments": {"question": q}}
        else:
            call = {"name": "check_availability", "arguments": {"date": "2026-10-03", "party_size": 2}}
        self._send({"message": {"role": "assistant", "content": "", "tool_calls": [{"function": call}]}, **usage})

ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
