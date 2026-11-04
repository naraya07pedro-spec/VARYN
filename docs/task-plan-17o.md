# Checkpoint 17O: fixed-plan bounded task execution

Date: 2026-11-04. Development remains on feat/local-memory-prototype-20261103, draft PR #1, main unchanged.

## Delivered

The new `varyn/task_planner.py` provides a deterministic, fully prevalidated 1–6 step task plan and a sequential task runner using the existing VARYN BoundedAgent and DesktopApprovalController. The desktop now offers **Run reviewed synthetic task plan (JSON)**. A trusted user types explicit task JSON and invokes the button. Model-generated tasks do not bypass human review; there is no autonomous LLM plan generation in this checkpoint.

Only two registered synthetic, in-memory tools are allowed:
- `inspect_status`: read-only synthetic agent counters.
- `stage_note`: store a temporary synthetic note in agent RAM, **requiring an explicit separate GUI approval for each mutation**. The preview includes exact tool, note effect, risk, digest and stage number.

Plan compilation rejects unknown tools, unexpected fields, invalid/oversized JSON, too many steps and malformed arguments before the first proposal is staged. Runner checks remaining action budget before starting. A refusal stops all later actions without replay. Failed or ambiguous execution terminates the current plan; completed earlier steps are not rolled back. The existing optional agent metadata journal can record proposals and uncertain dispatches without storing note text or approval tokens, but **task plans themselves are not durably persisted or resumable**.

## Safe example to paste into the Message box

```json
{
  "format": "varyn.task_plan.v1",
  "steps": [
    {"tool": "inspect_status", "arguments": {}},
    {"tool": "stage_note", "arguments": {"text": "synthetic workflow checkpoint"}},
    {"tool": "inspect_status", "arguments": {}}
  ]
}
```

Click **Run reviewed synthetic task plan (JSON)** and approve the *one* mutating step after inspecting the exact digest. The transcript shows completed step summaries; the synthetic agent's stored note count increases. No external side effects, file access or network calls occur.

## Verification and honesty

- `tests/test_task_planner.py`: 15 unit/integration regressions for actual multi-step execution and desktop callbacks, denial, step budget, malformed plans, absent approval, unexpected callback values, rejection of shell/network/filesystem tools, and no model-generated automatic consent.
- `tests/test_task_planner_tk.py`: one hosted Windows real Tk synthetic button/callback smoke with mutation approval. This invokes genuine Tk widget callbacks programmatically, **not physical human clicks**.
- Both tests are mandated by `.github/workflows/memory-checks.yml`, together with the previous 17N selected-memory tests and whole existing Windows/Ubuntu suite.
- The prior 17N checkpoint has an initial failed CI build (#41809287501) from a malformed Python conditional approval string, since fixed. **Do not claim 17N or 17O CI success until the final commit's actual Windows and Ubuntu jobs run and pass**.

## Known limits

The current task plan is manually specified and deterministic, **not** full autonomous AI planning, multi-provider tool calling, web research, production integrations or persistent end-to-end recovery. Agent approvals are UI convention and digest binding, not independently authenticated owner identity or OS isolation. Only synthetic RAM notes are changed. Option C automatic official ChatGPT/Claude/Gemini consumer-app conversation sync remains blocked and was not substituted with developer APIs.

Next milestone: durable user-reviewed task plans, crash-safe reconciliation, resumed execution only after explicit fresh human approval and safe integration with selected project memory and agent routing.
