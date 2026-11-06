"""Hosted Windows Tk: owner dashboard and local state, no provider calls."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.owner_home import OwnerHome


@unittest.skipUnless(os.name == "nt", "Hosted Windows Tk required")
class OwnerHomeWindowsTests(unittest.TestCase):
    def test_home_tasks_and_model_controls_are_local_by_default(self):
        with TemporaryDirectory() as folder:
            desktop=VarynDesktop(controller=DesktopController(allow_live_providers=False))
            desktop.withdraw()
            home=None
            try:
                home=OwnerHome(desktop,database_path=Path(folder)/"tasks.sqlite3")
                self.assertTrue(home.winfo_exists())
                self.assertEqual(home.store.count(),0)
                home.title_var.set("SYNTHETIC: local task example")
                home.due_var.set("2020-01-01T10:00:00+07:00")
                home.add()
                self.assertEqual(home.store.count(),1)
                home._tick()
                self.assertEqual(home.store.count(status="due"),1)
                chosen=home.table.get_children()[0]
                home.table.selection_set(chosen)
                home.change("completed")
                self.assertEqual(home.store.count(status="completed"),1)
                self.assertFalse(desktop._universal_model_live_capability)
                self.assertEqual(desktop.controller.status()["requests_used"],0)
                home._model()
                self.assertIsNotNone(desktop._model_center)
                self.assertFalse(desktop._model_center.network.get())
                self.assertFalse(desktop._model_center.real_task_opt_in.get())
            finally:
                if home is not None and not home.closed:home.close()
                desktop._close()


if __name__=="__main__":
    unittest.main()
