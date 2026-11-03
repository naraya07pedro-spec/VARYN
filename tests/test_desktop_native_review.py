"""15C headless Tkinter native proposal lifecycle integration tests."""
import queue
import unittest

from varyn.desktop import VarynDesktop
from varyn.desktop_lifecycle import DesktopRequestState
from varyn.desktop_approval import DesktopApprovalController
from varyn.native_tool_calls import NativeToolIntent


class StubButton:
    def configure(self, **kwargs):
        pass


class StubWindow:
    def __init__(self):
        self._results = queue.Queue()
        self._lifecycle = DesktopRequestState()
        self._closing = False
        self._busy = True
        self._approval = DesktopApprovalController()
        self.send_button = StubButton()
        self.preview = None
        self.delayed = []
        self.messages = []

    def _confirm_agent_proposal(self, preview):
        self.preview = preview

    def _refresh_status(self):
        pass

    def _append(self, who, text):
        self.messages.append((who, text))

    def after(self, delay, callback):
        self.delayed.append((delay, callback))


def intent(text="synthetic"):
    return NativeToolIntent("openai", "stage_note", {"text": text})


class DesktopNativeTests(unittest.TestCase):
    def test_current_result_stages_proposal_but_no_execution(self):
        w = StubWindow()
        request = w._lifecycle.begin()
        w._results.put((request, "native_intent", "", intent()))
        VarynDesktop._poll_result(w)
        self.assertIsNotNone(w.preview)
        self.assertEqual(w._approval.status()["pending_approvals"], 1)
        self.assertEqual(w._approval.status()["stored_synthetic_notes"], 0)
        self.assertFalse(w._busy)

    def test_discarded_request_stages_nothing(self):
        w = StubWindow()
        request = w._lifecycle.begin()
        w._lifecycle.discard_visible()
        w._results.put((request, "native_intent", "", intent()))
        VarynDesktop._poll_result(w)
        self.assertIsNone(w.preview)
        self.assertEqual(w._approval.status()["pending_approvals"], 0)

    def test_old_result_does_not_replace_active_request(self):
        w = StubWindow()
        stale = w._lifecycle.begin()
        w._lifecycle.discard_visible()
        current = w._lifecycle.begin()
        w._results.put((stale, "native_intent", "", intent("stale")))
        w._results.put((current, "native_intent", "", intent("current")))
        VarynDesktop._poll_result(w)
        self.assertIsNone(w.preview)
        self.assertEqual(len(w.delayed), 1)
        VarynDesktop._poll_result(w)
        self.assertIn("current", w.preview.summary)

    def test_closed_window_never_stages(self):
        w = StubWindow()
        request = w._lifecycle.begin()
        w._lifecycle.close()
        w._closing = True
        w._results.put((request, "native_intent", "", intent()))
        VarynDesktop._poll_result(w)
        self.assertEqual(w._approval.status()["pending_approvals"], 0)

    def test_human_rejection_still_blocks_native_proposal(self):
        w = StubWindow()
        request = w._lifecycle.begin()
        w._results.put((request, "native_intent", "", intent()))
        VarynDesktop._poll_result(w)
        p = w.preview
        w._approval.decide(p.proposal_id, p.digest, approved=False)
        self.assertEqual(w._approval.status()["stored_synthetic_notes"], 0)

    def test_invalid_tool_cannot_stage_even_after_network(self):
        w = StubWindow()
        request = w._lifecycle.begin()
        w._results.put((request, "native_intent", "",
                         NativeToolIntent("openai", "shell", {})))
        VarynDesktop._poll_result(w)
        self.assertIsNone(w.preview)
        self.assertEqual(w._approval.status()["pending_approvals"], 0)
        self.assertTrue(any(x[0] == "AGENT" for x in w.messages))


if __name__ == "__main__":
    unittest.main()
