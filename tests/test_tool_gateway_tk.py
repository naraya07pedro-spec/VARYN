"""17S-1 hosted Windows real Tk button wiring for disposable file tool.

Programmatic button invokes are NOT a human consent or owner-device test.
"""
import sys
import unittest
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows Tk required")
class ToolGatewayTkTests(unittest.TestCase):
    def test_real_button_grant_review_deny_read_and_revoke(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            controls, stack = {}, [ui]
            while stack:
                parent = stack.pop()
                for child in parent.winfo_children():
                    if isinstance(child, ttk.Button):
                        controls[child.cget("text")] = child
                    stack.append(child)
            grant = controls["Create & grant VARYN demo folder"]
            read = controls["Review one VARYN synthetic file read (local only)"]
            revoke = controls["Revoke test-folder grant"]
            self.assertIsNone(ui._file_grant_id)
            with patch("varyn.desktop.messagebox.askyesno", return_value=False):
                grant.invoke()
            self.assertIsNone(ui._file_grant_id)
            with patch("varyn.desktop.messagebox.askyesno", return_value=True):
                grant.invoke()
            self.assertIsNotNone(ui._file_grant_id)
            folder = str(ui._file_fixture.root)
            with patch("varyn.desktop.messagebox.askyesno", return_value=False):
                read.invoke()
            self.assertEqual(ui._synthetic_tools.status()["decisions"], 1)
            with patch("varyn.desktop.messagebox.askyesno", return_value=True) as ask:
                read.invoke()
            self.assertEqual(ask.call_count, 1)
            self.assertEqual(ui._synthetic_tools.status()["decisions"], 2)
            screen = ui.transcript.get("1.0", "end-1c")
            self.assertIn("VARYN local-only synthetic test record", screen)
            self.assertNotIn(folder, screen)
            self.assertEqual(ui.controller.status()["requests_used"], 0)
            revoke.invoke()
            self.assertIsNone(ui._file_grant_id)
            with patch("varyn.desktop.messagebox.askyesno") as ask:
                read.invoke()
            ask.assert_not_called()
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
