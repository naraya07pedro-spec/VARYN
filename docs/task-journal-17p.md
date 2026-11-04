# Checkpoint 17P: durable metadata-only task checkpoints

**Date:** 2026-11-04. Development branch `feat/local-memory-prototype-20261103`, draft PR #1, not merged into main.

## Implemented

A new opt-in `varyn/task_journal.py` records only a random task ID, SHA-256 plan digest, bounded step count, cursor and lifecycle status in an on-disk SQLite database. It **does not store task JSON, tool arguments, model responses, note text, API credentials or approval tokens**. It never reconstructs an executable task.

The existing 17O `TaskPlanRunner` can accept a `TaskJournal`. It persists a plan before execution, writes an uncertain checkpoint **before each tool proposal**, marks completed steps only after they return, and records terminal completion, denial or uncertain failure. A state/digest/cursor mismatch refuses replay.

VARYN Desktop accepts explicit `--task-journal PATH` to opt in. On launch, the journal converts previously unfinished `planned` and `ready` tasks to `needs_review`; previously `uncertain` tasks become `needs_reconciliation`. The user must manually inspect/replan. **No task, tool call, API request or synthetic mutation is automatically resumed or replayed after restart.** Local synthetic agent RAM state is not restored by the journal.

### Synthetic-only test invocation

```powershell
py -3 -m varyn.desktop --task-journal ".\\varyn-task-checkpoints.sqlite3"
```

Paste this into the existing Message field:

```json
{"format":"varyn.task_plan.v1","steps":[{"tool":"inspect_status","arguments":{}},{"tool":"stage_note","arguments":{"text":"synthetic checkpoint"}},{"tool":"inspect_status","arguments":{}}]}
```

Click **Run reviewed synthetic task plan (JSON)**. Review the exact `stage_note` digest and approve only that one synthetic mutation. Task checkpoint metadata is recorded in the explicitly selected local SQLite file. Don't place the SQLite file in a shared/private data directory; no encryption or OS-identity authentication exists.

## Explicit limitations

This is **crash-state detection**, **not automatic task resumption**, and it does not restore synthetic RAM notes after restarting the process. All task plans remain manually authored. No browser, local private files, external apps, real money transfers, shell commands or provider API effects are authorized by this feature. The SQLite task journal is metadata-only but not encrypted. It does not solve selected consumer official-app ChatGPT, Claude and Gemini Option C bidirectional history sync.

## Testing

`tests/test_task_journal.py` includes coverage of persistent completion, no plaintext arguments in SQLite, crashed in-flight steps, review-required restarts, denial, callback failure, duplicate-step rejection, digest binding, invalid paths and safe close. CI has a dedicated test step on Windows and Ubuntu. **CI must be verified at the exact final commit before this milestone is marked validated.**

The earlier checkpoints 17N and 17O still require post-fix hosted Windows/Ubuntu CI verification. The GitHub connector's commit-workflow-run listing can omit push-triggered runs; no success should be invented from its empty output. A push trigger was added specifically for the feature branch to improve Action execution reliability, but it has not yet supplied independently observed latest-commit success.

**Next value target:** true owner-reviewed recovery of durable plans *without* replaying ambiguous external side effects; verified provider permissions and source/provenance tracking; measurable end-to-end task completion, not just test-count inflation.
