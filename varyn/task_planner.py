"""17O: deterministic multi-step synthetic task planner and execution gate.

NOT autonomous language-model planning. Only a trusted caller may submit
an explicit fixed JSON task plan. No shell, files, network or provider calls.
Each mutation requires an independent UI-owned approval callback.
"""
from dataclasses import dataclass
import json

from varyn.agent_runtime import AgentRejected, AgentLimitReached
from varyn.desktop_approval import DesktopApprovalController

_MAX_TASK_STEPS = 6


@dataclass(frozen=True)
class TaskStep:
    tool: str
    arguments: dict


class TaskPlanError(ValueError):
    pass


def compile_plan(raw):
    """Entire plan is validated before any proposal or dispatch."""
    if type(raw) is not str or not 1 <= len(raw) <= 3000:
        raise TaskPlanError("Plan JSON must be 1..3000 characters")
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        raise TaskPlanError("Invalid task JSON") from None
    if type(doc) is not dict or set(doc) != {"format", "steps"}:
        raise TaskPlanError("Unrecognized task plan schema")
    if doc["format"] != "varyn.task_plan.v1":
        raise TaskPlanError("Unsupported task plan format")
    steps = doc["steps"]
    if type(steps) is not list or not 1 <= len(steps) <= _MAX_TASK_STEPS:
        raise TaskPlanError("Task plan must contain 1..6 steps")
    plan = []
    for item in steps:
        if type(item) is not dict or set(item) != {"tool", "arguments"}:
            raise TaskPlanError("Invalid task step")
        tool, args = item["tool"], item["arguments"]
        if type(tool) is not str or type(args) is not dict:
            raise TaskPlanError("Invalid task tool or arguments")
        # Reuse existing exact allowlist and argument limits. No new tools.
        from varyn.agent_runtime import BoundedAgent
        BoundedAgent._validate(tool, args)
        plan.append(TaskStep(tool, dict(args)))
    return tuple(plan)


class TaskPlanRunner:
    """Sequential fixed-plan execution; fail closed, no automatic retry.

    Approval callback receives the same immutable digest-bound preview used by
    existing VARYN DesktopApprovalController. It must run only on trusted UI
    thread, never in provider text, model output or a background process.
    """

    def __init__(self, approvals):
        if not isinstance(approvals, DesktopApprovalController):
            raise TypeError("VARYN DesktopApprovalController required")
        self.approvals = approvals

    def run(self, plan, *, approve_mutation=None):
        if type(plan) is not tuple or not 1 <= len(plan) <= _MAX_TASK_STEPS:
            raise TaskPlanError("Compile task plan before running")
        # Preflight all steps and capacity ahead of the first proposal.
        from varyn.agent_runtime import BoundedAgent
        for step in plan:
            if type(step) is not TaskStep:
                raise TaskPlanError("Invalid step structure")
            BoundedAgent._validate(step.tool, step.arguments)
        status = self.approvals.status()
        if status["steps_used"] + status["pending_approvals"] + len(plan) > status["steps_limit"]:
            raise AgentLimitReached("Not enough remaining agent steps for task")
        if any(step.tool == "stage_note" for step in plan) and not callable(approve_mutation):
            raise PermissionError("Each mutating step requires GUI approval")
        outcomes = []
        for index, step in enumerate(plan):
            preview = None
            try:
                preview = self.approvals.propose(step.tool, dict(step.arguments))
                approved = True
                if preview.mutates:
                    approved = approve_mutation(index, preview)
                    if type(approved) is not bool:
                        raise PermissionError("Invalid human decision")
                if not approved:
                    self.approvals.decide(
                        preview.proposal_id, preview.digest, approved=False,
                    )
                    outcomes.append({"index": index, "tool": preview.tool, "status": "rejected"})
                    return {
                        "format": "varyn.task_run.v1",
                        "status": "stopped_on_denial",
                        "steps": outcomes, "next_step": None,
                        "auto_retried": False,
                        "external_actions": False,
                    }
                result = self.approvals.decide(
                    preview.proposal_id, preview.digest, approved=True,
                )
            except BaseException:
                # Pending UI proposals must not be left to be approved later.
                self.approvals.reject_all_pending()
                raise
            outcomes.append({
                "index": index,
                "tool": result["tool"],
                "status": result["status"],
                "output": dict(result["output"]),
            })
        return {
            "format": "varyn.task_run.v1",
            "status": "completed",
            "steps": outcomes,
            "next_step": None,
            "auto_retried": False,
            "external_actions": False,
        }
