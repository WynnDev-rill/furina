from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .bridge import AndroidBridge
from .chat import FurinaChat
from .config import load_config
from .routing import RoutingLLM
from .memory import MemoryStore


class Runtime:
    def __init__(self):
        self.cfg = load_config()
        self.store = MemoryStore()
        self.llm = RoutingLLM(self.cfg)
        self.chat = FurinaChat(self.cfg, self.store, self.llm)
        self.bridge = AndroidBridge(self.cfg)


RUNTIME = Runtime()


class Handler(BaseHTTPRequestHandler):
    server_version = "FurinaCore/0.2"

    def _json(self, code: int, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length", "0"))
        if n > 1_000_000:
            raise ValueError("payload too large")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "llm": RUNTIME.llm.health()})
        elif self.path == "/v1/memories":
            self._json(200, {"memories": [m.__dict__ for m in RUNTIME.store.list_memories()]})
        elif self.path == "/v1/screen":
            try:
                self._json(200, RUNTIME.bridge.screen())
            except Exception as e:
                self._json(502, {"error": str(e)})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = self._body()
            if self.path == "/v1/chat":
                text = str(body.get("message", ""))
                self._json(200, {"response": RUNTIME.chat.respond(text)})
            elif self.path == "/v1/action":
                if not body.get("approved"):
                    self._json(403, {"error": "approved=true required"})
                    return
                self._json(200, RUNTIME.bridge.action(body.get("action") or {}))
            else:
                self._json(404, {"error": "not found"})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        return


def run_server():
    cfg = RUNTIME.cfg
    ThreadingHTTPServer((cfg.core_host, cfg.core_port), Handler).serve_forever()
