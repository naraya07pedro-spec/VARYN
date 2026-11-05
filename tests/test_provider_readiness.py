"""17S-41: readiness without HTTP, metadata-only receipts, real local TCP wire."""
import json
import os
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from varyn.gateway_chat import KEY_ENVS, reported_model, URLS
from varyn.model_registry import Offer, Registry
from varyn.provider_readiness import (
    FORMAT, ReadinessRejected, local_observation,
    readiness, receipt_json, save_new,
)
from varyn.providers import ModelReply, ProviderError
from varyn.universal_gateway import UniversalGateway


TODAY = date.today()
TOKEN = "SYNTHETIC-FAKE-KEY-NOT-REAL"


def offer(provider="openrouter", model="openrouter/free"):
    return Offer(
        provider, model, 0, 0, TODAY.isoformat(),
        owner_reviewed=True, route_fixed=True, enabled=True,
    )


def observed_result(*, reported=None):
    return {
        "reply": ModelReply(
            "SYNTHETIC: returned secret-like text NEVER SAVED",
            "openrouter", "openrouter/free",
            {"input_tokens": 12, "output_tokens": 7},
        ),
        "estimated_micro_usd": 0,
        "actual_billing_cap_enforced": False,
        "native_consumer_history_sync": False,
        "provider_reported_model": reported,
    }


class OfflineReadiness(unittest.TestCase):
    def test_no_key_and_no_permission_never_create_network_activity(self):
        q = readiness(offer(), environment={})
        self.assertFalse(q["ready_for_live_attempt"])
        self.assertEqual(q["network_calls"], 0)
        self.assertFalse(q["key_present"])
        self.assertEqual(q["key_env_name"], "OPENROUTER_API_KEY")
        self.assertIn("os_environment_credential", q["missing"])
        self.assertIn("one_request_network_permission", q["missing"])
        self.assertIn("desktop_gateway_capability", q["missing"])
        self.assertNotIn("api_key", str(q).lower())

    def test_ready_for_attempt_is_not_connected_or_verified(self):
        q = readiness(
            offer(), environment={"OPENROUTER_API_KEY": TOKEN},
            live_capability=True, enabled_network=True,
        )
        self.assertTrue(q["ready_for_live_attempt"])
        self.assertEqual(q["mode"], "attempt_only_not_connection_tested")
        self.assertFalse(q["provider_endpoint_tested"])
        self.assertFalse(q["provider_account_verified"])
        self.assertFalse(q["actual_price_verified"])
        self.assertFalse(q["native_consumer_sync"])
        self.assertNotIn(TOKEN, repr(q))
        for bad in ({"live_capability": False}, {"enabled_network": False}):
            kwargs = dict(
                live_capability=True, enabled_network=True,
                environment={"OPENROUTER_API_KEY": TOKEN},
            )
            kwargs.update(bad)
            self.assertFalse(readiness(offer(), **kwargs)["ready_for_live_attempt"])

    def test_local_9router_requires_upstream_approval_and_key(self):
        q = readiness(
            offer("9router", "cc/example"),
            live_capability=True, enabled_network=True, environment={},
        )
        self.assertFalse(q["ready_for_live_attempt"])
        self.assertIn("9router_upstream_permission", q["missing"])
        self.assertIn("os_environment_credential", q["missing"])
        q = readiness(
            offer("9router", "cc/example"),
            live_capability=True, enabled_network=True,
            upstream_authorized=True,
            environment={"VARYN_9ROUTER_API_KEY": TOKEN},
        )
        self.assertTrue(q["ready_for_live_attempt"])
        self.assertEqual(q["network_calls"], 0)

    def test_fake_is_simulation_not_external_connectivity(self):
        fake = offer("fake", "fake-test")
        q = readiness(fake, live_capability=True, enabled_network=True)
        self.assertFalse(q["ready_for_live_attempt"])
        self.assertEqual(q["mode"], "simulation_only")
        self.assertFalse(q["key_present"])


class ReceiptContracts(unittest.TestCase):
    def test_metadata_does_not_persist_prompt_response_or_credentials(self):
        data = local_observation(
            observed_result(reported="other/upstream"),
            quoted_offer=offer(),
            reported_at=datetime(2026, 11, 6, 0, 0, tzinfo=timezone.utc),
        )
        text = receipt_json(data)
        self.assertEqual(data["format"], FORMAT)
        self.assertFalse(data["provider_identity_authenticated"])
        self.assertFalse(data["native_consumer_app_history_synced"])
        self.assertFalse(data["actual_cost_verified"])
        self.assertFalse(data["selected_model_equals_reported"])
        self.assertEqual(data["provider_reported_model_UNVERIFIED"], "other/upstream")
        self.assertIsNone(data["real_amount_charged_usd"])
        self.assertEqual(data["reported_token_counters_NOT_AUDITED"]["input_tokens"], 12)
        for forbidden in ("SYNTHETIC: returned secret", TOKEN, "Authorization",
                          "user_prompt", "response_text"):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("SYNTHETIC:", text)
        self.assertLess(len(text), 4096)

    def test_immutable_authority_flags_and_schema(self):
        data = local_observation(observed_result(), quoted_offer=offer())
        for key in ("provider_identity_authenticated", "actual_cost_verified",
                    "native_consumer_app_history_synced", "credential_included"):
            with self.subTest(key=key), self.assertRaises(ReadinessRejected):
                receipt_json(dict(data, **{key: True}))
        with self.assertRaises(ReadinessRejected):
            receipt_json(dict(data, response="private model text"))
        with self.assertRaises(ReadinessRejected):
            receipt_json(dict(data, real_amount_charged_usd="0.00"))
        with self.assertRaises(ReadinessRejected):
            local_observation(observed_result(), quoted_offer=offer("fake", "fake-test"))
        with self.assertRaises(ReadinessRejected):
            local_observation(
                dict(observed_result(), actual_billing_cap_enforced=True),
                quoted_offer=offer(),
            )

    def test_new_only_json_never_overwrites(self):
        receipt = local_observation(observed_result(), quoted_offer=offer())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "acceptance.json"
            save_new(path, receipt)
            before = path.read_bytes()
            self.assertEqual(json.loads(before)["format"], FORMAT)
            with self.assertRaises(FileExistsError):
                save_new(path, receipt)
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(ReadinessRejected):
                save_new(Path(folder) / "no-extension", receipt)

    def test_provider_model_label_is_not_attested(self):
        valid = json.dumps({"model": "qwen/qwen3-32b"}).encode()
        self.assertEqual(reported_model(valid), "qwen/qwen3-32b")
        for raw in (
            b"{}", b"invalid", b'{"model":"../secret"}',
            b'{"model":"unsafe\\nHeader"}', b'{"model":25}',
            b'{"model":"a//b"}',
        ):
            self.assertIsNone(reported_model(raw))


class RealLoopbackWire(unittest.TestCase):
    def test_local_http_with_real_socket_mock_server_not_actual_9router(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                body = json.loads(self.rfile.read(length))
                received.append((self.path, self.headers.get("Authorization"), body))
                data = {
                    "model": "qwen/mock-upstream",
                    "choices": [{"finish_reason": "stop", "message": {
                        "role": "assistant", "content": "SYNTHETIC: loopback only",
                    }}],
                    "usage": {"prompt_tokens": 15, "completion_tokens": 8},
                }
                payload = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = "http://127.0.0.1:" + str(server.server_port) + "/v1/chat/completions"
        gateway = UniversalGateway(
            Registry([offer("9router", "cc/test")]), allow_network=True,
        )
        try:
            with patch.dict(URLS, {"9router": url}), \
                 patch.dict(os.environ, {
                     KEY_ENVS["9router"]: TOKEN,
                     "HTTP_PROXY": "http://127.0.0.1:1",
                     "NO_PROXY": "",
                 }):
                result = gateway.generate(
                    "SYNTHETIC: local loopback transport only",
                    input_estimate=64, max_output_tokens=64,
                    ceiling_micro_usd=0, today=TODAY, provider="9router",
                    approve_request=True, authorized_upstream=True,
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.assertEqual(len(received), 1)
        path, auth, body = received[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(auth, "Bearer " + TOKEN)
        self.assertEqual(body["model"], "cc/test")
        self.assertTrue(body["messages"][0]["content"].startswith("SYNTHETIC:"))
        self.assertEqual(result["provider_reported_model"], "qwen/mock-upstream")
        self.assertIs(result["provider_reported_model_matches_selected"], False)
        self.assertIs(result["upstream_model_identity_verified"], False)
        self.assertFalse(result["actual_billing_cap_enforced"])
        self.assertEqual(result["reply"].usage["input_tokens"], 15)
        # This only validates local HTTP serialization and proxy bypass.
        self.assertEqual(gateway.budget.snapshot()["requests_reserved"], 1)


if __name__ == "__main__":
    unittest.main()
