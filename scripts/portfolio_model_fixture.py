#!/usr/bin/env python3
"""Controlled local model transport for portfolio tests; not a model-quality eval."""
import json
from http.server import ThreadingHTTPServer
from recovery_fixture import Handler, MODEL

MODE = "valid"
CALLS = 0


class PortfolioHandler(Handler):
    def do_POST(self):
        global MODE, CALLS
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path == "/fixture/mode":
            value = json.loads(raw)
            if value.get("mode") not in {"valid", "invalid", "unavailable"}:
                self.send_error(400); return
            MODE = value["mode"]
            self.send({"mode": MODE}); return
        CALLS += 1
        if MODE == "unavailable":
            self.send_error(503, "Synthetic unavailable"); return
        content = (json.dumps({"category": "billing", "priority": "medium",
                              "reason": "Controlled synthetic billing fixture."})
                   if MODE == "valid" else '{"category":"execute_a_refund","priority":"urgent","tool":"send"}')
        self.send({"model": MODEL, "done": True, "done_reason": "stop",
                   "message": {"role": "assistant", "content": content},
                   "eval_count": 20, "prompt_eval_count": 50})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 11434), PortfolioHandler).serve_forever()
