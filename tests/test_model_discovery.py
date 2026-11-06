"""17S-43: explicit model-list permission and REAL localhost GET protocol."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

from varyn import model_discovery
from varyn.model_discovery import (
    DiscoveryRejected, PINNED_MODEL_URLS, discover_once, get_pinned_models,
    parse_catalog, safe_model_id,
)

KEY = "SYNTHETIC-INVALID-NO-REAL-API-KEY"


def fixture(ids=("openrouter/free", "qwen/qwen3-32b")):
    return json.dumps({"data": [{"id": x, "name": "UNTRUSTED"} for x in ids]}).encode()


class CatalogParsingTests(unittest.TestCase):
    def test_only_sanitized_model_ids_not_prices_or_marketing(self):
        src = json.dumps({"data": [
            {"id": "z/last", "pricing": {"prompt": "0"}},
            {"id": "a/first", "description": "IGNORE THIS"},
            {"id": "a/first"},
            {"id": "../evil"},
            {"id": "m//bad"},
            {"id": "test\nInjected"},
            {"id": False}, {"id": 5},
            {"missing": "id"},
        ]}).encode()
        result = parse_catalog(src)
        self.assertEqual(result["model_ids"], ("a/first", "z/last"))
        self.assertEqual(result["total_sanitized_model_ids"], 2)
        self.assertEqual(result["raw_items_reported"], 9)
        self.assertFalse(result["provider_model_access_verified"])
        self.assertFalse(result["price_or_free_tier_verified"])
        self.assertFalse(result["native_consumer_history_synced"])
        self.assertNotIn("description", repr(result))
        self.assertNotIn("pricing", repr(result))

    def test_catalog_bounded_duplicated_and_invalid(self):
        self.assertTrue(safe_model_id("deepseek-v4"))
        self.assertFalse(safe_model_id("../evil"))
        for value in (b"invalid", b"[]", b'{"data":"string"}', b"", b"X" * (model_discovery.MAX_REPLY_BYTES + 1)):
            with self.subTest(value=value[:20]), self.assertRaises(DiscoveryRejected):
                parse_catalog(value)
        many = [str(x) for x in range(78)]
        result = parse_catalog(fixture(many))
        self.assertEqual(len(result["model_ids"]), 60)
        self.assertEqual(result["total_sanitized_model_ids"], 78)
        self.assertTrue(result["list_truncated"])

    def test_owner_approval_network_key_and_9router_upstream_fail_closed(self):
        calls = []
        def stub(*a):
            calls.append(a)
            return parse_catalog(fixture())
        with self.assertRaises(PermissionError):
            discover_once("deepseek", environment={"DEEPSEEK_API_KEY": KEY}, transport=stub)
        with self.assertRaises(PermissionError):
            discover_once("deepseek", owner_approved=True, network_enabled=False,
                          environment={"DEEPSEEK_API_KEY": KEY}, transport=stub)
        with self.assertRaises(DiscoveryRejected):
            discover_once("deepseek", owner_approved=True, network_enabled=True,
                          environment={}, transport=stub)
        with self.assertRaises(PermissionError):
            discover_once("9router", owner_approved=True, network_enabled=True,
                          environment={"VARYN_9ROUTER_API_KEY": KEY},
                          transport=stub)
        self.assertEqual(calls, [])
        r = discover_once("deepseek", owner_approved=True, network_enabled=True,
                          environment={"DEEPSEEK_API_KEY": KEY}, transport=stub)
        self.assertEqual(len(calls), 1)
        self.assertEqual(r["provider"], "deepseek")
        self.assertFalse(r["provider_model_access_verified"])
        self.assertFalse(r["price_or_free_tier_verified"])
        self.assertFalse(r["native_consumer_history_synced"])
        self.assertNotIn(KEY, repr(r))

    def test_forged_result_or_bad_provider_rejected(self):
        def pretend(*args):
            return {"model_ids": ("../bad",), "total_sanitized_model_ids": 1,
                    "list_truncated": False, "native_consumer_history_synced": False}
        with self.assertRaises(DiscoveryRejected):
            discover_once("openrouter", owner_approved=True, network_enabled=True,
                          environment={"OPENROUTER_API_KEY": KEY}, transport=pretend)
        with self.assertRaises(DiscoveryRejected):
            discover_once("arbitrary", owner_approved=True, network_enabled=True,
                          environment={}, transport=pretend)

    def test_exact_pinned_urls_no_custom_hosts(self):
        self.assertEqual(PINNED_MODEL_URLS["9router"],
                         "http://127.0.0.1:20128/v1/models")
        self.assertEqual(PINNED_MODEL_URLS["deepseek"],
                         "https://api.deepseek.com/models")
        self.assertEqual(PINNED_MODEL_URLS["openrouter"],
                         "https://openrouter.ai/api/v1/models")


class RealLocalGetTests(unittest.TestCase):
    def test_real_tcp_get_models_with_wrong_proxy_and_no_redirect(self):
        captured = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                captured.append((self.path, self.headers.get("Authorization")))
                raw = fixture(("cc/synthetic-one", "glm/synthetic-two"))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = "http://127.0.0.1:" + str(server.server_port) + "/v1/models"
        try:
            with patch.dict(PINNED_MODEL_URLS, {"9router": url}), \
                 patch.dict(os.environ, {
                     "HTTP_PROXY": "http://127.0.0.1:1",
                     "HTTPS_PROXY": "http://127.0.0.1:1",
                     "NO_PROXY": "",
                 }):
                result = get_pinned_models("9router", KEY, 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.assertEqual(captured, [("/v1/models", "Bearer " + KEY)])
        self.assertEqual(result["model_ids"],
                         ("cc/synthetic-one", "glm/synthetic-two"))
        self.assertFalse(result["provider_model_access_verified"])
        self.assertFalse(result["native_consumer_history_synced"])


if __name__ == "__main__":
    unittest.main()
