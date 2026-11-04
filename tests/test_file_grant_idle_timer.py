"""17E opt-in idle-expiry scheduler tests; disposable synthetic folders only.

No provider connection, model tool, permanent file, or process-wide daemon.
"""
import tempfile
import threading
import unittest
from pathlib import Path
from time import monotonic

from varyn.agent_runtime import AgentRejected
from varyn.file_grants import ScopedFileGrants


class FakeTimer:
    def __init__(self, delay, callback, args):
        self.delay = delay
        self.callback = callback
        self.args = args
        self.daemon = None
        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        # Can also simulate a cancelled timer callback that was already queued.
        self.callback(*self.args)


class FakeTimers:
    def __init__(self):
        self.timers = []

    def __call__(self, delay, callback, args):
        timer = FakeTimer(delay, callback, args)
        self.timers.append(timer)
        return timer


class SyntheticIdleExpiryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "test.txt").write_text("synthetic test data", encoding="utf-8")
        self.now = [100.0]
        self.timers = FakeTimers()
        self.grants = ScopedFileGrants(
            clock=lambda: self.now[0],
            auto_expire=True,
            timer_factory=self.timers,
        )
        self.addCleanup(self.grants.revoke_all)

    def grant(self, duration=4, max_operations=10):
        return self.grants.grant(
            self.root, user_confirmed=True,
            duration_seconds=duration, max_operations=max_operations,
        )

    def test_opt_in_schedules_one_daemon_timer_and_expires_while_idle(self):
        grant = self.grant(duration=4)
        reader = self.grants._grants[grant.grant_id]["reader"]
        timer = self.timers.timers[-1]
        self.assertTrue(timer.started)
        self.assertTrue(timer.daemon)
        self.assertEqual(timer.delay, 4)
        self.now[0] += 4
        timer.fire()
        self.assertTrue(reader._closed)
        self.assertIsNone(self.grants._timer)
        self.assertEqual(self.grants.status()["active"], 0)

    def test_cancelled_stale_timer_cannot_revoke_fresh_grant(self):
        old = self.grant(duration=2)
        old_timer = self.timers.timers[-1]
        newer = self.grant(duration=10)
        self.assertTrue(old_timer.cancelled)
        reader = self.grants._grants[newer.grant_id]["reader"]
        old_timer.fire()
        self.assertFalse(reader._closed)
        self.assertIn(newer.grant_id, self.grants._grants)
        # Expiring old grant is still done by the CURRENT timer.
        self.now[0] += 2
        self.timers.timers[-1].fire()
        self.assertTrue(self.grants._grants[newer.grant_id]["reader"] is reader)
        self.assertFalse(reader._closed)
        self.assertNotIn(old.grant_id, self.grants._grants)

    def test_early_timer_fire_does_not_revoke_future_grant(self):
        grant = self.grant(duration=5)
        reader = self.grants._grants[grant.grant_id]["reader"]
        timer = self.timers.timers[-1]
        self.now[0] += 3
        timer.fire()
        self.assertFalse(reader._closed)
        self.assertEqual(self.timers.timers[-1].delay, 2)

    def test_revoke_cancels_timer_and_stale_callback_is_inert(self):
        grant = self.grant()
        timer = self.timers.timers[-1]
        self.grants.revoke(grant.grant_id)
        self.assertTrue(timer.cancelled)
        self.assertIsNone(self.grants._timer)
        timer.fire()
        self.assertEqual(self.grants.status()["active"], 0)

    def test_revoke_all_cancels_timer_and_closes_readers(self):
        a, b = self.grant(), self.grant()
        readers = [self.grants._grants[g.grant_id]["reader"] for g in (a, b)]
        current_timer = self.timers.timers[-1]
        self.grants.revoke_all()
        self.assertTrue(current_timer.cancelled)
        self.assertIsNone(self.grants._timer)
        current_timer.fire()
        self.assertTrue(all(reader._closed for reader in readers))

    def test_quota_exhaustion_cancels_idle_timer(self):
        grant = self.grant(max_operations=1)
        reader = self.grants._grants[grant.grant_id]["reader"]
        self.grants.list_files(grant.grant_id)
        self.assertTrue(reader._closed)
        self.assertIsNone(self.grants._timer)
        with self.assertRaises(PermissionError):
            self.grants.list_files(grant.grant_id)

    def test_expiry_during_read_refuses_returning_content(self):
        grant = self.grant()
        reader = self.grants._grants[grant.grant_id]["reader"]
        real_read = reader.read_text

        def finish_after_deadline(name):
            value = real_read(name)
            self.now[0] += 5
            return value

        reader.read_text = finish_after_deadline
        with self.assertRaises(PermissionError):
            self.grants.read_text(grant.grant_id, "test.txt")
        self.assertTrue(reader._closed)
        self.assertIsNone(self.grants._timer)

    def test_timer_cannot_close_reader_in_active_operation(self):
        grant = self.grant()
        reader = self.grants._grants[grant.grant_id]["reader"]
        original = reader.list_files
        started = threading.Event()
        release = threading.Event()
        outcome = []

        def blocking_list():
            started.set()
            self.assertTrue(release.wait(3), "synthetic read never released")
            return original()

        reader.list_files = blocking_list

        def run_read():
            try:
                self.grants.list_files(grant.grant_id)
                outcome.append("unexpected success")
            except PermissionError:
                outcome.append("expired")

        read_thread = threading.Thread(target=run_read)
        read_thread.start()
        self.assertTrue(started.wait(3))
        self.now[0] += 5
        old_timer = self.timers.timers[-1]
        timer_thread = threading.Thread(target=old_timer.fire)
        timer_thread.start()
        release.set()
        read_thread.join(3)
        timer_thread.join(3)
        self.assertFalse(read_thread.is_alive())
        self.assertFalse(timer_thread.is_alive())
        self.assertEqual(outcome, ["expired"])
        self.assertTrue(reader._closed)

    def test_invalid_timer_configuration_is_rejected(self):
        for options in (
            {"auto_expire": 1},
            {"auto_expire": "yes"},
            {"timer_factory": object()},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                ScopedFileGrants(**options)

    def test_offline_default_does_not_create_a_timer(self):
        timers = FakeTimers()
        plain = ScopedFileGrants(
            clock=lambda: self.now[0], timer_factory=timers,
        )
        grant = plain.grant(self.root, user_confirmed=True, duration_seconds=2)
        self.assertEqual(timers.timers, [])
        self.now[0] += 2
        self.assertEqual(plain.status()["active"], 0)
        with self.assertRaises(AgentRejected):
            plain.read_text(grant.grant_id, "test.txt")
        plain.revoke_all()

    def test_public_status_hides_full_grant_and_file_contents(self):
        grant = self.grant()
        shown = repr(self.grants.status())
        self.assertNotIn(grant.grant_id, shown)
        self.assertNotIn(str(self.root), shown)
        self.assertNotIn("synthetic test data", shown)


class RealTimerExpiryTests(unittest.TestCase):
    def test_real_in_process_timer_closes_without_user_activity(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "data.txt").write_text("synthetic", encoding="utf-8")
            manager = ScopedFileGrants(auto_expire=True)
            self.addCleanup(manager.revoke_all)
            grant = manager.grant(root, user_confirmed=True, duration_seconds=1)
            reader = manager._grants[grant.grant_id]["reader"]
            closed = threading.Event()
            original = reader.close

            def signal_close():
                original()
                closed.set()

            reader.close = signal_close
            # No status/read/revoke call can itself trigger expiry before event.
            self.assertTrue(closed.wait(4.0), "idle expiry timer did not close reader")
            self.assertTrue(reader._closed)
            with self.assertRaises(AgentRejected):
                manager.list_files(grant.grant_id)


if __name__ == "__main__":
    unittest.main()
