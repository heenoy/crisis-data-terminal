from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml_inference.service import prediction_response  # noqa: E402

MAX_BODY_BYTES = 8192


class handler(BaseHTTPRequestHandler):
    def _json(self, status: int, body: dict) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self._json(400, {"success": False, "error": {"code": "EMPTY_REQUEST", "message": "请求体不能为空"}})
            return
        if length > MAX_BODY_BYTES:
            self._json(413, {"success": False, "error": {"code": "REQUEST_TOO_LARGE", "message": "请求体超过大小限制"}})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"success": False, "error": {"code": "INVALID_JSON", "message": "请求体必须为有效JSON"}})
            return
        status, body = prediction_response(payload)
        self._json(status, body)

    def do_GET(self) -> None:
        self._json(405, {"success": False, "error": {"code": "METHOD_NOT_ALLOWED", "message": "该接口仅支持POST"}})

    def log_message(self, _format: str, *_args) -> None:
        return
