"""Evidence-based selection, project isolation and exact serialized limits."""
import json
import tempfile
import unittest
from pathlib import Path
from varyn.context import build_context
from varyn.decisions import DecisionJournal
from varyn.memory import MemoryStore


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "context.sqlite3"
        self.mem = MemoryStore(self.path, "alice")
        self.dec = DecisionJournal(self.path, "alice")

    def tearDown(self):
        self.dec.close()
        self.mem.close()
        self.temp.cleanup()

    def build(self, query="storage", max_chars=4000):
        return build_context(self.path, "alice", "VARYN", query, max_chars)

    def test_relevant_memory_selected_without_unrelated_text(self):
        self.mem.add("VARYN", "storage on drive D")
        self.mem.add("VARYN", "weather is sunny")
        result = self.build()
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["type"], "memory")

    def test_only_latest_decision_is_sent(self):
        self.dec.put("VARYN", "storage", "storage old plan", "fixture:old")
        self.dec.put("VARYN", "storage", "storage latest plan", "fixture:new", 1)
        result = self.build()
        self.assertEqual([item["content"] for item in result["items"]], ["storage latest plan"])
        self.assertEqual(result["items"][0]["revision"], 2)
        self.assertFalse(result["items"][0]["source_verified"])

    def test_other_projects_and_owners_not_retrieved(self):
        self.mem.add("RepoPilot", "storage outside project")
        self.dec.put("RepoPilot", "storage", "storage other project", "fixture:1")
        other = MemoryStore(self.path, "bob")
        try:
            other.add("VARYN", "storage from another owner")
        finally:
            other.close()
        self.assertEqual(self.build()["items"], [])

    def test_relevance_prefers_more_matching_terms(self):
        self.mem.add("VARYN", "storage")
        self.mem.add("VARYN", "storage storage storage")
        result = self.build()
        self.assertEqual(result["items"][0]["content"], "storage storage storage")

    def test_budget_limits_exact_encoded_document(self):
        for i in range(20):
            self.mem.add("VARYN", f"storage record {i} " + "x" * 150)
        result = self.build(max_chars=360)
        encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertLessEqual(len(encoded), 360)
        self.assertLess(len(result["items"]), 20)

    def test_long_unfitting_record_is_skipped(self):
        self.mem.add("VARYN", "storage " + "X" * 19000)
        self.mem.add("VARYN", "storage short")
        result = self.build(max_chars=450)
        self.assertEqual([x["content"] for x in result["items"]], ["storage short"])

    def test_invalid_budget_and_query_fail_closed(self):
        with self.assertRaises(ValueError):
            self.build(max_chars=250)
        with self.assertRaises(ValueError):
            self.build(query="!!!")
        with self.assertRaises(ValueError):
            self.build(query="")

    def test_no_cross_owner_context_after_restart(self):
        self.mem.add("VARYN", "storage alpha")
        self.mem.close()
        self.dec.close()
        self.mem = MemoryStore(self.path, "alice")
        self.dec = DecisionJournal(self.path, "alice")
        self.assertTrue(self.build()["items"])
        self.assertFalse(build_context(self.path, "bob", "VARYN", "storage")["items"])


if __name__ == "__main__":
    unittest.main()
