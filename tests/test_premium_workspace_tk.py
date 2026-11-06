"""Premium VARYN owner surface: visual structure + real working callbacks."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.premium_workspace import PremiumOwnerHome
from varyn.premium_chat import PremiumChatSurface
from varyn.twilight_banner import TwilightBanner


@unittest.skipUnless(os.name == "nt", "Hosted Windows native Tk only")
class PremiumWorkspaceTests(unittest.TestCase):
    def test_reference_layout_cards_chat_tasks_and_history(self):
        with TemporaryDirectory() as folder:
            desktop = VarynDesktop(
                controller=DesktopController(allow_live_providers=False),
            )
            desktop.withdraw()
            owner = None
            try:
                owner = PremiumOwnerHome(
                    desktop, database_path=Path(folder)/"owner.sqlite3",
                )
                self.assertIsInstance(owner.chat_surface, PremiumChatSurface)
                self.assertIsInstance(owner.chat_surface.hero, TwilightBanner)
                self.assertEqual(
                    set(owner._nav),
                    {"chat", "tasks", "connectors", "history"},
                )
                self.assertFalse(owner.chat_surface._conversation_open)
                self.assertEqual(
                    owner.chat_surface.mode.get(), "Offline demo (not AI)",
                )
                owner.chat_surface._template()
                self.assertIn(
                    "rencana pekerjaan", owner.chat_surface.input.get("1.0", "end"),
                )
                owner.chat_surface.input.delete("1.0", "end")
                owner.chat_surface.input.insert("1.0", "Halo VARYN")
                owner.chat_surface.send_message()
                self.assertTrue(owner.chat_surface._conversation_open)
                self.assertIn(
                    "SIMULATION ONLY",
                    owner.chat_surface.chat.get("1.0", "end"),
                )
                self.assertFalse(owner.chat_surface.allow_network.get())
                owner._show("history")
                self.assertIn(
                    "Halo VARYN", owner.history_view.get("1.0", "end"),
                )
                owner.chat_surface._go_tasks()
                self.assertEqual(owner._panels["tasks"].winfo_manager(), "pack")
                owner.title_var.set("Rencana mingguan")
                owner.add()
                self.assertEqual(owner.store.count(), 1)
                owner._show("connectors")
                self.assertEqual(owner._panels["connectors"].winfo_manager(), "pack")
                self.assertEqual(
                    desktop.controller.status()["requests_used"], 0,
                )
            finally:
                if owner is not None and not owner.closed:
                    owner.close()
                desktop._close()


if __name__ == "__main__":
    unittest.main()
