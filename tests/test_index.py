"""FTS5 regression cases for legacy records, maintenance, and isolation."""
import tempfile
import unittest
from pathlib import Path

from varyn.context import build_context
from varyn.memory import MemoryStore
from varyn.index import retrieve_indexed_memories, ensure_memory_index


class IndexedMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "indexed.sqlite3"
        self.memory = MemoryStore(self.path, "alice")

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def test_legacy_record_backfilled_before_limit(self):
        old_id = self.memory.add("VARYN", "storage historical original")
        for number in range(12):
            self.memory.add("VARYN", "recent unrelated entry " + str(number))
        result = build_context(
            self.path, "alice", "VARYN", "storage", max_candidates=1
        )
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["ref"], f"memory:{old_id}")

    def test_new_records_after_build_are_indexed(self):
        build_context(self.path, "alice", "VARYN", "storage")
        new_id = self.memory.add("VARYN", "storage just added")
        result = build_context(self.path, "alice", "VARYN", "storage")
        self.assertEqual(result["items"][0]["ref"], f"memory:{new_id}")

    def test_deleted_records_are_removed_from_index(self):
        mid = self.memory.add("VARYN", "storage temporary")
        build_context(self.path, "alice", "VARYN", "storage")
        self.assertTrue(self.memory.delete(mid))
        self.assertEqual(build_context(self.path, "alice", "VARYN", "storage")["items"], [])

    def test_content_update_trigger_refreshes_tokens(self):
        mid = self.memory.add("VARYN", "storage old")
        ensure_memory_index(self.memory.db)
        with self.memory.db:
            self.memory.db.execute(
                "UPDATE memories SET content=? WHERE id=?", ("backup updated", mid)
            )
        self.assertFalse(build_context(self.path, "alice", "VARYN", "storage")["items"])
        self.assertTrue(build_context(self.path, "alice", "VARYN", "backup")["items"])

    def test_owner_and_project_scoping_before_limit(self):
        self.memory.add("VARYN", "storage alice")
        other = MemoryStore(self.path, "bob")
        try:
            for index in range(10):
                other.add("VARYN", "storage bob " + str(index))
                other.add("RepoPilot", "storage bob other " + str(index))
        finally:
            other.close()
        result = build_context(
            self.path, "alice", "VARYN", "storage", max_candidates=1
        )
        self.assertEqual([item["content"] for item in result["items"]], ["storage alice"])

    def test_bilingual_expansion_finds_old_indonesian_note(self):
        self.memory.add("VARYN", "penyimpanan lama disini")
        result = build_context(self.path, "alice", "VARYN", "storage", max_candidates=1)
        self.assertEqual(result["status"], "matched")
        self.assertEqual(len(result["items"]), 1)

    def test_safe_fts_syntax_with_operator_like_words(self):
        self.memory.add("VARYN", 'storage test AND "quoted"')
        for query in ['storage OR "quote"', "storage NOT", "storage*"]:
            result = build_context(self.path, "alice", "VARYN", query)
            self.assertTrue(result["items"])

    def test_reopen_preserves_full_history_search(self):
        self.memory.add("VARYN", "storage remembered")
        build_context(self.path, "alice", "VARYN", "storage")
        self.memory.close()
        self.memory = MemoryStore(self.path, "alice")
        self.assertEqual(
            len(build_context(self.path, "alice", "VARYN", "storage")["items"]), 1
        )

    def test_many_unrelated_notes_do_not_hide_first_hit(self):
        self.memory.add("VARYN", "storage oldest relevant")
        for n in range(500):
            self.memory.add("VARYN", f"irrelevant note number {n}")
        rows = retrieve_indexed_memories(
            self.memory.db, "alice", "VARYN", "storage", 1
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["content"], "storage oldest relevant")


if __name__ == "__main__":
    unittest.main()
