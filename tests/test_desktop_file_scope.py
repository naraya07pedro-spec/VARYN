"""Headless synthetic tests for desktop file-consent wiring (Checkpoint 16C).

No real GUI clicks, external APIs, private files or model access.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from varyn.desktop import VarynDesktop
from varyn.file_grants import ScopedFileGrants
from varyn.agent_runtime import AgentRejected


class FakeDesktop:
    def __init__(self, grants=None):
        self._file_grants = grants if grants is not None else ScopedFileGrants()
        self._file_grant_id = None
        self._busy = False
        self._closing = False
        self.messages = []

    def _append(self, who, message):
        self.messages.append((who, message))


class DesktopFileScopeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / "example.txt").write_text("synthetic only", encoding="utf-8")
        self.ui = FakeDesktop()

    def _grant(self, folder=None, approve=True):
        with patch("varyn.desktop.filedialog.askdirectory",
                   return_value=str(folder if folder is not None else self.root)), \
             patch("varyn.desktop.messagebox.askyesno", return_value=approve) as consent:
            VarynDesktop._grant_synthetic_folder(self.ui)
            return consent.call_count

    def test_explicit_confirmation_grants_scope(self):
        self.assertEqual(self._grant(), 1)
        self.assertIsNotNone(self.ui._file_grant_id)
        status = self.ui._file_grants.status()
        self.assertEqual(status["active"], 1)
        self.assertFalse(status["model_connected"])
        self.assertFalse(status["identity_authenticated"])

    def test_decline_never_creates_grant(self):
        self._grant(approve=False)
        self.assertIsNone(self.ui._file_grant_id)
        self.assertEqual(self.ui._file_grants.status()["active"], 0)

    def test_cancel_folder_dialog_does_not_ask_for_consent(self):
        with patch("varyn.desktop.filedialog.askdirectory", return_value=""), \
             patch("varyn.desktop.messagebox.askyesno") as consent:
            VarynDesktop._grant_synthetic_folder(self.ui)
        consent.assert_not_called()
        self.assertIsNone(self.ui._file_grant_id)

    def test_invalid_folder_denied_after_confirmation(self):
        self._grant(folder=self.root / "missing")
        self.assertEqual(self.ui._file_grants.status()["active"], 0)
        self.assertTrue(any("denied" in m.lower() for _, m in self.ui.messages))

    def test_filename_count_does_not_leak_name_or_file_text(self):
        self._grant()
        VarynDesktop._inspect_synthetic_folder(self.ui)
        transcript = "\n".join(x[1] for x in self.ui.messages)
        self.assertIn("count: 1", transcript)
        self.assertNotIn("example.txt", transcript)
        self.assertNotIn("synthetic only", transcript)
        self.assertNotIn(str(self.root), transcript)

    def test_revoke_blocks_old_grant(self):
        self._grant()
        old = self.ui._file_grant_id
        VarynDesktop._revoke_synthetic_folder(self.ui)
        self.assertIsNone(self.ui._file_grant_id)
        with self.assertRaises(AgentRejected):
            self.ui._file_grants.list_files(old)
        VarynDesktop._inspect_synthetic_folder(self.ui)
        self.assertIn("No active", self.ui.messages[-1][1])

    def test_new_grant_revokes_old_grant(self):
        self._grant()
        old = self.ui._file_grant_id
        self._grant()
        self.assertNotEqual(old, self.ui._file_grant_id)
        self.assertEqual(self.ui._file_grants.status()["active"], 1)
        with self.assertRaises(AgentRejected):
            self.ui._file_grants.list_files(old)

    def test_busy_or_closing_ui_cannot_issue_grants(self):
        for field in ("_busy", "_closing"):
            ui = FakeDesktop()
            setattr(ui, field, True)
            with patch("varyn.desktop.filedialog.askdirectory") as dialog:
                VarynDesktop._grant_synthetic_folder(ui)
            dialog.assert_not_called()
            self.assertIsNone(ui._file_grant_id)

    def test_expiry_invalidates_ui_grant_without_model_access(self):
        now = [100.0]
        ui = FakeDesktop(grants=ScopedFileGrants(clock=lambda: now[0]))
        self.ui = ui
        self._grant()
        now[0] += 301
        VarynDesktop._inspect_synthetic_folder(ui)
        self.assertIsNone(ui._file_grant_id)
        self.assertIn("expired", ui.messages[-1][1])

    def test_normal_desktop_close_revokes_all_grants(self):
        from types import SimpleNamespace
        self._grant()
        old = self.ui._file_grant_id
        self.ui._lifecycle = SimpleNamespace(busy=False, close=lambda: None)
        self.ui._approval = SimpleNamespace(reject_all_pending=lambda: None)
        self.ui._agent_journal = None
        self.ui.controller = SimpleNamespace(discard_pending_history=lambda: None)
        self.ui.destroy = lambda: None
        VarynDesktop._close(self.ui)
        self.assertTrue(self.ui._closing)
        self.assertIsNone(self.ui._file_grant_id)
        with self.assertRaises(AgentRejected):
            self.ui._file_grants.list_files(old)

    def test_no_grant_contents_in_public_status(self):
        self._grant()
        VarynDesktop._inspect_synthetic_folder(self.ui)
        report = repr(self.ui._file_grants.status())
        self.assertNotIn(str(self.root), report)
        self.assertNotIn("example.txt", report)
        self.assertNotIn("synthetic only", report)


if __name__ == "__main__":
    unittest.main()
