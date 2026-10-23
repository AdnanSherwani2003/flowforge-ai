"""Synthetic-only fault proxy. Never loaded by the business backend."""
import json
import os
import socket
import struct
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

stats = {}
lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body):
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        with lock:
            self.reply(200, dict(stats))

    def do_POST(self):
        mode = self.path.strip("/")
        data = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        with lock:
            stats[mode] = stats.get(mode, 0) + 1
        if mode == "reset":
            # Abort an established socket with TCP RST, rather than returning HTTP.
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            self.close_connection = True
            self.connection.close()
            return
        if mode in ("503", "telemetry-unavailable"):
            self.reply(503, {"detail": "SYNTHETIC_PRIVATE_ERROR_CANARY internal-topology"})
            return
        if mode == "timeout":
            time.sleep(float(os.environ.get("FAULT_DELAY_SECONDS", "6.5")))
            self.reply(504, {"detail": "Synthetic timeout"})
            return
        # Successful forwarding uses the unchanged normal backend, with fault hooks off.
        headers = {"Content-Type": "application/json"}
        for key in ("X-Correlation-ID", "X-Execution-ID", "X-FlowForge-Digest-Key"):
            if key in self.headers:
                headers[key] = self.headers[key]
        if mode == "unauthorized":
            headers["X-FlowForge-Digest-Key"] = "synthetic-invalid-key"
        req = urllib.request.Request("http://backend:8001" + os.environ.get("FAULT_BACKEND_PATH", "/api/tickets"), data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                status, body = response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            status, body = exc.code, json.load(exc)
        if mode == "after-persist" and status in (200, 201):
            with lock:
                stats["persisted"] = stats.get("persisted", 0) + 1
            time.sleep(float(os.environ.get("FAULT_DELAY_SECONDS", "6.5")))
        self.reply(status, body)


ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
