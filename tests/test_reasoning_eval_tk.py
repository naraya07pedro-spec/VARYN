"""17Q actual hosted Windows Tk offline diagnostic callback smoke.

Synthetic-only, no real model, no external judge or network requests.
"""
import json
import sys
import unittest
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows Tk required")
class ReasoningEvalTkTests(unittest.TestCase):
    def test_button_enables_after_completed_collaboration_and_reports_limits(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            buttons, stack = [], [ui]
            while stack:
                current = stack.pop()
                for child in current.winfo_children():
                    if isinstance(child, ttk.Button) and child.cget(
                        "text"
                    ) == "Evaluate last collaboration":
                        buttons.append(child)
                    stack.append(child)
            self.assertEqual(len(buttons), 1)
            button = buttons[0]
            self.assertEqual(str(button.cget("state")), "disabled")
            synthetic = {
                "format": "varyn.collaboration.v1",
                "status": "completed",
                "task": "Synthetic offline example",
                "stages": [
                    {"role": "analyst", "text": "offline", "provider": "fake",
                     "model": "fake-test"},
                    {"role": "critic", "text": "consent", "provider": "fake",
                     "model": "fake-test"},
                    {"role": "synthesizer", "text": "offline consent",
                     "provider": "fake", "model": "fake-test"},
                ],
                "final_answer": "offline consent",
                "multi_model_review": False,
            }
            # Simulate an already-accepted completed synthetic report.
            ui._last_collaboration = synthetic
            button.configure(state="normal")
            rubric = json.dumps({
                "case_id": "offline_case", "required": ["offline", "consent"],
                "forbidden": [], "alternatives": [],
            })
            with patch("varyn.desktop.simpledialog.askstring", return_value=rubric):
                button.invoke()
            screen = ui.transcript.get("1.0", "end-1c")
            self.assertIn("EVAL", screen)
            self.assertIn("synthesis 2/2", screen)
            self.assertIn("NOT established", screen)
            self.assertEqual(ui.controller.status()["requests_used"], 0)
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
