"""17M: explicit, project-scoped, synthetic-only desktop memory regressions."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from varyn.desktop_memory import DesktopMemory
from varyn.memory import MemoryStore


class DesktopMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "opt-in.sqlite3"

    def open(self):
        return DesktopMemory(self.path)

    def test_explicit_save_search_and_persistence_across_restart(self):
        db = self.open()
        memory_id = db.save("VARYN", "SYNTHETIC: alpha checkpoint", confirmed=True)
        self.assertEqual(db.search("VARYN", "alpha")[0]["id"], memory_id)
        db.close()
        db = self.open()
        self.assertEqual(len(db.search("VARYN", "checkpoint")), 1)
        db.close()

    def test_project_isolation_on_read_and_atomic_delete(self):
        db = self.open()
        a = db.save("VARYN", "SYNTHETIC: alpha", confirmed=True)
        b = db.save("RepoPilot", "SYNTHETIC: alpha", confirmed=True)
        self.assertEqual([x["id"] for x in db.search("VARYN", "alpha")], [a])
        self.assertEqual([x["id"] for x in db.search("RepoPilot", "alpha")], [b])
        self.assertFalse(db.delete("RepoPilot", a, confirmed=True))
        self.assertEqual([x["id"] for x in db.search("VARYN", "alpha")], [a])
        self.assertTrue(db.delete("VARYN", a, confirmed=True))
        self.assertEqual(db.search("VARYN", "alpha"), [])
        db.close()

    def test_save_requires_explicit_confirmation_and_synthetic_prefix(self):
        db = self.open()
        with self.assertRaises(PermissionError):
            db.save("VARYN", "SYNTHETIC: denied")
        with self.assertRaises(PermissionError):
            db.save("VARYN", "Personal confidential raw note", confirmed=True)
        self.assertEqual(db.search("VARYN", "denied"), [])
        db.close()

    def test_delete_requires_individual_confirmation(self):
        db = self.open()
        i = db.save("VARYN", "SYNTHETIC: cannot erase quietly", confirmed=True)
        with self.assertRaises(PermissionError):
            db.delete("VARYN", i)
        self.assertEqual(len(db.search("VARYN", "erase")), 1)
        db.close()

    def test_wrong_project_and_bad_identifiers_fail_closed(self):
        db = self.open()
        i = db.save("VARYN", "SYNTHETIC: project", confirmed=True)
        for project in ("", "../VARYN", "x/y", "A" * 41, None, 4, "X Y"):
            with self.subTest(project=project), self.assertRaises(ValueError):
                db.search(project, "project")
        for bad in (0, -1, 1.0, True, None, "1"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                db.delete("VARYN", bad, confirmed=True)
        self.assertEqual(len(db.search("VARYN", "project")), 1)
        db.close()

    def test_search_is_exact_project_and_literal_wildcard(self):
        db = self.open()
        db.save("VARYN", "SYNTHETIC: 100% ready", confirmed=True)
        db.save("VARYN", "SYNTHETIC: 100 percent ready", confirmed=True)
        db.save("OTHER", "SYNTHETIC: 100% ready", confirmed=True)
        self.assertEqual(len(db.search("VARYN", "%")), 1)
        self.assertEqual(len(db.search("OTHER", "%")), 1)
        self.assertEqual(len(db.search("VARYN", "100")), 2)
        db.close()

    def test_rejects_oversized_note_and_query(self):
        db = self.open()
        with self.assertRaises(ValueError):
            db.save("VARYN", "SYNTHETIC: " + "x" * 1001, confirmed=True)
        with self.assertRaises(ValueError):
            db.search("VARYN", "x" * 101)
        db.close()

    def test_closed_database_refuses_operations(self):
        db = self.open()
        db.close()
        with self.assertRaises(RuntimeError):
            db.search("VARYN", "test")
        with self.assertRaises(RuntimeError):
            db.save("VARYN", "SYNTHETIC: test", confirmed=True)
        with self.assertRaises(RuntimeError):
            db.delete("VARYN", 1, confirmed=True)
        db.close()

    def test_existing_symlink_database_refused(self):
        target = Path(self.tmp.name) / "target.db"
        target.write_text("sentinel", encoding="utf-8")
        try:
            self.path.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Host cannot create symlinks without privilege")
        with self.assertRaises(ValueError):
            self.open()
        self.assertEqual(target.read_text(encoding="utf-8"), "sentinel")

    def test_missing_directory_refused_without_creating_anything(self):
        path = Path(self.tmp.name) / "not-created" / "file.sqlite3"
        with self.assertRaises(ValueError):
            DesktopMemory(path)
        self.assertFalse(path.parent.exists())

    def test_no_provider_context_export_or_api_on_local_operations(self):
        with patch("varyn.multi_provider._post",
                   side_effect=AssertionError("no network")):
            db = self.open()
            db.save("VARYN", "SYNTHETIC: local note", confirmed=True)
            self.assertEqual(len(db.search("VARYN", "local")), 1)
            db.close()

    def test_underlying_existing_cli_delete_still_works(self):
        store = MemoryStore(self.path, "owner")
        i = store.add("VARYN", "SYNTHETIC: compatibility")
        self.assertTrue(store.delete(i))
        self.assertFalse(store.delete(i))
        store.close()


if __name__ == "__main__":
    unittest.main()
