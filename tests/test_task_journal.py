"""17P durable task journal: completed, denied, and ambiguous crash states."""
import tempfile
import unittest
from pathlib import Path

from varyn.desktop_approval import DesktopApprovalController
from varyn.task_planner import TaskPlanRunner, compile_plan
from varyn.task_journal import TaskJournal, JournalConflict, digest_plan


def plan(*steps):
    import json
    return compile_plan(json.dumps({
        "format": "varyn.task_plan.v1",
        "steps": [{"tool": name, "arguments": args} for name, args in steps],
    }))


class TaskJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "task.sqlite3"

    def test_completed_plan_is_durable_and_stores_no_arguments(self):
        selected = plan(
            ("inspect_status", {}),
            ("stage_note", {"text": "synthetic private content marker"}),
            ("inspect_status", {}),
        )
        journal = TaskJournal(self.path)
        outcome = TaskPlanRunner(DesktopApprovalController(), journal=journal).run(
            selected, approve_mutation=lambda index, proposal: True,
        )
        self.assertEqual(outcome["status"], "completed")
        tid = outcome["task_journal_id"]
        self.assertEqual(journal.inspect(tid)["cursor"], 3)
        journal.close()
        persisted = self.path.read_bytes()
        self.assertNotIn(b"synthetic private content marker", persisted)
        reopened = TaskJournal(self.path)
        self.assertEqual(reopened.inspect(tid)["status"], "completed")
        self.assertEqual(reopened.recover()["auto_replayed"], 0)
        self.assertEqual(reopened.inspect(tid)["status"], "completed")
        reopened.close()

    def test_restart_after_prepared_step_requires_manual_reconciliation(self):
        work = plan(("stage_note", {"text": "synthetic test"}))
        journal = TaskJournal(self.path)
        tid, digest = journal.create(work)
        journal.begin(tid, digest, 0)
        journal.close()
        restart = TaskJournal(self.path)
        self.assertEqual(restart.recover()["needs_reconciliation"], 1)
        self.assertEqual(restart.inspect(tid)["status"], "needs_reconciliation")
        with self.assertRaises(JournalConflict):
            restart.begin(tid, digest, 0)
        self.assertFalse(restart.inspect(tid)["executable"])
        restart.close()

    def test_restart_after_checkpoint_before_next_step_requires_review(self):
        work = plan(("inspect_status", {}), ("inspect_status", {}))
        journal = TaskJournal(self.path)
        tid, digest = journal.create(work)
        journal.begin(tid, digest, 0)
        journal.complete(tid, digest, 0)
        journal.close()
        restart = TaskJournal(self.path)
        result = restart.recover()
        self.assertEqual(result["needs_review"], 1)
        self.assertEqual(restart.inspect(tid)["cursor"], 1)
        self.assertEqual(restart.inspect(tid)["status"], "needs_review")
        with self.assertRaises(JournalConflict):
            restart.begin(tid, digest, 1)
        restart.close()

    def test_denied_mutation_stops_and_persists(self):
        selected = plan(("stage_note", {"text": "not permitted"}),
                        ("inspect_status", {}))
        journal = TaskJournal(self.path)
        controller = DesktopApprovalController()
        output = TaskPlanRunner(controller, journal=journal).run(
            selected, approve_mutation=lambda index, preview: False,
        )
        self.assertEqual(output["status"], "stopped_on_denial")
        self.assertEqual(controller.status()["steps_used"], 0)
        self.assertEqual(journal.inspect(output["task_journal_id"])["status"],
                         "denied")
        journal.close()

    def test_approval_callback_crash_is_failed_uncertain_without_replay(self):
        selected = plan(("stage_note", {"text": "synthetic"}))
        journal = TaskJournal(self.path)
        controller = DesktopApprovalController()
        with self.assertRaises(RuntimeError):
            TaskPlanRunner(controller, journal=journal).run(
                selected,
                approve_mutation=lambda *_: (_ for _ in ()).throw(
                    RuntimeError("synthetic UI crash")
                ),
            )
        self.assertEqual(controller.status()["pending_approvals"], 0)
        status = journal.db.execute(
            "SELECT status FROM task_checkpoints"
        ).fetchone()[0]
        self.assertEqual(status, "failed_uncertain")
        journal.close()

    def test_same_step_cannot_be_dispatched_twice(self):
        selected = plan(("inspect_status", {}))
        journal = TaskJournal(self.path)
        tid, d = journal.create(selected)
        journal.begin(tid, d, 0)
        with self.assertRaises(JournalConflict):
            journal.begin(tid, d, 0)
        journal.complete(tid, d, 0)
        journal.finish(tid, d, 1)
        with self.assertRaises(JournalConflict):
            journal.begin(tid, d, 0)
        journal.close()

    def test_digest_binds_order_and_arguments(self):
        a = plan(("stage_note", {"text": "one"}),
                 ("inspect_status", {}))
        b = plan(("inspect_status", {}),
                 ("stage_note", {"text": "one"}))
        c = plan(("stage_note", {"text": "two"}),
                 ("inspect_status", {}))
        self.assertNotEqual(digest_plan(a), digest_plan(b))
        self.assertNotEqual(digest_plan(a), digest_plan(c))
        self.assertEqual(digest_plan(a), digest_plan(a))

    def test_refuse_bad_disk_path(self):
        with self.assertRaises(ValueError):
            TaskJournal(":memory:")
        with self.assertRaises(ValueError):
            TaskJournal(Path(self.temp.name) / "absent" / "file.sqlite3")

    def test_closing_database_rejects_future_updates(self):
        journal = TaskJournal(self.path)
        journal.close()
        with self.assertRaises(JournalConflict):
            journal.create(plan(("inspect_status", {})))

    def test_incomplete_plan_never_auto_executes_on_restart(self):
        journal = TaskJournal(self.path)
        tid, d = journal.create(plan(("inspect_status", {})))
        journal.close()
        other = TaskJournal(self.path)
        self.assertEqual(other.recover()["needs_review"], 1)
        self.assertEqual(other.inspect(tid)["cursor"], 0)
        self.assertEqual(other.recover()["needs_review"], 0)
        other.close()


if __name__ == "__main__":
    unittest.main()
