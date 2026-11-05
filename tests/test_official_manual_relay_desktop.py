"""17S-22 desktop manual consumer app relay callback safety contracts.

Simulated dialog decisions and fake clipboard; never a real app session.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.official_manual_relay import OfficialManualRelay


class FakeRelayDesktop:
    def __init__(self, *, task="SYNTHETIC: handoff test", provider="chatgpt",
                 approved=True):
        self._busy = False
        self._closing = False
        self._official_relay = OfficialManualRelay(clock=lambda: 1000)
        self.official_relay_target = SimpleNamespace(get=lambda: provider)
        self.prompt = SimpleNamespace(get=lambda *args: task)
        self._review_manual_relay_packet = lambda preview: approved
        self._clipboard = "USER_EXISTING_CLIPBOARD"
        self.messages = []
        self.copies = 0

    def clipboard_clear(self):
        self._clipboard = ""

    def clipboard_append(self, value):
        self.copies += 1
        self._clipboard += value

    def _append(self, who, message):
        self.messages.append((who, message))


class OfficialManualDesktopTests(unittest.TestCase):
    def test_declined_never_touches_clipboard(self):
        ui = FakeRelayDesktop(approved=False)
        VarynDesktop._copy_official_app_relay(ui)
        self.assertEqual(ui.copies, 0)
        self.assertEqual(ui._clipboard, "USER_EXISTING_CLIPBOARD")
        self.assertIn("Declined", ui.messages[-1][1])
        self.assertEqual(ui._official_relay.status()["hops_used"], 0)

    def test_approved_packet_copies_only_to_clipboard_not_provider(self):
        ui = FakeRelayDesktop()
        with patch("varyn.multi_provider._post",
                   side_effect=AssertionError("Network must remain off")):
            VarynDesktop._copy_official_app_relay(ui)
        self.assertEqual(ui.copies, 1)
        self.assertIn("VARYN | HUMAN-MEDIATED", ui._clipboard)
        self.assertTrue(ui._official_relay.status()["awaiting_user_pasteback"])
        self.assertEqual(ui._official_relay.status()["provider_requests"], 0)
        self.assertIn("No app account access", ui.messages[-1][1])

    def test_clipboard_failure_does_not_mark_handoff_complete(self):
        ui = FakeRelayDesktop()
        def deny_copy(_):
            raise ValueError("clipboard rejected")
        ui.clipboard_append = deny_copy
        VarynDesktop._copy_official_app_relay(ui)
        self.assertFalse(ui._official_relay.status()["awaiting_user_pasteback"])
        self.assertIn("failed/expired", ui.messages[-1][1])

    def test_busy_closed_skip_authorization_and_clipboard(self):
        for name in ("_busy", "_closing"):
            ui = FakeRelayDesktop()
            setattr(ui, name, True)
            VarynDesktop._copy_official_app_relay(ui)
            self.assertEqual(ui.copies, 0)
            self.assertFalse(ui.messages)

    def test_modal_nested_close_invalidates_review(self):
        ui = FakeRelayDesktop()
        def close_during_review(preview):
            ui._closing = True
            return True
        ui._review_manual_relay_packet = close_during_review
        VarynDesktop._copy_official_app_relay(ui)
        self.assertEqual(ui.copies, 0)
        self.assertFalse(ui._official_relay.status()["awaiting_user_pasteback"])

    def test_manual_pasteback_requires_explicit_review(self):
        ui = FakeRelayDesktop(task="SYNTHETIC: copy")
        VarynDesktop._copy_official_app_relay(ui)
        ui.prompt = SimpleNamespace(get=lambda *args: "SYNTHETIC: copied reply")
        with patch("varyn.desktop.messagebox.askyesno",
                   return_value=False) as ask:
            VarynDesktop._review_official_app_reply(ui)
        self.assertEqual(ask.call_count, 1)
        self.assertFalse(ui._official_relay.status()["reply_in_ram"])
        with patch("varyn.desktop.messagebox.askyesno",
                   return_value=True) as ask:
            VarynDesktop._review_official_app_reply(ui)
        self.assertEqual(ask.call_count, 1)
        self.assertTrue(ui._official_relay.status()["reply_in_ram"])
        self.assertIn("origin NOT verified", ui.messages[-1][1])

    def test_no_pending_reply_never_prompts_for_consent(self):
        ui = FakeRelayDesktop()
        with patch("varyn.desktop.messagebox.askyesno") as ask:
            VarynDesktop._review_official_app_reply(ui)
        ask.assert_not_called()
        self.assertIn("No valid pending", ui.messages[-1][1])

    def test_reset_does_not_clear_unrelated_clipboard(self):
        ui = FakeRelayDesktop()
        VarynDesktop._copy_official_app_relay(ui)
        existing = ui._clipboard
        VarynDesktop._discard_official_app_relay(ui)
        self.assertEqual(ui._clipboard, existing)
        self.assertFalse(ui._official_relay.status()["reply_in_ram"])
        self.assertFalse(ui._official_relay.status()["awaiting_user_pasteback"])
        self.assertIn("NOT automatically cleared", ui.messages[-1][1])


if __name__ == "__main__":
    unittest.main()
