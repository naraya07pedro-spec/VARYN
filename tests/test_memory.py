"""Local memory behavior checks, using only Python's standard library."""
import tempfile
import unittest
from pathlib import Path
from varyn.memory import MemoryStore

class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "notes.sqlite3"

    def tearDown(self):
        self.tmp.cleanup()

    def test_persists_across_restart(self):
        store = MemoryStore(self.path, "owner")
        memory_id = store.add("VARYN", "Project decision alpha")
        store.close()
        store = MemoryStore(self.path, "owner")
        self.assertEqual([m["id"] for m in store.search("decision")], [memory_id])
        store.close()

    def test_owner_isolation_and_delete(self):
        a = MemoryStore(self.path, "alice")
        memory_id = a.add("personal", "private alpha")
        b = MemoryStore(self.path, "bob")
        self.assertEqual(b.search("private"), [])
        self.assertFalse(b.delete(memory_id))
        self.assertEqual(len(a.search("private")), 1)
        self.assertTrue(a.delete(memory_id))
        self.assertEqual(a.search("private"), [])
        a.close()
        b.close()

    def test_project_filter(self):
        store = MemoryStore(self.path, "alice")
        store.add("VARYN", "checkpoint A")
        store.add("RepoPilot", "checkpoint B")
        self.assertEqual(len(store.search("checkpoint", "VARYN")), 1)
        self.assertEqual(len(store.search("checkpoint")), 2)
        store.close()

    def test_literal_wildcard_and_empty_input(self):
        store = MemoryStore(self.path, "alice")
        store.add("VARYN", "100% complete")
        store.add("VARYN", "100 percent complete")
        self.assertEqual(len(store.search("%")), 1)
        with self.assertRaises(ValueError):
            store.add("VARYN", "")
        with self.assertRaises(ValueError):
            store.search("")
        store.close()

if __name__ == "__main__":
    unittest.main()
