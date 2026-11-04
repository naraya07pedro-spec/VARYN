"""17S-2 hosted Windows Tk: real button, mocked public GET, no API calls."""
import sys
import time
import unittest
from threading import Event
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.public_github_tool import PublicGithubToolGateway


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows Tk required")
class PublicGithubToolTkTests(unittest.TestCase):
    def test_real_gui_requires_network_and_exact_approval(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            buttons = []
            stack = [ui]
            while stack:
                parent = stack.pop()
                for child in parent.winfo_children():
                    if (isinstance(child, ttk.Button) and
                            child.cget("text") ==
                            "Review public GitHub tool intent (JSON, network)"):
                        buttons.append(child)
                    stack.append(child)
            self.assertEqual(len(buttons), 1)
            ui.prompt.insert(
                "1.0",
                '{"format":"varyn.public_tool_intent.v1",'
                '"tool":"github_public_repo_metadata",'
                '"arguments":{"repository":"naraya07pedro-spec/VARYN"}}',
            )
            calls = []
            ui._public_github_tools = PublicGithubToolGateway(
                fetcher=lambda name: calls.append(name) or {
                    "format": "varyn.github_public_repo_metadata.v1",
                    "repository": name, "public": True, "read_only": True,
                    "provider_handoff": False, "untrusted_external_data": True,
                    "default_branch": "main",
                    "stars": 0, "open_items_including_prs": 0,
                    "archived": False,
                }
            )
            with patch("varyn.desktop.messagebox.askyesno") as ask:
                buttons[0].invoke()
            ask.assert_not_called()
            self.assertEqual(calls, [])

            # Provider-API consent remains independent and disabled.
            self.assertFalse(ui.consent_network.get())
            ui.consent_public_tools.set(True)
            with patch("varyn.desktop.messagebox.askyesno", return_value=False) as ask:
                buttons[0].invoke()
            self.assertEqual(ask.call_count, 1)
            self.assertEqual(calls, [])

            with patch("varyn.desktop.messagebox.askyesno", return_value=True) as ask:
                buttons[0].invoke()
            self.assertEqual(ask.call_count, 1)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                ui.update()  # process Tk main-thread after callbacks
                visible = ui.transcript.get("1.0", "end-1c")
                if "Public metadata" in visible:
                    break
                time.sleep(0.01)
            self.assertEqual(calls, ["naraya07pedro-spec/VARYN"])
            visible = ui.transcript.get("1.0", "end-1c")
            self.assertIn("Public metadata", visible)
            self.assertIn("default branch main", visible)
            self.assertEqual(ui.controller.status()["requests_used"], 0)
            self.assertEqual(ui._public_github_tools.status()["pending"], 0)
        finally:
            ui._close()


    def test_revocation_during_blocked_get_suppresses_gui_result(self):
        ui = VarynDesktop(controller=DesktopController())
        entered, release = Event(), Event()
        try:
            ui.withdraw()
            ui.prompt.insert(
                "1.0",
                '{"format":"varyn.public_tool_intent.v1",'
                '"tool":"github_public_repo_metadata",'
                '"arguments":{"repository":"naraya07pedro-spec/VARYN"}}',
            )
            def slow_fetch(name):
                entered.set()
                release.wait(3)
                return {
                    "format": "varyn.github_public_repo_metadata.v1",
                    "repository": name, "public": True, "read_only": True,
                    "untrusted_external_data": True, "provider_handoff": False,
                    "default_branch": "main", "stars": 1,
                    "open_items_including_prs": 0, "archived": False,
                }
            ui._public_github_tools = PublicGithubToolGateway(fetcher=slow_fetch)
            from varyn.public_tool_worker import PublicGithubToolWorker
            ui._public_tool_worker = PublicGithubToolWorker(ui._public_github_tools)
            ui.consent_public_tools.set(True)
            with patch("varyn.desktop.messagebox.askyesno", return_value=True):
                ui._review_public_github_intent()
            self.assertTrue(entered.wait(2))
            ui.consent_public_tools.set(False)
            ui._public_tool_permission_changed()
            self.assertTrue(ui._public_tool_worker.busy)
            release.set()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                ui.update()
                if not ui._public_tool_worker.busy:
                    break
                time.sleep(0.01)
            self.assertFalse(ui._public_tool_worker.busy)
            screen = ui.transcript.get("1.0", "end-1c")
            self.assertNotIn("Public metadata,", screen)
            self.assertIn("permission revoked", screen)
            self.assertEqual(ui.controller.status()["requests_used"], 0)
        finally:
            release.set()
            with patch("varyn.desktop.messagebox.askyesno", return_value=True):
                ui._close()


if __name__ == "__main__":
    unittest.main()
