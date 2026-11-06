"""17S-45: safe, actionable HTTP failure categories without credential leaks.

No real provider credentials, network accounts, or paid requests are used.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from queue import Queue
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from varyn.gateway_chat import (
    URLS, SafeProviderHTTPError, post, prepare,
)
from varyn.model_control_center import ModelControlCenter


TASK = "SYNTHETIC: identify a fictional widget."
MODEL = "synthetic-test"
KEY = "SYNTHETIC-DO-NOT-USE-AS-A-REAL-KEY"
PRIVATE_BODY = b"PRIVATE PROVIDER BODY token=SECRET-SENTINEL"


class HTTPDiagnosticsTests(unittest.TestCase):
    def test_status_mapping_is_bounded_and_ignores_remote_reason(self):
        expected = {
            400: "bad_request",
            401: "authentication",
            402: "billing",
            403: "access_denied",
            404: "model_or_endpoint",
            408: "timeout",
            409: "conflict",
            422: "invalid_parameters",
            429: "rate_limited",
            503: "server_error",
            599: "server_error",
            418: "other_http",
        }
        for code, category in expected.items():
            with self.subTest(code=code):
                err = SafeProviderHTTPError(code)
                self.assertEqual(err.category, category)
                self.assertNotIn(str(code), str(err))
        self.assertEqual(SafeProviderHTTPError("SECRET").category, "other_http")

    def test_http_exception_body_headers_and_key_never_reach_caller(self):
        calls = []
        class Opener:
            def open(self, request, timeout):
                calls.append(request)
                raise HTTPError(
                    request.full_url, 401, "SECRET-SENTINEL",
                    {"X-Private": "SECRET-SENTINEL"},
                    BytesIO(PRIVATE_BODY),
                )
        with patch("varyn.gateway_chat.urllib.request.build_opener",
                   return_value=Opener()):
            with self.assertRaises(SafeProviderHTTPError) as caught:
                post("deepseek", prepare(MODEL, TASK, max_tokens=32), KEY, 3)
        self.assertEqual(len(calls), 1)
        self.assertEqual(caught.exception.category, "authentication")
        self.assertIsNone(caught.exception.__cause__)
        for sensitive in (KEY, "SECRET-SENTINEL", "PRIVATE PROVIDER BODY"):
            self.assertNotIn(sensitive, str(caught.exception))

    def test_real_loopback_http_error_is_sanitized_and_not_retried(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.server.request_count += 1
                size = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(size)
                self.send_response(429)
                self.end_headers()
                self.wfile.write(PRIVATE_BODY)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        server.request_count = 0
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = "http://127.0.0.1:%d/v1/chat/completions" % server.server_port
            with patch.dict(URLS, {"9router": url}):
                with self.assertRaises(SafeProviderHTTPError) as caught:
                    post("9router", prepare(MODEL, TASK, max_tokens=32), KEY, 3)
            self.assertEqual(caught.exception.category, "rate_limited")
            self.assertEqual(server.request_count, 1)
            self.assertNotIn("SECRET-SENTINEL", str(caught.exception))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_gui_worker_queue_only_receives_safe_category(self):
        class FaultingGateway:
            def generate(self, *args, **kwargs):
                raise SafeProviderHTTPError(403)
        output = Queue()
        selected = SimpleNamespace(provider="deepseek")
        ModelControlCenter._worker(
            FaultingGateway(), (selected, 0, TASK, 64, 32, 0),
            False, output,
        )
        kind, data = output.get_nowait()
        self.assertEqual((kind, data), ("http_error", "access_denied"))
        self.assertNotIn(KEY, str((kind, data)))


if __name__ == "__main__":
    unittest.main()
