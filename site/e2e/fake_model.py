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
        system = "\n".join(m["content"] for m in msgs if m["role"] == "system")
        if "You are the parent agent" in system:
            # Parent decision: spawn every specialist the message needs.
            q = q.rsplit("Customer: ", 1)[-1].lower()
            agents = []
            if any(w in q for w in ("open", "parking", "vegan", "slow")):
                agents.append({"id": "support-desk", "role": "support-desk", "bundle": "support-desk",
                               "intent": "answer the question from the FAQ", "depends_on": []})
            if any(w in q for w in ("table", "book")) and "booking-desk" in system:
                agents.append({"id": "booking-desk", "role": "booking-desk", "bundle": "booking-desk",
                               "intent": "check the table request", "depends_on": []})
            dec = ({"kind": "agents", "reason": "the message needs " + " and ".join(a["role"] for a in agents),
                    "agents": agents} if agents else
                   {"kind": "chat", "reason": "small talk", "reply": "Hello! Ask me about hours or a table."})
            return self._send({"message": {"role": "assistant", "content": json.dumps(dec)}, **usage})
        if system.startswith("You write the single reply"):
            results = json.loads(q.split("Agent results:\n", 1)[-1])
            text = " ".join(str(r["answer"]) for r in results if r.get("answer"))
            return self._send({"message": {"role": "assistant", "content": text}, **usage})
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
