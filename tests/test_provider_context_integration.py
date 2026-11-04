"""Offline end-to-end retrieval-to-provider fixture; no network or API key."""
import sqlite3
import unittest

from varyn.context import build_context
from varyn.decisions import DecisionJournal
from varyn.memory import MemoryStore
from varyn.providers import FakeProvider, prepare_payload


class ContextAdapterIntegrationTests(unittest.TestCase):
    def test_real_retrieval_package_can_be_passed_as_untrusted_data(self):
        db = sqlite3.connect(":memory:")
        try:
            store = MemoryStore(None, "local-label", connection=db)
            journal = DecisionJournal(None, "local-label", connection=db)
            store.add("VARYN", "storage decision lookup sample")
            journal.put("VARYN", "drive", "storage on drive D", "fixture:unverified")
            package = build_context(
                None, "local-label", "VARYN", "storage",
                max_chars=1000, connection=db,
            )
            self.assertEqual(package["status"], "matched")
            self.assertEqual({x["type"] for x in package["items"]}, {"memory", "decision"})
            payload = prepare_payload("demo-model", "Where is storage?", context=package)
            self.assertEqual(payload["input"][0]["role"], "user")
            self.assertNotIn("system", [x["role"] for x in payload["input"]])
            self.assertIn("source_verified", payload["input"][0]["content"])
            with self.assertRaises(PermissionError):
                FakeProvider().generate(
                    "Where is storage?", model="demo-model", context=package
                )
            reply = FakeProvider().generate(
                "Where is storage?", model="demo-model", context=package,
                allow_context_upload=True,
            )
            self.assertEqual(reply.provider, "fake")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
