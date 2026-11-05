"""17S-14 deterministic offline broker tests, including adversarial tampering.

No model calls, no external network, no real owner files or executable
commands. Every regression is portable across hosted Ubuntu and Windows.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

from varyn.bounded_broker_protocol import (
    ACTION, MAX_BYTES, VERSION, BrokerRejected, OneShotReplyVerifier,
    authenticate_request, canonical, execute_fixed_action, new_request,
    new_response, offline_child_once, strict_json,
)

_KEY = bytes(range(32))


def good():
    req = new_request(_KEY, [3, 5, 8], now=1000)
    verified = authenticate_request(req, _KEY, now=1002)
    return req, verified


class ProtocolBoundaryTests(unittest.TestCase):
    def test_roundtrip_and_one_shot_replay_refusal(self):
        req, verified = good()
        self.assertEqual(verified["action"], ACTION)
        self.assertEqual(verified["version"], VERSION)
        self.assertEqual(execute_fixed_action(verified), 16)
        signed = new_response(verified, 16, _KEY)
        verifier = OneShotReplyVerifier(req, _KEY)
        self.assertEqual(verifier.consume(canonical(signed)), 16)
        with self.assertRaises(BrokerRejected):
            verifier.consume(canonical(signed))

    def test_forged_or_wrong_nonce_response_rejected_and_consumed(self):
        req, verified = good()
        forged = new_response(verified, 16, _KEY)
        forged["total"] = 999
        gate = OneShotReplyVerifier(req, _KEY)
        with self.assertRaises(BrokerRejected):
            gate.consume(canonical(forged))
        with self.assertRaises(BrokerRejected):
            gate.consume(canonical(new_response(verified, 16, _KEY)))

        different, _ = good()
        gate2 = OneShotReplyVerifier(req, _KEY)
        mismatch = new_response(authenticate_request(
            different, _KEY, now=1001), 16, _KEY)
        with self.assertRaises(BrokerRejected):
            gate2.consume(canonical(mismatch))

    def test_modified_payload_or_wrong_key_refused(self):
        request, _ = good()
        request["payload"]["counts"].append(999)
        with self.assertRaises(BrokerRejected):
            authenticate_request(request, _KEY, now=1000)
        unmodified, _ = good()
        with self.assertRaises(BrokerRejected):
            authenticate_request(unmodified, bytes(reversed(_KEY)), now=1000)

    def test_ttl_expired_future_and_bool_timestamp(self):
        req, _ = good()
        for now in (999, 1021, True):
            with self.subTest(now=now):
                with self.assertRaises(BrokerRejected):
                    authenticate_request(req, _KEY, now=now)
        self.assertEqual(authenticate_request(req, _KEY, now=1020)["issued_at"],
                         1000)

    def test_bad_actions_types_and_payload_bounds_refused(self):
        for numbers in ([], list(range(13)), [-1], [10001],
                        [True], [1.0], [1, "3"], "a"):
            with self.subTest(numbers=numbers):
                with self.assertRaises(BrokerRejected):
                    new_request(_KEY, numbers)
        for key in (b"short", "", None):
            with self.subTest(key=key):
                with self.assertRaises(BrokerRejected):
                    new_request(key, [2])
        with self.assertRaises(BrokerRejected):
            execute_fixed_action({"action": "shell", "type": "request",
                                  "payload": {"counts": [1]}})

    def test_duplicate_nonfinite_unknown_and_oversize_json_refused(self):
        invalid = [
            b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":Infinity}',
            b"{}", b"\xff", b"[" + b"1" * (MAX_BYTES + 1) + b"]",
        ]
        for raw in invalid:
            with self.subTest(raw=raw[:30]):
                if raw == b"{}":
                    self.assertEqual(strict_json(raw), {})
                else:
                    with self.assertRaises(BrokerRejected):
                        strict_json(raw)
        req, _ = good()
        req["unknown"] = "not allowed"
        with self.assertRaises(BrokerRejected):
            authenticate_request(req, _KEY, now=1000)

    def test_parent_rejects_correctly_signed_but_incorrect_result(self):
        req, verified = good()
        response = new_response(verified, 17, _KEY)
        with self.assertRaises(BrokerRejected):
            OneShotReplyVerifier(req, _KEY).consume(canonical(response))

    def test_filesystem_one_request_one_response_exclusive_creation(self):
        with TemporaryDirectory(prefix="varyn-broker-synthetic-") as folder:
            base = Path(folder)
            key = base / "k"
            request = base / "request.json"
            response = base / "response.json"
            key.write_bytes(_KEY)
            signed = new_request(_KEY, [2, 4, 6])
            request.write_bytes(canonical(signed))
            self.assertEqual(offline_child_once(request, response, key), 0)
            gate = OneShotReplyVerifier(signed, _KEY)
            self.assertEqual(gate.consume(response.read_bytes()), 12)
            with self.assertRaises(FileExistsError):
                offline_child_once(request, response, key)
            self.assertTrue(key.exists())
            self.assertEqual(key.read_bytes(), _KEY)

    def test_stale_request_not_processed_by_child(self):
        with TemporaryDirectory(prefix="varyn-broker-expired-") as folder:
            base = Path(folder)
            key = base / "k"
            request = base / "request.json"
            response = base / "response.json"
            key.write_bytes(_KEY)
            signed = new_request(_KEY, [1], now=1)
            request.write_bytes(canonical(signed))
            with self.assertRaises(BrokerRejected):
                offline_child_once(request, response, key)
            self.assertFalse(response.exists())


if __name__ == "__main__":
    unittest.main()
