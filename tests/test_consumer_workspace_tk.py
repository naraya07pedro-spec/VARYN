"""VARYN consumer UX: language, native maximize, and real offline UI flows."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import unittest

from varyn.ui_language import (
    TRANSLATIONS, EN, LABELS, DEFAULT_LANGUAGE, save_language, load_language,
)


class LanguagePreferencesTests(unittest.TestCase):
    def test_translation_keys_are_complete_for_every_supported_language(self):
        self.assertEqual(DEFAULT_LANGUAGE, "en")
        self.assertEqual(len(TRANSLATIONS), 4)
        expected = set(EN)
        self.assertGreaterEqual(len(expected), 65)
        for locale, translations in TRANSLATIONS.items():
            self.assertEqual(set(translations), expected, locale)
            self.assertTrue(all(translations.values()))

    def test_local_preference_only_persists_language_code(self):
        with TemporaryDirectory() as location:
            path = Path(location) / "preferences.json"
            with patch("varyn.ui_language.config_path", return_value=path):
                self.assertEqual(load_language(), "en")
                save_language("es")
                self.assertEqual(load_language(), "es")
                self.assertIn('"language": "es"', path.read_text(encoding="utf-8"))
                with self.assertRaises(ValueError):
                    save_language("unsupported")
                self.assertEqual(load_language(), "es")


@unittest.skipUnless(os.name == "nt", "Hosted Windows Tk only")
class ConsumerDesktopTests(unittest.TestCase):
    def test_everyday_home_switches_language_and_remains_functional(self):
        from varyn.desktop import VarynDesktop
        from varyn.desktop_controller import DesktopController
        from varyn.consumer_workspace import ConsumerWorkspace
        from varyn.consumer_chat import ConsumerChat

        with TemporaryDirectory() as folder:
            with patch("varyn.consumer_workspace.load_language", return_value="en"), patch(
                "varyn.consumer_workspace.save_language"
            ):
                desktop = VarynDesktop(
                    controller=DesktopController(allow_live_providers=False),
                )
                desktop.withdraw()
                window = None
                try:
                    window = ConsumerWorkspace(
                        desktop, database_path=Path(folder) / "tasks.sqlite3",
                    )
                    self.assertIsInstance(window.chat_surface, ConsumerChat)
                    self.assertEqual(window.language, "en")
                    self.assertEqual(window._nav["tasks"].cget("text"), "Tasks")
                    self.assertEqual(window._nav["connectors"].cget("text"), "Apps")
                    self.assertIn("memory", window._nav)
                    self.assertTrue(window.telegram_token.winfo_exists())
                    self.assertIsNone(window._telegram)
                    self.assertTrue(window.memory_preview.winfo_exists())
                    self.assertTrue(window.chat_surface.input.winfo_exists())
                    self.assertEqual(window.transient(), "")
                    self.assertEqual(
                        tuple(int(v) for v in window.resizable()), (1, 1),
                    )
                    self.assertEqual(
                        window.chat_surface.heading.cget("text"),
                        EN["heading"],
                    )
                    window.language_var.set("Bahasa Indonesia")
                    window._change_language()
                    self.assertEqual(window._nav["tasks"].cget("text"), "Tugas")
                    self.assertEqual(
                        window.chat_surface.send.cget("text"), "Kirim",
                    )
                    self.assertEqual(window.chat_surface._t("offline"), "Coba offline (demo)")
                    window.language_var.set("Español")
                    window._change_language()
                    self.assertEqual(window._nav["history"].cget("text"), "Historial")
                    window.language_var.set("English")
                    window._change_language()
                    self.assertEqual(window.chat_surface.send.cget("text"), "Send")

                    window.chat_surface._template()
                    self.assertIn(
                        "my three most important priorities",
                        window.chat_surface.input.get("1.0", "end"),
                    )
                    window.chat_surface.input.delete("1.0", "end")
                    window.chat_surface.input.insert("1.0", "A real UI message")
                    window.chat_surface.send_message()
                    self.assertTrue(window.chat_surface._conversation_open)
                    self.assertIn(
                        "DEMO ONLY",
                        window.chat_surface.chat.get("1.0", "end"),
                    )
                    self.assertEqual(
                        desktop.controller.status()["requests_used"], 0,
                    )
                    self.assertFalse(window.chat_surface.allow_network.get())

                    window._show("tasks")
                    self.assertEqual(
                        window._panels["tasks"].winfo_manager(), "pack",
                    )
                    window.title_var.set("Write release notes")
                    window.add()
                    self.assertEqual(window.store.count(), 1)
                    window._show("connectors")
                    self.assertTrue(window.app_tree.get_children())
                    self.assertTrue(
                        all(window.app_tree.set(k, "status") == "Not connected"
                            for k in window.app_tree.get_children()),
                    )
                    window._show("history")
                    self.assertIn(
                        "A real UI message",
                        window.history_view.get("1.0", "end"),
                    )
                finally:
                    if window is not None and not window.closed:
                        window.close()
                    desktop._close()


if __name__ == "__main__":
    unittest.main()
