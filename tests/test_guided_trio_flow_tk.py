"""17S-35 native hosted Windows Tk guided workflow and original consent gates."""
import sys
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


def button(parent, exact):
    stack = [parent]
    while stack:
        for child in stack.pop().winfo_children():
            if isinstance(child, ttk.Button) and child.cget("text") == exact:
                return child
            stack.append(child)
    raise AssertionError("Button not found: " + exact)


@unittest.skipUnless(sys.platform == "win32", "Actual hosted Windows Tk only")
class GuidedTrioTkTests(unittest.TestCase):
    def test_sequential_guided_hops_require_original_owner_review(self):
        ui = VarynDesktop(controller=DesktopController(allow_live_providers=False))
        try:
            ui.withdraw()
            ui._open_relay_workbench()
            wb = ui._relay_workbench
            start = button(wb, "17S-35 | Start three-app guided review")
            advance = button(wb, "17S-35 | Prepare next app after reviewed reply")
            copy = button(wb, "2. Review EXACT packet and copy to clipboard")
            reply = button(wb, "3. Review EXACT pasted reply and stage in RAM")
            start.invoke()
            self.assertEqual(wb._guided_flow.phase, "ready")
            self.assertEqual(wb.target.get(), "chatgpt")
            advance.invoke()
            self.assertEqual(wb._guided_flow.provider, "chatgpt")
            wb.target.set("gemini")
            with patch.object(ui, "_review_manual_relay_packet") as ask:
                copy.invoke()
            ask.assert_not_called()
            wb.target.set("chatgpt")
            with patch.object(ui, "_review_manual_relay_packet", return_value=False):
                copy.invoke()
            self.assertEqual(ui._official_relay.status()["hops_used"], 0)
            self.assertEqual(wb._guided_flow.phase, "ready")
            for ix, provider in enumerate(("chatgpt", "claude", "gemini")):
                with patch.object(ui, "_review_manual_relay_packet", return_value=True):
                    copy.invoke()
                self.assertEqual(ui._official_relay.status()["hops_used"], ix+1)
                self.assertEqual(wb._guided_flow.phase, "awaiting_reply")
                self.assertIn("SYNTHETIC:", ui.clipboard_get())
                if provider != "chatgpt":
                    self.assertIn("claimed source:", ui.clipboard_get())
                advance.invoke()
                self.assertEqual(wb.target.get(), provider)
                wb.reply.delete("1.0", "end")
                wb.reply.insert(
                    "1.0", "SYNTHETIC: USER PASTED UNVERIFIED " + provider
                )
                with patch.object(ui, "_review_manual_reply_text",
                                  return_value=False):
                    reply.invoke()
                self.assertEqual(wb._guided_flow.phase, "awaiting_reply")
                with patch.object(ui, "_review_manual_reply_text",
                                  return_value=True):
                    reply.invoke()
                self.assertEqual(
                    wb._guided_flow.phase,
                    "completed" if provider=="gemini" else "ready_next",
                )
                if ix < 2:
                    advance.invoke()
                    self.assertEqual(
                        wb.target.get(), ("claude", "gemini")[ix]
                    )
                    self.assertEqual(wb.reply.get("1.0", "end-1c"), "")
            self.assertEqual(ui.controller.status()["requests_used"], 0)
            self.assertEqual(ui._official_relay.status()["provider_requests"], 0)
            self.assertFalse(wb._guided_flow.status()["browser_delivery_verified"])
            self.assertFalse(wb._guided_flow.status()["consumer_history_sync_verified"])
            button(wb, "17S-35 | Discard guided flow and relay RAM").invoke()
            self.assertFalse(wb._guided_flow.active)
            self.assertEqual(ui._official_relay.status()["hops_used"], 0)
        finally:
            ui._close()

if __name__ == '__main__':
    unittest.main()
