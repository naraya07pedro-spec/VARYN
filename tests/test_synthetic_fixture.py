"""17F: disposable synthetic fixture ownership and cleanup, both OSes."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from varyn.synthetic_fixture import SyntheticFixture, _FIXTURE_FILES


class SyntheticFixtureTests(unittest.TestCase):
    def test_creates_only_two_known_non_sensitive_text_files(self):
        fixture = SyntheticFixture()
        self.addCleanup(fixture.close)
        self.assertEqual({path.name for path in fixture.root.iterdir()},
                         set(_FIXTURE_FILES))
        for name, text in _FIXTURE_FILES.items():
            self.assertEqual((fixture.root / name).read_text(encoding="utf-8"), text)
            self.assertTrue(name.endswith((".txt", ".md")))

    def test_close_deletes_owned_directory_and_is_idempotent(self):
        fixture = SyntheticFixture()
        root = fixture.root
        self.assertTrue(root.is_dir())
        fixture.close()
        self.assertFalse(root.exists())
        fixture.close()

    def test_fixture_cleanup_does_not_touch_neighboring_files(self):
        with tempfile.TemporaryDirectory() as outside:
            unrelated = Path(outside) / "unrelated.txt"
            unrelated.write_text("unrelated synthetic record", encoding="utf-8")
            fixture = SyntheticFixture()
            fixture.close()
            self.assertEqual(unrelated.read_text(encoding="utf-8"),
                             "unrelated synthetic record")

    def test_timer_and_ui_concurrent_close_is_idempotent(self):
        fixture = SyntheticFixture()
        root = fixture.root
        failures = []

        def close():
            try:
                fixture.close()
            except Exception as error:
                failures.append(type(error).__name__)

        workers = [threading.Thread(target=close) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(3)
            self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertFalse(root.exists())
        fixture.close()

    def test_fixture_creation_failure_does_not_leave_temp_directory(self):
        roots = []
        original = tempfile.TemporaryDirectory

        def make(*args, **kwargs):
            temp = original(*args, **kwargs)
            roots.append(Path(temp.name))
            return temp

        with patch("varyn.synthetic_fixture.TemporaryDirectory", side_effect=make), \
             patch("varyn.synthetic_fixture.Path.write_text",
                   side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                SyntheticFixture()
        self.assertEqual(len(roots), 1)
        self.assertFalse(roots[0].exists())


if __name__ == "__main__":
    unittest.main()
