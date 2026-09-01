from __future__ import annotations

import importlib.util
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_handler(filename: str):
    path = ROOT / "api" / filename
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.handler


class RunningServer:
    def __init__(self, handler): self.server = HTTPServer(("127.0.0.1", 0), handler)
    def __enter__(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}"
    def __exit__(self, *_): self.server.shutdown(); self.thread.join(); self.server.server_close()


class HttpApiTests(unittest.TestCase):
    def test_health_get(self):
        with RunningServer(load_handler("health.py")) as url:
            with urllib.request.urlopen(url) as response:
                self.assertEqual(response.status, 200); self.assertEqual(json.load(response)["status"], "ready")

    def test_options_get(self):
        with RunningServer(load_handler("impact-options.py")) as url:
            with urllib.request.urlopen(url) as response: self.assertGreater(len(json.load(response)["countries"]), 200)

    def test_options_post_rejected_with_sanitized_json(self):
        with RunningServer(load_handler("impact-options.py")) as url:
            request = urllib.request.Request(url, data=b"{}", headers={"Content-Type":"application/json"}, method="POST")
            with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(request)
            body = json.loads(caught.exception.read())
            self.assertEqual(caught.exception.code, 405)
            self.assertEqual(body["error"]["code"], "METHOD_NOT_ALLOWED")
            self.assertNotIn("traceback", json.dumps(body).lower())

    def test_prediction_post(self):
        payload = {"country_code":"CHN","disaster_type":"Flood","disaster_subtype":"Flood (General)",
                   "event_date":"2023-07-15","date_granularity":"day","magnitude":1000,"magnitude_scale":"Km2"}
        with RunningServer(load_handler("predict-impact.py")) as url:
            request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
            with urllib.request.urlopen(request) as response:
                body=json.load(response); self.assertEqual(response.status,200); self.assertAlmostEqual(sum(body["prediction"]["probabilities"].values()),1,places=11)

    def test_prediction_get_rejected(self):
        with RunningServer(load_handler("predict-impact.py")) as url:
            with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(url)
            self.assertEqual(caught.exception.code,405)

    def test_invalid_json_is_sanitized(self):
        with RunningServer(load_handler("predict-impact.py")) as url:
            request=urllib.request.Request(url,data=b"{",headers={"Content-Type":"application/json"},method="POST")
            with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(request)
            body=json.loads(caught.exception.read()); self.assertEqual(body["error"]["code"],"INVALID_JSON"); self.assertNotIn("traceback",json.dumps(body).lower())


if __name__ == "__main__": unittest.main(verbosity=2)
