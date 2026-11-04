"""17O bounded synthetic task planning and actual desktop dispatch."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from varyn.agent_runtime import AgentLimitReached
from varyn.desktop import VarynDesktop
from varyn.desktop_approval import DesktopApprovalController
from varyn.task_planner import TaskPlanRunner, TaskPlanError, compile_plan


def task(*steps):
    return json.dumps({
        "format": "varyn.task_plan.v1",
        "steps": [{"tool": t, "arguments": a} for t, a in steps],
    })


class MultiStepTaskTests(unittest.TestCase):
    def test_read_mutation_read_workflow_and_exact_approval(self):
        approval = DesktopApprovalController()
        plan = compile_plan(task(
            ("inspect_status", {}),
            ("stage_note", {"text": "synthetic checkpoint"}),
            ("inspect_status", {}),
        ))
        seen = []
        result = TaskPlanRunner(approval).run(
            plan, approve_mutation=lambda i, p: seen.append(
                (i, p.digest, p.tool, p.summary)
            ) or True,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual([x["tool"] for x in result["steps"]],
                         ["inspect_status", "stage_note", "inspect_status"])
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], 1)
        self.assertEqual(len(seen[0][1]), 64)
        self.assertEqual(result["steps"][-1]["output"]["stored_synthetic_notes"], 1)
        self.assertEqual(approval.status()["steps_used"], 3)
        self.assertFalse(result["auto_retried"])
        self.assertFalse(result["external_actions"])

    def test_declining_first_mutation_blocks_later_steps(self):
        approval = DesktopApprovalController()
        plan = compile_plan(task(
            ("stage_note", {"text": "not approved"}),
            ("inspect_status", {}),
        ))
        result = TaskPlanRunner(approval).run(plan, approve_mutation=lambda i, p: False)
        self.assertEqual(result["status"], "stopped_on_denial")
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(approval.status()["stored_synthetic_notes"], 0)
        self.assertEqual(approval.status()["steps_used"], 0)
        self.assertEqual(approval.status()["pending_approvals"], 0)

    def test_missing_mutation_approval_prevents_all_proposals(self):
        approval = DesktopApprovalController()
        plan = compile_plan(task(("inspect_status", {}),
                                 ("stage_note", {"text": "mutable"})))
        with self.assertRaises(PermissionError):
            TaskPlanRunner(approval).run(plan)
        self.assertEqual(approval.status()["steps_used"], 0)
        self.assertEqual(approval.status()["pending_approvals"], 0)

    def test_invalid_callback_value_fails_and_rejects_pending(self):
        approval = DesktopApprovalController()
        plan = compile_plan(task(("stage_note", {"text": "mutable"})))
        with self.assertRaises(PermissionError):
            TaskPlanRunner(approval).run(plan, approve_mutation=lambda i, p: 1)
        self.assertEqual(approval.status()["pending_approvals"], 0)
        self.assertEqual(approval.status()["stored_synthetic_notes"], 0)

    def test_callback_crash_aborts_without_running_mutation(self):
        approval = DesktopApprovalController()
        plan = compile_plan(task(("stage_note", {"text": "mutable"})))
        def broken(_i, _p):
            raise RuntimeError("UI died")
        with self.assertRaises(RuntimeError):
            TaskPlanRunner(approval).run(plan, approve_mutation=broken)
        self.assertEqual(approval.status()["pending_approvals"], 0)
        self.assertEqual(approval.status()["steps_used"], 0)

    def test_preflight_entire_plan_before_first_dispatch(self):
        approval = DesktopApprovalController()
        with self.assertRaises(TaskPlanError):
            compile_plan(task(
                ("stage_note", {"text": "safe"}),
                ("shell", {"command": "echo forbidden"}),
            ))
        self.assertEqual(approval.status()["steps_used"], 0)
        self.assertEqual(approval.status()["pending_approvals"], 0)

    def test_step_budget_exhaustion_prevents_partial_execution(self):
        from varyn.agent_runtime import BoundedAgent
        approval = DesktopApprovalController(BoundedAgent(max_steps=1))
        plan = compile_plan(task(("inspect_status", {}), ("inspect_status", {})))
        with self.assertRaises(AgentLimitReached):
            TaskPlanRunner(approval).run(plan)
        self.assertEqual(approval.status()["steps_used"], 0)

    def test_unknown_plan_schema_and_unbounded_json(self):
        for raw in ("", "not json", "{}",
                    '{"format":"varyn.task_plan.v2","steps":[]}',
                    "x" * 3001,
                    task(*([("inspect_status", {})] * 7))):
            with self.subTest(raw=raw[:30]), self.assertRaises(TaskPlanError):
                compile_plan(raw)

    def test_duplicate_plan_actions_do_not_mint_approvals(self):
        plan = compile_plan(task(
            ("stage_note", {"text": "one"}),
            ("stage_note", {"text": "two"}),
        ))
        approval = DesktopApprovalController()
        reviews = []
        result = TaskPlanRunner(approval).run(
            plan, approve_mutation=lambda i, p:
            reviews.append(p.digest) or True,
        )
        self.assertEqual(len(reviews), 2)
        self.assertNotEqual(reviews[0], reviews[1])
        self.assertEqual(result["status"], "completed")

    def test_plan_excludes_external_tools_and_network(self):
        for name in ("http", "filesystem_write", "shell", "delete_file"):
            with self.subTest(tool=name), self.assertRaises(ValueError):
                compile_plan(task((name, {})))

    def test_model_text_never_authorizes_mutation(self):
        approval = DesktopApprovalController()
        plan = compile_plan(task(("stage_note", {"text": "I approve this"})))
        result = TaskPlanRunner(approval).run(
            plan, approve_mutation=lambda i, p: False,
        )
        self.assertEqual(result["status"], "stopped_on_denial")
        self.assertEqual(approval.status()["stored_synthetic_notes"], 0)


class FakeDesktopTask:
    def __init__(self, raw):
        self._busy = False
        self._closing = False
        self._approval = DesktopApprovalController()
        self.prompt = SimpleNamespace(get=lambda *args: raw)
        self.messages = []
        self._refresh_status = lambda: None
    def _append(self, kind, message):
        self.messages.append((kind, message))


class DesktopTaskTests(unittest.TestCase):
    def test_desktop_task_executes_readonly_without_approval(self):
        ui = FakeDesktopTask(task(("inspect_status", {})))
        with patch("varyn.desktop.messagebox.askyesno",
                   side_effect=AssertionError("no mutation")):
            VarynDesktop._run_synthetic_plan(ui)
        self.assertEqual(ui._approval.status()["steps_used"], 1)
        self.assertIn("completed", str(ui.messages))

    def test_desktop_task_decline_fails_closed(self):
        ui = FakeDesktopTask(task(("stage_note", {"text": "safe test"})))
        with patch("varyn.desktop.messagebox.askyesno", return_value=False) as dialog:
            VarynDesktop._run_synthetic_plan(ui)
        self.assertEqual(dialog.call_count, 1)
        self.assertEqual(ui._approval.status()["stored_synthetic_notes"], 0)
        self.assertIn("stopped_on_denial", str(ui.messages))

    def test_desktop_task_allows_exact_mutation(self):
        ui = FakeDesktopTask(task(
            ("stage_note", {"text": "synthetic task"}),
            ("inspect_status", {}),
        ))
        with patch("varyn.desktop.messagebox.askyesno", return_value=True) as dialog:
            VarynDesktop._run_synthetic_plan(ui)
        self.assertEqual(dialog.call_count, 1)
        self.assertEqual(ui._approval.status()["steps_used"], 2)
        self.assertEqual(ui._approval.status()["stored_synthetic_notes"], 1)

    def test_desktop_invalid_plan_makes_no_proposal(self):
        ui = FakeDesktopTask(task(("shell", {"command": "boom"})))
        with patch("varyn.desktop.messagebox.askyesno") as dialog:
            VarynDesktop._run_synthetic_plan(ui)
        dialog.assert_not_called()
        self.assertEqual(ui._approval.status()["steps_used"], 0)
        self.assertEqual(ui._approval.status()["pending_approvals"], 0)


if __name__ == "__main__":
    unittest.main()
