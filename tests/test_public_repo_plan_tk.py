"""17S-7 hosted Windows Tk two-step reviewed GitHub comparisons.

The actual GUI, button, callbacks and modal review flow are exercised.
All GitHub fetches are mocked; no real network calls, provider API or files.
"""
import sys
import time
import unittest
from tkinter import ttk
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.desktop_controller import DesktopController
from varyn.public_github_tool import PublicGithubToolGateway
from varyn.public_tool_worker import PublicGithubToolWorker

PAIR = ("naraya07pedro-spec/VARYN", "python/cpython")
PLAN = ('{"format":"varyn.public_repo_comparison.v1",'
        '"repositories":["naraya07pedro-spec/VARYN","python/cpython"]}')


def metadata(name):
    return {
        "format": "varyn.github_public_repo_metadata.v1",
        "repository": name, "default_branch": "main",
        "stars": 4 if name == PAIR[0] else 20,
        "open_items_including_prs": 1, "archived": False,
        "public": True, "read_only": True,
        "untrusted_external_data": True, "provider_handoff": False,
    }


@unittest.skipUnless(sys.platform == "win32", "Hosted Windows Tk display required")
class PublicRepoPlanTkTests(unittest.TestCase):
    def test_real_tk_button_requires_three_reviews_and_only_two_mocked_gets(self):
        ui = VarynDesktop(controller=DesktopController())
        try:
            ui.withdraw()
            calls = []
            ui._public_tool_worker.close()
            ui._public_github_tools = PublicGithubToolGateway(
                fetcher=lambda repo: calls.append(repo) or metadata(repo))
            ui._public_tool_worker = PublicGithubToolWorker(
                ui._public_github_tools)
            ui.consent_public_tools.set(True)
            ui.prompt.insert("1.0", PLAN)
            stack = [ui]
            buttons = []
            while stack:
                parent = stack.pop()
                for child in parent.winfo_children():
                    if (isinstance(child, ttk.Button) and child.cget("text")
                            == "Review 2-repo public GitHub comparison plan (JSON)"):
                        buttons.append(child)
                    stack.append(child)
            self.assertEqual(len(buttons), 1)
            with patch("varyn.desktop.messagebox.askyesno",
                       side_effect=[True, True, True]) as ask, patch(
                       "varyn.public_github_tool.build_opener",
                       side_effect=AssertionError("Real GitHub HTTP forbidden")):
                buttons[0].invoke()
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    ui.update()
                    if "GITHUB COMPARISON" in ui.transcript.get("1.0", "end-1c"):
                        break
                    time.sleep(0.01)
            self.assertEqual(ask.call_count, 3)
            self.assertEqual(calls, list(PAIR))
            visible = ui.transcript.get("1.0", "end-1c")
            self.assertIn("More stars: python/cpython", visible)
            self.assertIn("NOT code quality or security", visible)
            self.assertEqual(ui.controller.status()["requests_used"], 0)
            self.assertEqual(ui._public_github_tools.status()["used"], 2)
            self.assertIsNone(ui._public_comparison)
        finally:
            with patch("varyn.desktop.messagebox.askyesno", return_value=True):
                ui._close()


if __name__ == "__main__":
    unittest.main()
