"""17O actual Windows Tk task plan button smoke, synthetic-only."""
import json
import sys
import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows Tk needed")
class TaskPlannerTkTests(unittest.TestCase):
    def test_real_task_plan_button_mutation_review_and_result(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            spec = {
                "format": "varyn.task_plan.v1",
                "steps": [
                    {"tool": "inspect_status", "arguments": {}},
                    {"tool": "stage_note", "arguments": {"text": "synthetic step"}},
                    {"tool": "inspect_status", "arguments": {}},
                ],
            }
            ui.prompt.insert("1.0", json.dumps(spec))
            found = []
            nodes = [ui]
            while nodes:
                parent = nodes.pop()
                for child in parent.winfo_children():
                    if isinstance(child, ttk.Button) and child.cget(
                        "text"
                    ) == "Run reviewed synthetic task plan (JSON)":
                        found.append(child)
                    nodes.append(child)
            self.assertEqual(len(found), 1)
            prompts = []
            with patch("varyn.desktop.messagebox.askyesno",
                       side_effect=lambda title, msg, **kwargs:
                       prompts.append(msg) or True):
                found[0].invoke()
            self.assertEqual(len(prompts), 1)
            self.assertIn("Digest:", prompts[0])
            self.assertEqual(ui._approval.status()["steps_used"], 3)
            self.assertEqual(ui._approval.status()["stored_synthetic_notes"], 1)
            screen = ui.transcript.get("1.0", "end-1c")
            self.assertIn("TASK STEP", screen)
            self.assertIn("completed", screen)
        finally:
            ui._close()


if __name__ == "__main__":
    unittest.main()
