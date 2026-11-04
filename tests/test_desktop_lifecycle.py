"""Headless desktop lifecycle and simulated slow provider tests."""
import threading
import unittest
from varyn.desktop_lifecycle import DesktopRequestState
from varyn.desktop_controller import DesktopController
from varyn.providers import ModelReply


class DesktopLifecycleTests(unittest.TestCase):
    def test_single_inflight_and_matched_completion(self):
        s = DesktopRequestState()
        first = s.begin()
        self.assertTrue(s.busy)
        with self.assertRaises(RuntimeError):
            s.begin()
        self.assertTrue(s.finish(first))
        self.assertFalse(s.busy)

    def test_discard_hides_old_result_but_new_result_can_complete(self):
        s = DesktopRequestState()
        original = s.begin()
        self.assertTrue(s.discard_visible())
        newer = s.begin()
        self.assertFalse(s.finish(original))
        self.assertTrue(s.busy)
        self.assertTrue(s.finish(newer))

    def test_close_rejects_delayed_response_and_new_request(self):
        s = DesktopRequestState()
        request = s.begin()
        s.close()
        self.assertFalse(s.finish(request))
        self.assertTrue(s.closed)
        with self.assertRaises(RuntimeError):
            s.begin()

    def test_duplicate_finish_rejected(self):
        s = DesktopRequestState()
        request = s.begin()
        self.assertTrue(s.finish(request))
        self.assertFalse(s.finish(request))

    def test_malformed_id_rejected(self):
        s = DesktopRequestState()
        current = s.begin()
        self.assertFalse(s.finish(True))
        self.assertTrue(s.finish(current))

    def test_discard_after_close_does_not_reopen(self):
        s = DesktopRequestState()
        s.close()
        self.assertFalse(s.discard_visible())
        self.assertFalse(s.busy)

    def test_idle_discard_does_not_allow_old_request_id(self):
        s = DesktopRequestState()
        self.assertTrue(s.discard_visible())
        fresh = s.begin()
        self.assertFalse(s.finish(fresh - 1))
        self.assertTrue(s.finish(fresh))


class SlowProviderTests(unittest.TestCase):
    def test_discard_prevents_late_reply_from_controller_history(self):
        entered = threading.Event()
        release = threading.Event()

        class Slow:
            def generate(self, question, *, model, **kwargs):
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("fixture synchronization failed")
                return ModelReply("late synthetic response", "fake", model, {})
        controller = DesktopController(
            allow_live_providers=False, providers={"fake": Slow()},
        )
        results = []
        thread = threading.Thread(
            target=lambda: results.append(controller.send("test", model="fake-test")),
            daemon=True,
        )
        thread.start()
        self.assertTrue(entered.wait(3))
        controller.discard_pending_history()
        release.set()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(results), 1)
        self.assertEqual(controller.history, ())
        self.assertEqual(controller.status()["requests_used"], 1)

    def test_clear_during_slow_request_removes_future_history(self):
        entered = threading.Event()
        release = threading.Event()

        class Slow:
            def generate(self, question, *, model, **kwargs):
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("fixture synchronization failed")
                return ModelReply("late response", "fake", model, {})
        controller = DesktopController(providers={"fake": Slow()})
        thread = threading.Thread(
            target=lambda: controller.send("test", model="fake-test"),
            daemon=True,
        )
        thread.start()
        self.assertTrue(entered.wait(3))
        controller.clear_history()
        release.set()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(controller.history, ())


if __name__ == "__main__":
    unittest.main()
