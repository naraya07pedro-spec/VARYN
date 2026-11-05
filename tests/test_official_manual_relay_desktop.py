"""17S-22 desktop manual consumer app relay callback safety contracts.

Simulated dialog decisions and fake clipboard; never a real app session.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.official_manual_relay import OfficialManualRelay
from varyn.relay_working_context import WorkingContextBoard


class FakeFlag:
    def __init__(self, value=False):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeRelayDesktop:
    def __init__(self, *, task="SYNTHETIC: handoff test", provider="chatgpt",
                 approved=True):
        self._busy = False
        self._closing = False
        self._official_relay = OfficialManualRelay(clock=lambda: 1000)
        self._working_context = WorkingContextBoard(clock=lambda: 1000)
        self.working_topic = SimpleNamespace(get=lambda: "next_step")
        self.memory_project = SimpleNamespace(get=lambda: "VARYN")
        self.include_working_context = FakeFlag(False)
        self._review_scrollable_manual_text = lambda **kwargs: approved
        self.official_relay_target = SimpleNamespace(get=lambda: provider)
        self.prompt = SimpleNamespace(get=lambda *args: task)
        self._review_manual_relay_packet = lambda preview: approved
        self._review_manual_reply_text = lambda candidate: approved
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
    def test_open_official_site_requires_separate_owner_consent(self):
        ui = FakeRelayDesktop(task="SYNTHETIC: never passed in URL",
                              provider="claude")
        with patch("varyn.desktop.messagebox.askyesno",
                   return_value=False) as approval, \
             patch("varyn.desktop.webbrowser.open_new_tab") as opener:
            VarynDesktop._open_selected_official_app(ui)
        approval.assert_called_once()
        opener.assert_not_called()
        self.assertEqual(ui._official_relay.status()["hops_used"], 0)
        self.assertIn("declined", ui.messages[-1][1])

        with patch("varyn.desktop.messagebox.askyesno",
                   return_value=True) as approval, \
             patch("varyn.desktop.webbrowser.open_new_tab",
                   return_value=True) as opener:
            VarynDesktop._open_selected_official_app(ui)
        approval.assert_called_once()
        opener.assert_called_once_with("https://claude.ai/")
        self.assertEqual(ui._official_relay.status()["hops_used"], 0)
        self.assertNotIn("never passed in URL", str(opener.call_args))
        self.assertIn("Browser launch requested", ui.messages[-1][1])

    def test_browser_failure_and_unknown_provider_cannot_claim_open(self):
        ui = FakeRelayDesktop(provider="fake")
        with patch("varyn.desktop.messagebox.askyesno") as ask, \
             patch("varyn.desktop.webbrowser.open_new_tab") as open_tab:
            VarynDesktop._open_selected_official_app(ui)
        ask.assert_not_called()
        open_tab.assert_not_called()
        self.assertIn("Unknown official app", ui.messages[-1][1])

        ui = FakeRelayDesktop(provider="gemini")
        with patch("varyn.desktop.messagebox.askyesno",
                   return_value=True), \
             patch("varyn.desktop.webbrowser.open_new_tab",
                   return_value=False) as open_tab:
            VarynDesktop._open_selected_official_app(ui)
        open_tab.assert_called_once_with("https://gemini.google.com/")
        self.assertIn("could not be launched", ui.messages[-1][1])

    def test_open_official_site_during_nested_window_close_refuses(self):
        ui = FakeRelayDesktop()
        def close_in_modal(*args, **kwargs):
            ui._closing = True
            return True
        with patch("varyn.desktop.messagebox.askyesno",
                   side_effect=close_in_modal), \
             patch("varyn.desktop.webbrowser.open_new_tab") as open_tab:
            VarynDesktop._open_selected_official_app(ui)
        open_tab.assert_not_called()

    def test_preview_expired_during_review_preserves_clipboard(self):
        ui = FakeRelayDesktop()
        def review_and_expire(preview):
            ui._official_relay._clock = lambda: preview.expires_at + 2
            return True
        ui._review_manual_relay_packet = review_and_expire
        VarynDesktop._copy_official_app_relay(ui)
        self.assertEqual(ui._clipboard, "USER_EXISTING_CLIPBOARD")
        self.assertEqual(ui.copies, 0)
        self.assertEqual(ui._official_relay.status()["hops_used"], 0)
        self.assertFalse(ui._official_relay.status()["awaiting_user_pasteback"])
        self.assertIn("failed/expired", ui.messages[-1][1])

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
        ui._review_manual_reply_text = lambda _: False
        VarynDesktop._review_official_app_reply(ui)
        self.assertFalse(ui._official_relay.status()["reply_in_ram"])
        ui._review_manual_reply_text = lambda _: True
        VarynDesktop._review_official_app_reply(ui)
        self.assertTrue(ui._official_relay.status()["reply_in_ram"])
        self.assertIn("origin NOT verified", ui.messages[-1][1])

    def test_review_ui_receipt_matches_only_active_outgoing_request(self):
        ui = FakeRelayDesktop(task="SYNTHETIC: handoff", provider="gemini")
        VarynDesktop._copy_official_app_relay(ui)
        outbound_id = ui._official_relay._awaiting_outbound[0]
        ui.prompt = SimpleNamespace(get=lambda *args: "SYNTHETIC: reply")
        observed = []
        def review(preview):
            observed.append(preview)
            self.assertEqual(preview.provider, "gemini")
            self.assertEqual(preview.outbound_request_id, outbound_id)
            self.assertEqual(preview.reply_text, "SYNTHETIC: reply")
            self.assertFalse(preview.origin_verified)
            return True
        ui._review_manual_reply_text = review
        VarynDesktop._review_official_app_reply(ui)
        self.assertEqual(len(observed), 1)
        receipt = ui._official_relay.last_return_receipt()
        self.assertEqual(receipt["outbound_request_id"], outbound_id)
        self.assertFalse(receipt["provider_origin_verified"])
        self.assertIn("locally bound receipt", ui.messages[-1][1])

    def test_discard_during_nested_return_modal_refuses_stale_receipt(self):
        ui = FakeRelayDesktop(task="SYNTHETIC: handoff")
        VarynDesktop._copy_official_app_relay(ui)
        ui.prompt = SimpleNamespace(get=lambda *args: "SYNTHETIC: reply")
        def discard_during_modal(preview):
            ui._official_relay.discard_pending()
            return True
        ui._review_manual_reply_text = discard_during_modal
        VarynDesktop._review_official_app_reply(ui)
        self.assertIsNone(ui._official_relay.last_return_receipt())
        self.assertFalse(ui._official_relay.status()["reply_in_ram"])
        self.assertIn("No valid pending handoff", ui.messages[-1][1])

    def test_return_review_expired_while_modal_open_refuses_untrusted_reply(self):
        ui = FakeRelayDesktop(task="SYNTHETIC: handoff")
        VarynDesktop._copy_official_app_relay(ui)
        ui.prompt = SimpleNamespace(get=lambda *args: "SYNTHETIC: late return")
        def wait_too_long(preview):
            ui._official_relay._clock = lambda: preview.expires_at + 2
            return True
        ui._review_manual_reply_text = wait_too_long
        VarynDesktop._review_official_app_reply(ui)
        self.assertFalse(ui._official_relay.status()["reply_in_ram"])
        self.assertIsNone(ui._official_relay.last_return_receipt())
        self.assertIn("No valid pending handoff", ui.messages[-1][1])

    def test_no_pending_reply_never_prompts_for_consent(self):
        ui = FakeRelayDesktop()
        ui._review_manual_reply_text = lambda _: self.fail(
            "Review dialog must not open without previous handoff")
        VarynDesktop._review_official_app_reply(ui)
        self.assertIn("No valid pending", ui.messages[-1][1])

    def test_owner_reviewed_project_note_requires_explicit_future_transfer(self):
        ui = FakeRelayDesktop(task="SYNTHETIC: first task")
        VarynDesktop._copy_official_app_relay(ui)
        ui.prompt = SimpleNamespace(get=lambda *args: "SYNTHETIC: pasted reply")
        VarynDesktop._review_official_app_reply(ui)
        self.assertTrue(ui._official_relay.status()["return_receipt_available"])
        ui.prompt = SimpleNamespace(
            get=lambda *args: "SYNTHETIC: owner-reviewed next task")
        VarynDesktop._review_project_working_note(ui)
        self.assertEqual(ui._working_context.status()["saved_count"], 1)
        self.assertIn("Review added", ui.messages[-1][1])

        ui.official_relay_target = SimpleNamespace(get=lambda: "claude")
        ui.prompt = SimpleNamespace(get=lambda *args: "SYNTHETIC: second task")
        VarynDesktop._copy_official_app_relay(ui)
        self.assertNotIn("TEMPORARY PROJECT NOTES", ui._clipboard)
        self.assertEqual(ui._official_relay.status()["hops_used"], 2)

    def test_owner_selected_project_note_enters_exact_clipboard_packet(self):
        ui = FakeRelayDesktop(task="SYNTHETIC: workspace note")
        VarynDesktop._review_project_working_note(ui)
        self.assertEqual(ui._working_context.status()["saved_count"], 1)
        ui.include_working_context.set(True)
        with patch("varyn.multi_provider._post",
                   side_effect=AssertionError("No API requests allowed")):
            VarynDesktop._copy_official_app_relay(ui)
        self.assertIn("HUMAN-REVIEWED TEMPORARY PROJECT NOTES", ui._clipboard)
        self.assertIn("SYNTHETIC: workspace note", ui._clipboard)
        self.assertEqual(ui._official_relay.status()["provider_requests"], 0)

    def test_conflicting_topic_requires_reading_previous_and_replace(self):
        ui = FakeRelayDesktop(task="SYNTHETIC: original")
        VarynDesktop._review_project_working_note(ui)
        ui.prompt = SimpleNamespace(get=lambda *args: "SYNTHETIC: changed")
        seen = []
        def inspect(**kwargs):
            seen.append(kwargs)
            return True
        ui._review_scrollable_manual_text = inspect
        VarynDesktop._review_project_working_note(ui)
        self.assertIn("CONFLICT", seen[-1]["heading"])
        self.assertIn("SYNTHETIC: original", seen[-1]["content"])
        self.assertIn("SYNTHETIC: changed", seen[-1]["content"])
        self.assertEqual(ui._working_context.selection("VARYN").notes[0].revision, 2)

    def test_nested_discard_during_note_review_fails_closed(self):
        ui = FakeRelayDesktop(task="SYNTHETIC: proposed")
        def dismiss(**kwargs):
            ui._working_context.reset()
            return True
        ui._review_scrollable_manual_text = dismiss
        VarynDesktop._review_project_working_note(ui)
        self.assertEqual(ui._working_context.status()["saved_count"], 0)
        self.assertIn("failed closed", ui.messages[-1][1])

    def test_explicit_discard_removes_board_and_turns_off_share(self):
        ui = FakeRelayDesktop(task="SYNTHETIC: stage only")
        VarynDesktop._review_project_working_note(ui)
        ui.include_working_context.set(True)
        VarynDesktop._discard_project_working_notes(ui)
        self.assertEqual(ui._working_context.status()["saved_count"], 0)
        self.assertFalse(ui.include_working_context.get())
        self.assertIn("clipboard bytes cannot be recalled", ui.messages[-1][1])

    def test_cross_project_board_not_silently_sent(self):
        ui = FakeRelayDesktop(task="SYNTHETIC: private-to-project-A")
        VarynDesktop._review_project_working_note(ui)
        ui.memory_project = SimpleNamespace(get=lambda: "OTHER")
        ui.include_working_context.set(True)
        original_clipboard = ui._clipboard
        VarynDesktop._copy_official_app_relay(ui)
        self.assertEqual(ui._clipboard, original_clipboard)
        self.assertEqual(ui.copies, 0)
        self.assertIn("check project context selection", ui.messages[-1][1])

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
