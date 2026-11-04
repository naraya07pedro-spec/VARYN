"""17N Windows Tk memory selection smoke, synthetic-only."""
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


@unittest.skipUnless(sys.platform == "win32", "Requires Windows graphical Tk")
class MemoryHandoffGuiTests(unittest.TestCase):
    def test_selected_note_handoff_in_real_tk(self):
        with tempfile.TemporaryDirectory() as directory:
            ui = VarynDesktop(
                controller=DesktopController(),
                memory_db=Path(directory) / "synthetic.sqlite3",
            )
            try:
                ui.withdraw()
                note_id = ui._memory.save(
                    "VARYN", "SYNTHETIC: example context", confirmed=True
                )
                ui.consent_context.set(True)
                ui._permissions_changed()
                ui.prompt.insert("1.0", "Synthetic task")
                ui._open_collaboration()
                dialog = next(c for c in ui.winfo_children()
                              if isinstance(c, tk.Toplevel))
                nodes = [dialog]
                boxes, buttons = [], []
                while nodes:
                    node = nodes.pop()
                    for child in node.winfo_children():
                        if isinstance(child, ttk.Entry):
                            boxes.append(child)
                        if isinstance(child, ttk.Button):
                            buttons.append(child)
                        nodes.append(child)
                empty = [x for x in boxes if x.get() == ""]
                self.assertEqual(len(empty), 1)
                empty[0].insert(0, str(note_id))
                approved = []
                with patch("varyn.desktop.messagebox.askyesno",
                           side_effect=lambda title, message, **kw:
                           approved.append(message) or True):
                    next(b for b in buttons if b.cget("text") ==
                         "Review and run 3 stages").invoke()
                self.assertEqual(len(approved), 1)
                self.assertIn("SYNTHETIC: example context", approved[0])
                rid, kind, _, result = ui._results.get(timeout=5)
                self.assertEqual(kind, "collaboration")
                ui._results.put((rid, kind, "", result))
                ui._poll_result()
                screen = ui.transcript.get("1.0", "end-1c")
                self.assertIn("MEMORY SOURCES", screen)
                self.assertIn("memory:" + str(note_id), screen)
            finally:
                ui._close()


if __name__ == "__main__":
    unittest.main()
