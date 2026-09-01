from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml_inference.service import options_http_response  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def _json(self, status: int, body: dict) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        status, body = options_http_response()
        self._json(status, body)

    def do_POST(self) -> None:
        self._json(405, {"success": False, "error": {"code": "METHOD_NOT_ALLOWED", "message": "输入选项接口仅支持GET"}})

    def log_message(self, _format: str, *_args) -> None:
        return
