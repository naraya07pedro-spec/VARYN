"""Independent glossary regressions: positive and negative controls."""
import tempfile
import unittest
from pathlib import Path
from varyn.context import build_context
from varyn.lexicon import canonical_terms
from varyn.memory import MemoryStore


class BilingualRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "glossary.sqlite3"
        self.store = MemoryStore(self.path, "demo")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_indonesian_storage_retrieves_english_storage(self):
        self.store.add("VARYN", "storage location is D drive")
        result = build_context(self.path, "demo", "VARYN", "penyimpanan")
        self.assertEqual(len(result["items"]), 1)

    def test_english_backup_retrieves_indonesian_backup(self):
        self.store.add("VARYN", "cadangan database sudah dibuat")
        result = build_context(self.path, "demo", "VARYN", "backup")
        self.assertEqual(len(result["items"]), 1)

    def test_unrelated_topic_not_retrieved_via_alias(self):
        self.store.add("VARYN", "chat history only")
        result = build_context(self.path, "demo", "VARYN", "penyimpanan")
        self.assertEqual(result["status"], "no_match_in_sample")
        self.assertEqual(result["items"], [])

    def test_alias_does_not_cross_project_or_owner(self):
        self.store.add("RepoPilot", "storage private data")
        other = MemoryStore(self.path, "other")
        try:
            other.add("VARYN", "storage other user")
        finally:
            other.close()
        self.assertEqual(
            build_context(self.path, "demo", "VARYN", "penyimpanan")["items"], []
        )

    def test_unlisted_synonym_still_not_understood(self):
        self.store.add("VARYN", "storage location is D")
        self.assertEqual(
            build_context(self.path, "demo", "VARYN", "arsip")["status"],
            "no_match_in_sample",
        )

    def test_canonical_counter_casefold_and_phrase_limits(self):
        self.assertEqual(canonical_terms("PENYIMPANAN storage")["storage"], 2)
        self.assertEqual(canonical_terms("memori memory")["memory"], 2)
        self.assertEqual(canonical_terms("foo bar")["foo"], 1)


if __name__ == "__main__":
    unittest.main()
