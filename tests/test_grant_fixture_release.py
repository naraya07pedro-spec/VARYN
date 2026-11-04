"""17G: once-only synthetic fixture release tied to a temporary grant.

No provider connection, arbitrary user folders, model tools or real private data.
Tests run on Ubuntu and Windows and include one real one-second idle timer.
"""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from varyn.agent_runtime import AgentRejected
from varyn.file_grants import ScopedFileGrants
from varyn.synthetic_fixture import SyntheticFixture


class ReleaseHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "dummy.txt").write_text("synthetic", encoding="utf-8")
        self.clock = [100.0]
        self.grants = ScopedFileGrants(clock=lambda: self.clock[0])
        self.addCleanup(self.grants.revoke_all)

    def grant(self, **kwargs):
        return self.grants.grant(
            self.root, user_confirmed=True, **kwargs
        )

    def test_expiry_sweep_calls_hook_once_after_reader_close(self):
        state = []
        grant = self.grant(
            duration_seconds=1, on_release=lambda: state.append("release")
        )
        reader = self.grants._grants[grant.grant_id]["reader"]
        reader_close = reader.close

        def track_close():
            state.append("reader_closed")
            reader_close()

        reader.close = track_close
        self.clock[0] += 2
        self.assertEqual(self.grants.status()["active"], 0)
        self.assertEqual(state, ["reader_closed", "release"])
        self.grants.status()
        self.grants.revoke_all()
        self.assertEqual(state, ["reader_closed", "release"])

    def test_explicit_revoke_calls_hook_exactly_once(self):
        calls = []
        grant = self.grant(on_release=lambda: calls.append("close"))
        self.grants.revoke(grant.grant_id)
        with self.assertRaises(AgentRejected):
            self.grants.revoke(grant.grant_id)
        self.assertEqual(calls, ["close"])

    def test_revoke_all_calls_only_each_owning_callback(self):
        first, second = [], []
        self.grant(on_release=lambda: first.append(1))
        self.grant(on_release=lambda: second.append(2))
        self.grants.revoke_all()
        self.grants.revoke_all()
        self.assertEqual(first, [1])
        self.assertEqual(second, [2])

    def test_last_quota_use_releases_fixture_before_return(self):
        calls = []
        grant = self.grant(max_operations=1,
                           on_release=lambda: calls.append("quota"))
        self.assertEqual(
            self.grants.list_files(grant.grant_id)["files"][0]["name"],
            "dummy.txt",
        )
        self.assertEqual(calls, ["quota"])
        with self.assertRaises(PermissionError):
            self.grants.list_files(grant.grant_id)
        self.assertEqual(calls, ["quota"])

    def test_last_failed_operation_also_calls_hook(self):
        calls = []
        grant = self.grant(max_operations=1,
                           on_release=lambda: calls.append("failed"))
        with self.assertRaises(AgentRejected):
            self.grants.read_text(grant.grant_id, "../denied.txt")
        self.assertEqual(calls, ["failed"])

    def test_operation_over_deadline_releases_before_result_escape(self):
        calls = []
        grant = self.grant(duration_seconds=1,
                           on_release=lambda: calls.append("expired"))
        reader = self.grants._grants[grant.grant_id]["reader"]
        actual = reader.read_text

        def cross_deadline(name):
            result = actual(name)
            self.clock[0] += 2
            return result

        reader.read_text = cross_deadline
        with self.assertRaises(PermissionError):
            self.grants.read_text(grant.grant_id, "dummy.txt")
        self.assertEqual(calls, ["expired"])

    def test_callback_error_does_not_restore_access_or_expose_path(self):
        def bad_callback():
            raise OSError("private path should never appear in audit")

        grant = self.grant(on_release=bad_callback)
        reader = self.grants._grants[grant.grant_id]["reader"]
        self.grants.revoke(grant.grant_id)
        self.assertTrue(reader._closed)
        self.assertEqual(self.grants.status()["active"], 0)
        audit = repr(self.grants.status()["audit"])
        self.assertIn("cleanup_failed", audit)
        self.assertNotIn("private path", audit)
        self.assertNotIn(str(self.root), audit)

    def test_noncallable_release_hook_is_denied_before_grant(self):
        with self.assertRaises(ValueError):
            self.grant(on_release="not a callback")
        self.assertEqual(self.grants.status()["active"], 0)

    def test_scheduler_start_failure_releases_owned_fixture(self):
        class BrokenTimer:
            def __init__(self, delay, callback, args):
                self.daemon = False

            def start(self):
                raise RuntimeError("synthetic scheduling failure")

            def cancel(self):
                pass

        fixture = SyntheticFixture()
        root = fixture.root
        manager = ScopedFileGrants(
            auto_expire=True, timer_factory=BrokenTimer,
        )
        self.addCleanup(manager.revoke_all)
        with self.assertRaises(PermissionError):
            manager.grant(root, user_confirmed=True,
                          on_release=fixture.close)
        self.assertFalse(root.exists())
        self.assertEqual(manager.status()["active"], 0)

    def test_hook_is_not_model_connected_and_does_not_store_files(self):
        fixture = SyntheticFixture()
        self.addCleanup(fixture.close)
        grant = self.grant(on_release=fixture.close)
        status = self.grants.status()
        self.assertFalse(status["model_connected"])
        self.assertFalse(status["file_contents_logged"])
        self.assertNotIn(str(fixture.root), repr(status))
        self.assertNotIn(grant.grant_id, repr(status))
        self.grants.revoke(grant.grant_id)


class RealIdleCleanupTests(unittest.TestCase):
    def test_real_timer_closes_handle_then_deletes_fixture_without_ui(self):
        fixture = SyntheticFixture()
        self.addCleanup(fixture.close)
        manager = ScopedFileGrants(auto_expire=True)
        self.addCleanup(manager.revoke_all)
        closed = threading.Event()
        original = fixture.close

        def cleanup_and_signal():
            original()
            closed.set()

        grant = manager.grant(
            fixture.root, user_confirmed=True, duration_seconds=1,
            on_release=cleanup_and_signal,
        )
        reader = manager._grants[grant.grant_id]["reader"]
        # No status, inspection, revoke, polling, or user action before event.
        self.assertTrue(closed.wait(5), "idle grant failed to remove its fixture")
        self.assertTrue(reader._closed)
        self.assertFalse(fixture.root.exists())
        self.assertEqual(manager.status()["active"], 0)
        with self.assertRaises(AgentRejected):
            manager.list_files(grant.grant_id)

    def test_double_callback_from_competing_timer_and_revoke_is_once(self):
        fixture = SyntheticFixture()
        self.addCleanup(fixture.close)
        manager = ScopedFileGrants(auto_expire=True)
        self.addCleanup(manager.revoke_all)
        calls = []
        ended = threading.Event()
        original = fixture.close

        def cleanup():
            calls.append("cleanup")
            original()
            ended.set()

        grant = manager.grant(
            fixture.root, user_confirmed=True, duration_seconds=1,
            on_release=cleanup,
        )

        def revoke_near_expiry():
            if not ended.wait(0.5):
                try:
                    manager.revoke(grant.grant_id)
                except AgentRejected:
                    pass

        worker = threading.Thread(target=revoke_near_expiry)
        worker.start()
        self.assertTrue(ended.wait(5))
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(calls, ["cleanup"])
        self.assertFalse(fixture.root.exists())


if __name__ == "__main__":
    unittest.main()
