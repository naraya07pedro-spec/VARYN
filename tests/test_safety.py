"""Synthetic credential examples only: never real tokens in tests."""
import tempfile
import unittest
from pathlib import Path

from varyn.memory import MemoryStore
from varyn.decisions import DecisionJournal
from varyn.safety import SensitiveContentError, assert_no_obvious_secrets


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "secrets-test.sqlite3"
        self.memory = MemoryStore(self.path, "demo")
        self.journal = DecisionJournal(self.path, "demo")

    def tearDown(self):
        self.journal.close()
        self.memory.close()
        self.temp.cleanup()

    def test_credential_shapes_rejected_without_echoing_value(self):
        examples = [
            "ghp_" + "A" * 24,
            "github_pat_" + "B" * 24,
            "AKIA" + "C" * 16,
            "sk-proj-" + "D" * 25,
            "-----BEGIN PRIVATE KEY-----",
            "Authorization: Bearer " + "E" * 24,
            "password=" + "notarealpassword",
            "api_key=" + "notarealkey123",
        ]
        for value in examples:
            with self.subTest(value=value[:5]):
                with self.assertRaises(SensitiveContentError) as captured:
                    assert_no_obvious_secrets(value)
                self.assertNotIn(value, str(captured.exception))

    def test_memory_rejection_does_not_persist_or_log_credential(self):
        with self.assertRaises(SensitiveContentError):
            self.memory.add("VARYN", "password=" + "synthetic1234")
        self.assertEqual(self.memory.search("password"), [])

    def test_decision_content_and_source_rejected_without_revision(self):
        for content, source in [
            ("password=" + "synthetic1234", "fixture:1"),
            ("safe summary", "api_key=" + "synthetic12345"),
        ]:
            with self.subTest(source=source[:5]), self.assertRaises(SensitiveContentError):
                self.journal.put("VARYN", "storage", content, source)
        self.assertIsNone(self.journal.current("VARYN", "storage"))

    def test_revision_and_storage_still_work_for_normal_text(self):
        memory_id = self.memory.add("VARYN", "Keep backup files separate")
        self.assertGreater(memory_id, 0)
        v1 = self.journal.put("VARYN", "backup", "Use offline backups", "fixture:1")
        self.assertEqual(v1, 1)
        self.assertEqual(self.journal.current("VARYN", "backup")["content"], "Use offline backups")

    def test_boundary_is_explicitly_incomplete(self):
        # Deliberate known false negative: scanners cannot guarantee absence.
        assert_no_obvious_secrets("credential stored under a disguised label")

    def test_non_string_inputs_fail(self):
        with self.assertRaises(TypeError):
            assert_no_obvious_secrets(None)


if __name__ == "__main__":
    unittest.main()
