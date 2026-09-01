from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml_inference.service import health_response  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        encoded = json.dumps(health_response(), ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers(); self.wfile.write(encoded)

    def do_POST(self) -> None:
        self.send_response(405); self.end_headers()

    def log_message(self, _format: str, *_args) -> None:
        return
