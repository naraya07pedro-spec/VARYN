"""17S-22: real Windows Tk relay buttons, programmatic input only."""
import sys
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


@unittest.skipUnless(sys.platform == "win32", "Hosted native Windows Tk required")
class OfficialManualTkTests(unittest.TestCase):
    def test_real_buttons_copy_and_pasteback_do_not_call_api(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            ui.prompt.insert("1.0", "SYNTHETIC: test provider handoff")
            targets = {}
            children = [ui]
            while children:
                parent = children.pop()
                for widget in parent.winfo_children():
                    if isinstance(widget, ttk.Button):
                        targets[widget.cget("text")] = widget
                    children.append(widget)
            copy = targets["17S-22 | Review and copy task to official app"]
            paste = targets["17S-22 | Review pasted reply (RAM-only)"]
            reset = targets["17S-22 | Discard manual relay RAM state"]
            with patch.object(ui, "_review_manual_relay_packet",
                              return_value=False):
                copy.invoke()
            self.assertEqual(ui._official_relay.status()["hops_used"], 0)
            with patch.object(ui, "_review_manual_relay_packet",
                              return_value=True):
                copy.invoke()
            self.assertEqual(ui._official_relay.status()["hops_used"], 1)
            self.assertIn("HUMAN-MEDIATED", ui.clipboard_get())
            ui.prompt.delete("1.0", "end")
            ui.prompt.insert("1.0", "SYNTHETIC: pasted, unverified provider reply")
            with patch.object(ui, "_review_manual_reply_text",
                              return_value=True):
                paste.invoke()
            self.assertTrue(ui._official_relay.status()["reply_in_ram"])
            reset.invoke()
            self.assertFalse(ui._official_relay.status()["reply_in_ram"])
            self.assertEqual(ui.controller.status()["requests_used"], 0)
        finally:
            ui._close()

    def test_bound_return_modal_displays_outbound_receipt_and_unverified_source(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            outgoing = ui._official_relay.prepare(
                "gemini", "SYNTHETIC: outgoing task")
            ui._official_relay.decide(outgoing, approved=True, copied=True)
            review = ui._official_relay.begin_return_review(
                "SYNTHETIC: user-pasted claimed reply")
            with patch.object(ui, "_review_scrollable_manual_text",
                              return_value=False) as modal:
                self.assertFalse(ui._review_manual_reply_text(review))
            modal.assert_called_once()
            kwargs = modal.call_args.kwargs
            self.assertIn(outgoing.request_id, kwargs["heading"])
            self.assertIn("UNVERIFIED", kwargs["heading"])
            self.assertEqual(kwargs["digest"], review.reply_digest)
            self.assertEqual(kwargs["content"], review.reply_text)
            ui._official_relay.finish_return_review(review, approved=False)
            self.assertFalse(ui._official_relay.status()["reply_in_ram"])
        finally:
            ui._close()

    def test_actual_scrollable_preview_reject_button(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            draft = ui._official_relay.prepare("claude", "SYNTHETIC: preview")
            observed = {"read_only": False, "scrollbar": False,
                        "rejected_button": False}
            def close_preview():
                reject = None
                for top in ui.winfo_children():
                    if not isinstance(top, tk.Toplevel):
                        continue
                    stack = [top]
                    while stack:
                        parent = stack.pop()
                        for child in parent.winfo_children():
                            if isinstance(child, tk.Text):
                                observed["read_only"] = (
                                    child.cget("state") == "disabled" and
                                    draft.packet in child.get("1.0", "end-1c"))
                            if isinstance(child, ttk.Scrollbar):
                                observed["scrollbar"] = True
                            if (isinstance(child, ttk.Button) and
                                    child.cget("text") == "Reject"):
                                observed["rejected_button"] = True
                                reject = child
                            stack.append(child)
                if reject is not None:
                    reject.invoke()
            ui.after(100, close_preview)
            self.assertFalse(ui._review_manual_relay_packet(draft))
            self.assertTrue(all(observed.values()), repr(observed))
            ui._official_relay.discard_pending()
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
