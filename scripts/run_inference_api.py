from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml_inference.service import health_response, options_http_response, prediction_response

MAX_BODY_BYTES = 8192


class LocalInferenceHandler(BaseHTTPRequestHandler):
    def _json(self, status: int, body: dict) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/health":
            self._json(200, health_response())
            return
        if path == "/api/impact-options":
            status, body = options_http_response()
            self._json(status, body)
            return
        self._json(404, {"success": False, "error": {"code": "NOT_FOUND", "message": "接口不存在"}})

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/predict-impact":
            self._json(405, {"success": False, "error": {"code": "METHOD_NOT_ALLOWED", "message": "该接口不支持此请求方法"}})
            return
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

    def log_message(self, message_format: str, *args) -> None:
        # Method/path/status only; never log bodies, model internals, or secrets.
        print(f"[local-api] {self.address_string()} {message_format % args}")


if __name__ == "__main__":
    host = os.environ.get("LOCAL_API_HOST", "127.0.0.1")
    port = int(os.environ.get("LOCAL_API_PORT", "8000"))
    def stop_when_parent_pipe_closes() -> None:
        try:
            sys.stdin.buffer.read(1)
        finally:
            os._exit(0)

    if not sys.stdin.isatty():
        threading.Thread(target=stop_when_parent_pipe_closes, daemon=True).start()
    print(f"[local-api] listening on http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), LocalInferenceHandler).serve_forever()
