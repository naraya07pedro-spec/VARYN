"""17S-21: native hosted Windows viewport accessibility, not owner-PC proof.

The actual Tk window must expose late-stage controls even at the supported
minimum 540x480 size. Programmatic scrolling and mock consent are not human
input or proof of a production permission boundary.
"""
import sys
from types import SimpleNamespace
import unittest
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


@unittest.skipUnless(sys.platform == "win32", "Windows hosted Tk desktop required")
class ScrollableOwnerDesktopTests(unittest.TestCase):
    def test_late_consent_button_reachable_on_minimum_window(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.geometry("540x480")
            ui.update()
            canvas = ui._page_canvas
            self.assertGreater(canvas.winfo_height(), 100)
            limits = [float(x) for x in canvas.cget("scrollregion").split()]
            self.assertEqual(len(limits), 4)
            self.assertGreater(limits[3] - limits[1], canvas.winfo_height() + 100)
            self.assertLess(canvas.yview()[0], canvas.yview()[1])
            self.assertLess(canvas.yview()[1], 1.0)

            stack = [ui]
            control = None
            while stack:
                node = stack.pop()
                for child in node.winfo_children():
                    if (isinstance(child, ttk.Button) and
                            child.cget("text") ==
                            "17S-20 | Review parent-only synthetic count"):
                        control = child
                    stack.append(child)
            self.assertIsNotNone(control)
            total_height = limits[3] - limits[1]
            max_scroll = total_height - canvas.winfo_height()
            self.assertGreater(max_scroll, 0)
            desired = max(0, control.winfo_y() - 30)
            canvas.yview_moveto(min(1.0, desired / max_scroll))
            ui.update()
            self.assertGreaterEqual(control.winfo_rooty(), canvas.winfo_rooty())
            self.assertLessEqual(
                control.winfo_rooty() + control.winfo_height(),
                canvas.winfo_rooty() + canvas.winfo_height(),
            )

            with patch("varyn.desktop.messagebox.askyesno",
                       return_value=False) as ask:
                control.invoke()
            self.assertEqual(ask.call_count, 1)
            self.assertIn(
                "Declined: no fixture content read",
                ui.transcript.get("1.0", "end-1c"),
            )
            self.assertEqual(ui.controller.status()["requests_used"], 0)
        finally:
            ui._close()

    def test_mousewheel_moves_page_but_not_while_text_widget_scrolling(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.geometry("540x480")
            ui.update()
            canvas = ui._page_canvas
            canvas.yview_moveto(0)
            ui._on_page_mousewheel(SimpleNamespace(widget=ui, delta=-120))
            ui.update()
            self.assertGreater(canvas.yview()[0], 0)
            old = canvas.yview()
            ui._on_page_mousewheel(
                SimpleNamespace(widget=ui.transcript, delta=-120))
            self.assertEqual(canvas.yview(), old)
            ui._closing = True
            ui._on_page_mousewheel(SimpleNamespace(widget=ui, delta=-120))
            self.assertEqual(canvas.yview(), old)
            ui._closing = False
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
