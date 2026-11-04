"""17L hosted Windows REAL Tk modal -> fake role workers -> visible transcript.

No live provider, external API, owner accounts, real user data, mouse event,
or human consent. The test uses Tk's genuine registered button callbacks.
"""
import sys
import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


def _find_buttons(root, name):
    children = [root]
    result = []
    while children:
        node = children.pop()
        for child in node.winfo_children():
            if isinstance(child, ttk.Button) and child.cget("text") == name:
                result.append(child)
            children.append(child)
    return result


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows graphical Tk acceptance")
class HostedWindowsCollaborationWidgetTests(unittest.TestCase):
    def test_real_modal_three_fake_roles_and_visible_synthesis(self):
        window = None
        try:
            window = VarynDesktop(
                controller=DesktopController(allow_live_providers=False)
            )
            window.withdraw()
            window.prompt.insert("1.0", "Synthetic collaboration example")
            controls = _find_buttons(window, "Collaborate (3 roles)")
            self.assertEqual(len(controls), 1)
            with patch("varyn.desktop.messagebox.askyesno",
                       side_effect=AssertionError("No consent dialog for fake")):
                controls[0].invoke()
                windows = [
                    c for c in window.winfo_children()
                    if isinstance(c, tk.Toplevel)
                ]
                self.assertEqual(len(windows), 1)
                modal = windows[0]
                confirm = _find_buttons(modal, "Review and run 3 stages")
                self.assertEqual(len(confirm), 1)
                confirm[0].invoke()
                self.assertFalse(modal.winfo_exists())
                _, kind, _, report = window._results.get(timeout=5)
                self.assertEqual(kind, "collaboration")
                self.assertEqual(len(report["stages"]), 3)
                self.assertFalse(report["multi_model_review"])
                self.assertFalse(report["official_consumer_apps_connected"])
                window._results.put((1, kind, "", report))
                window._poll_result()
                screen = window.transcript.get("1.0", "end-1c")
                self.assertIn("COLLAB ANALYST", screen)
                self.assertIn("COLLAB CRITIC", screen)
                self.assertIn("COLLAB SYNTHESIZER", screen)
                self.assertIn("VARYN SYNTHESIS", screen)
                self.assertEqual(window.controller.status()["requests_used"], 3)
                self.assertFalse(window._busy)
                self.assertEqual(window.prompt.get("1.0", "end-1c"), "")
        finally:
            if window is not None:
                try:
                    window._close()
                except tk.TclError:
                    pass


if __name__ == "__main__":
    unittest.main()
