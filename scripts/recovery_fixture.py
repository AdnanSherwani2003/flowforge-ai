"""Disposable-stack model stub and post-commit response-loss proxy; no real secrets."""
import json
import time
import socket
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "qwen2.5:3b-instruct"
DIGEST = "357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, value):
        data = json.dumps(value).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path == "/api/tags":
            self.send({"models": [{"name": MODEL, "digest": DIGEST}]})
        else:
            self.send({"status": "ok"})

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path.startswith("/lose/"):
            # Forward to the isolated Next.js instance, wait for its successful
            # commit response, then actually close TCP without sending HTTP.
            headers = {k: v for k, v in self.headers.items() if k.lower() in
                       {"content-type", "cookie", "origin"}}
            request = urllib.request.Request("http://frontend:3000/" + self.path[6:],
                                             data=raw, headers=headers)
            with urllib.request.urlopen(request, timeout=15) as response:
                assert response.status == 200
                response.read()
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        value = json.loads(raw)
        content = json.dumps(value.get("messages", []))
        if "INTERRUPT_FIXTURE" in content:
            time.sleep(15)
        self.send({"model": MODEL, "done": True, "done_reason": "stop",
                   "message": {"role": "assistant", "content": json.dumps({
                       "category": "billing", "priority": "medium", "reason": "Synthetic billing example."})},
                   "eval_count": 20, "prompt_eval_count": 50})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 11434), Handler).serve_forever()
