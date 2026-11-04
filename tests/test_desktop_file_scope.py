"""17F headless desktop demo tests: host-owned synthetic folders only.

No GUI root/window, user folders, provider APIs, real sensitive files or
untrusted model tools. Scope count is never routed to any model.
"""
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from varyn.agent_runtime import AgentRejected
from varyn.desktop import VarynDesktop
from varyn.file_grants import ScopedFileGrants
from varyn.synthetic_fixture import SyntheticFixture


class FakeDesktop:
    def __init__(self, grants=None):
        self._file_grants = grants if grants is not None else ScopedFileGrants()
        self._file_grant_id = None
        self._file_fixture = None
        self._busy = False
        self._closing = False
        self.messages = []

    def _append(self, who, message):
        self.messages.append((who, message))


class DesktopSyntheticOnlyTests(unittest.TestCase):
    def setUp(self):
        self.ui = FakeDesktop()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        self.ui._file_grants.revoke_all()
        VarynDesktop._discard_synthetic_fixture(self.ui)

    def _grant(self, approve=True):
        with patch("varyn.desktop.messagebox.askyesno", return_value=approve) as consent:
            VarynDesktop._grant_synthetic_folder(self.ui)
        return consent.call_count

    def test_explicit_confirmation_creates_disposable_sample(self):
        self.assertEqual(self._grant(), 1)
        self.assertIsNotNone(self.ui._file_grant_id)
        fixture = self.ui._file_fixture
        self.assertIsNotNone(fixture)
        self.assertTrue(fixture.root.is_dir())
        self.assertEqual(
            {p.name for p in fixture.root.iterdir()},
            {"sample.txt", "notes.md"},
        )
        state = self.ui._file_grants.status()
        self.assertEqual(state["active"], 1)
        self.assertFalse(state["model_connected"])
        self.assertFalse(state["identity_authenticated"])

    def test_declined_confirmation_creates_nothing(self):
        self.assertEqual(self._grant(approve=False), 1)
        self.assertIsNone(self.ui._file_grant_id)
        self.assertIsNone(self.ui._file_fixture)
        self.assertEqual(self.ui._file_grants.status()["active"], 0)

    def test_desktop_never_opens_external_folder_picker(self):
        with patch("tkinter.filedialog.askdirectory") as picker:
            self._grant()
        picker.assert_not_called()
        self.assertTrue(self.ui._file_fixture.root.exists())

    def test_user_files_outside_generated_fixture_never_listed(self):
        with tempfile.TemporaryDirectory() as outside:
            private = Path(outside) / "private.txt"
            private.write_text("never imported", encoding="utf-8")
            self._grant()
            scope = self.ui._file_fixture.root
            self.assertNotEqual(scope, private.parent)
            VarynDesktop._inspect_synthetic_folder(self.ui)
            self.assertIn("count: 2", self.ui.messages[-1][1])
            transcript = repr(self.ui.messages)
            self.assertNotIn(str(private), transcript)
            self.assertNotIn("never imported", transcript)

    def test_create_failure_does_not_issue_grant(self):
        with patch("varyn.desktop.SyntheticFixture", side_effect=OSError("synthetic")):
            self._grant()
        self.assertIsNone(self.ui._file_fixture)
        self.assertIsNone(self.ui._file_grant_id)
        self.assertEqual(self.ui._file_grants.status()["active"], 0)
        self.assertTrue(any("denied" in m.lower() for _, m in self.ui.messages))

    def test_grant_failure_cleans_new_fixture(self):
        generated = []
        original = SyntheticFixture

        def create():
            instance = original()
            generated.append(instance)
            return instance

        with patch("varyn.desktop.SyntheticFixture", side_effect=create), \
             patch.object(self.ui._file_grants, "grant", side_effect=ValueError("deny")):
            self._grant()
        self.assertEqual(len(generated), 1)
        self.assertFalse(generated[0].root.exists())
        self.assertIsNone(self.ui._file_grant_id)

    def test_filename_count_does_not_leak_names_or_text(self):
        self._grant()
        VarynDesktop._inspect_synthetic_folder(self.ui)
        transcript = repr(self.ui.messages)
        self.assertIn("count: 2", transcript)
        self.assertNotIn("sample.txt", transcript)
        self.assertNotIn("notes.md", transcript)
        self.assertNotIn("VARYN local-only synthetic test record.", transcript)
        self.assertNotIn(str(self.ui._file_fixture.root), transcript)

    def test_revoke_closes_grant_and_deletes_its_fixture(self):
        self._grant()
        old = self.ui._file_grant_id
        root = self.ui._file_fixture.root
        VarynDesktop._revoke_synthetic_folder(self.ui)
        self.assertIsNone(self.ui._file_grant_id)
        self.assertIsNone(self.ui._file_fixture)
        self.assertFalse(root.exists())
        with self.assertRaises(AgentRejected):
            self.ui._file_grants.list_files(old)
        VarynDesktop._inspect_synthetic_folder(self.ui)
        self.assertIn("No active", self.ui.messages[-1][1])

    def test_replacement_revokes_and_cleans_previous_fixture(self):
        self._grant()
        old = self.ui._file_grant_id
        former = self.ui._file_fixture.root
        self._grant()
        self.assertNotEqual(old, self.ui._file_grant_id)
        self.assertFalse(former.exists())
        self.assertTrue(self.ui._file_fixture.root.exists())
        self.assertEqual(self.ui._file_grants.status()["active"], 1)
        with self.assertRaises(AgentRejected):
            self.ui._file_grants.list_files(old)

    def test_busy_or_closing_ui_cannot_issue_grants(self):
        for attribute in ("_busy", "_closing"):
            ui = FakeDesktop()
            setattr(ui, attribute, True)
            with patch("varyn.desktop.messagebox.askyesno") as dialog:
                VarynDesktop._grant_synthetic_folder(ui)
            dialog.assert_not_called()
            self.assertIsNone(ui._file_grant_id)
            self.assertIsNone(ui._file_fixture)

    def test_expiry_invalidates_grant_and_deletes_fixture_on_inspect(self):
        now = [100.0]
        old = self.ui
        self.ui = FakeDesktop(grants=ScopedFileGrants(clock=lambda: now[0]))
        old._file_grants.revoke_all()
        self._grant()
        root = self.ui._file_fixture.root
        now[0] += 301
        VarynDesktop._inspect_synthetic_folder(self.ui)
        self.assertIsNone(self.ui._file_grant_id)
        self.assertIsNone(self.ui._file_fixture)
        self.assertFalse(root.exists())
        self.assertIn("expired", self.ui.messages[-1][1])

    def test_desktop_close_revokes_and_deletes_disposable_sample(self):
        self._grant()
        old_id = self.ui._file_grant_id
        root = self.ui._file_fixture.root
        self.ui._lifecycle = SimpleNamespace(busy=False, close=lambda: None)
        self.ui._approval = SimpleNamespace(reject_all_pending=lambda: None)
        self.ui._agent_journal = None
        self.ui.controller = SimpleNamespace(discard_pending_history=lambda: None)
        self.ui.destroy = lambda: None
        VarynDesktop._close(self.ui)
        self.assertTrue(self.ui._closing)
        self.assertIsNone(self.ui._file_grant_id)
        self.assertIsNone(self.ui._file_fixture)
        self.assertFalse(root.exists())
        with self.assertRaises(AgentRejected):
            self.ui._file_grants.list_files(old_id)

    def test_desktop_idle_timer_deletes_fixture_without_user_action(self):
        """Proves the real 1s timer releases the exact UI-owned sample."""
        original_ui = self.ui
        original_ui._file_grants.revoke_all()
        manager = ScopedFileGrants(auto_expire=True)
        self.ui = FakeDesktop(grants=manager)
        deleted = threading.Event()
        created = []
        real_fixture = SyntheticFixture
        original_grant = manager.grant

        def make_fixture():
            fixture = real_fixture()
            original_close = fixture.close

            def cleanup_and_signal():
                original_close()
                deleted.set()

            fixture.close = cleanup_and_signal
            created.append(fixture)
            return fixture

        def short_grant(path, **kwargs):
            return original_grant(path, duration_seconds=1, **kwargs)

        with patch("varyn.desktop.SyntheticFixture", side_effect=make_fixture), \
             patch.object(manager, "grant", side_effect=short_grant):
            self._grant()
        self.assertEqual(len(created), 1)
        root = created[0].root
        self.assertTrue(root.is_dir())
        grant_id = self.ui._file_grant_id
        # No UI inspection, revoke, or status poll before the timer fires.
        self.assertTrue(deleted.wait(5), "synthetic fixture still on disk after expiry")
        self.assertFalse(root.exists())
        with self.assertRaises(AgentRejected):
            manager.list_files(grant_id)
        VarynDesktop._inspect_synthetic_folder(self.ui)
        self.assertIsNone(self.ui._file_grant_id)
        self.assertIsNone(self.ui._file_fixture)

    def test_audit_has_no_fixture_names_or_private_bytes(self):
        self._grant()
        VarynDesktop._inspect_synthetic_folder(self.ui)
        report = repr(self.ui._file_grants.status())
        self.assertNotIn(str(self.ui._file_fixture.root), report)
        self.assertNotIn("sample.txt", report)
        self.assertNotIn("notes.md", report)
        self.assertNotIn("VARYN Demo", report)


if __name__ == "__main__":
    unittest.main()
