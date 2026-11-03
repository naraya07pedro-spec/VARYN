"""15C worker returns parsed intents only, no approval and no Tk calls."""
import json
import queue
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.native_tool_requests import NativeToolRequestClient


class WorkerFixture:
    def __init__(self, body):
        self._results = queue.Queue()
        self._native_client = NativeToolRequestClient(
            allow_network=True, transport=lambda *args: body)


def response():
    return json.dumps({"status": "completed", "output": [
        {"type": "function_call", "name": "stage_note",
         "arguments": json.dumps({"text": "demo"})}
    ]}).encode()


class NativeWorkerTests(unittest.TestCase):
    def test_worker_only_emits_intent_without_approval(self):
        w = WorkerFixture(response())
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic-key"}):
            VarynDesktop._native_tool_worker(w, 7, "demo", "openai", "test-model")
        request_id, kind, question, result = w._results.get_nowait()
        self.assertEqual((request_id, kind, question), (7, "native_intent", ""))
        self.assertEqual(result.tool, "stage_note")

    def test_worker_refuses_missing_key_without_native_proposal(self):
        w = WorkerFixture(response())
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            VarynDesktop._native_tool_worker(w, 7, "demo", "openai", "test-model")
        self.assertEqual(w._results.get_nowait()[1], "error")
        self.assertEqual(w._native_client.budget.snapshot()["requests_reserved"], 0)

    def test_worker_rejects_malformed_native_response(self):
        w = WorkerFixture(b"bad JSON")
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic-key"}):
            VarynDesktop._native_tool_worker(w, 7, "demo", "openai", "test-model")
        self.assertEqual(w._results.get_nowait()[1], "error")
        self.assertEqual(w._native_client.budget.snapshot()["requests_reserved"], 1)

    def test_client_request_intent_does_not_stage_anything(self):
        w = WorkerFixture(response())
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic-key"}):
            result = w._native_client.request_intent(
                "openai", "demo", model="test-model",
                confirm_external_request=True)
        self.assertEqual(result.arguments, {"text": "demo"})


if __name__ == "__main__":
    unittest.main()
