"""17M hosted Windows genuine Tk synthetic save/search/delete controls.

Button commands are programmatically invoked, never human-clicked.
"""
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController


def buttons(root, label):
    items, found = [root], []
    while items:
        current = items.pop()
        for child in current.winfo_children():
            if isinstance(child, ttk.Button) and child.cget("text") == label:
                found.append(child)
            items.append(child)
    return found


@unittest.skipUnless(sys.platform == "win32", "Actual hosted Windows Tk required")
class DesktopMemoryWidgetTests(unittest.TestCase):
    def test_disabled_without_explicit_database(self):
        root = None
        try:
            root = VarynDesktop(controller=DesktopController())
            root.withdraw()
            for name in ("Save synthetic note", "Search project notes",
                         "Delete note ID"):
                result = buttons(root, name)
                self.assertEqual(len(result), 1)
                self.assertEqual(str(result[0].cget("state")), "disabled")
        finally:
            if root is not None:
                root._close()

    def test_real_save_search_delete_buttons_and_project_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = None
            path = Path(tmp) / "memory.sqlite3"
            try:
                root = VarynDesktop(
                    controller=DesktopController(), memory_db=path,
                )
                root.withdraw()
                root.prompt.insert("1.0", "SYNTHETIC: bounded research alpha")
                root.memory_project.set("VARYN")
                save, search, delete = (
                    buttons(root, name)[0] for name in
                    ("Save synthetic note", "Search project notes", "Delete note ID")
                )
                for control in (save, search, delete):
                    self.assertEqual(str(control.cget("state")), "normal")
                with patch("varyn.desktop.messagebox.askyesno", return_value=False):
                    save.invoke()
                self.assertEqual(root._memory.search("VARYN", "alpha"), [])
                with patch("varyn.desktop.messagebox.askyesno", return_value=True):
                    save.invoke()
                matches = root._memory.search("VARYN", "alpha")
                self.assertEqual(len(matches), 1)
                memory_id = matches[0]["id"]
                root.prompt.delete("1.0", "end")
                root.prompt.insert("1.0", "alpha")
                search.invoke()
                output = root.transcript.get("1.0", "end-1c")
                self.assertIn("SYNTHETIC: bounded research alpha", output)
                self.assertIn("Local-only search in project VARYN", output)
                self.assertEqual(root.controller.status()["requests_used"], 0)
                root.memory_project.set("OTHER")
                search.invoke()
                self.assertEqual(root._memory.search("OTHER", "alpha"), [])
                root.prompt.delete("1.0", "end")
                root.prompt.insert("1.0", str(memory_id))
                with patch("varyn.desktop.messagebox.askyesno", return_value=True):
                    delete.invoke()
                self.assertEqual(len(root._memory.search("VARYN", "alpha")), 1)
                root.memory_project.set("VARYN")
                with patch("varyn.desktop.messagebox.askyesno", return_value=True):
                    delete.invoke()
                self.assertEqual(root._memory.search("VARYN", "alpha"), [])
            finally:
                if root is not None:
                    root._close()


if __name__ == "__main__":
    unittest.main()
