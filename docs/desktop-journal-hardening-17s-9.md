# VARYN 17S-9 | Desktop callback teardown and SQLite fault gates

Date: 2026-11-05. Follows the CI-verified 17S-8 journal. All external GitHub fetches in this checkpoint's tests remain **mocked**; no consumer-app history integration, autonomous model planning, or new tool privileges are created.

## 1. Real Tk callback teardown

The hosted Windows 17S-8 suite had a nonfatal `invalid command name "..._poll_public_github_tool"` in its Tk test teardown. The root cause in code was an untracked `Tk.after(75, ...)` GitHub worker-poll callback surviving `destroy()`. The two-step comparison's deferred step callback was also untracked.

`varyn/desktop.py` now tracks exactly one pending public worker poll and one deferred comparison-next-step callback, cancels them with `after_cancel` before window teardown, checks the exact comparison object before resuming a deferred step, and sets `_closing=True` **before** canceling scheduled callbacks and destroying widgets. All three previous public-poll scheduling sites use the same tracked helper. `_abort_public_comparison` clears pending callbacks upon cancellation or revocation of an active plan. A callback that was already called checks current closing state.

`tests/test_public_repo_plan_tk.py` adds Windows-only **real Tk** assertions that callback identifiers exist before teardown, disappear after cancellation, and are canceled during `_close`. `tests/test_public_repo_plan.py` continues to exercise the no-resurrection behavior of the deferred second step.

## 2. Real SQLite transition failures, fail closed

`tests/test_public_repo_plan.py` injects actual SQLite `BEFORE UPDATE` triggers using `RAISE(ABORT)` in the opt-in `PublicComparisonJournal`, at three specific transitions:
- **Before the first GET:** `ready -> uncertain` fails; zero network dispatches, no retained authorization.
- **After first GET:** `uncertain -> ready` fails; second GET never sent, journal retains `needs_reconciliation`.
- **After the second validated GET:** `ready -> completed` fails; local result summary suppressed and an incomplete journal state retained for inspection. No automatic redo.

`tests/test_public_comparison_journal.py` also checks that opening an existing file with invalid SQLite contents fails with a database error and does not silently recreate/reset that file.

These are deterministic negative regressions against a local SQLite test fixture, not a simulation of power loss, filesystem exhaustion on the owner's machine, or guarantees about every form of disk corruption.

**Windows discovery and fix:** The first hosted Windows run including the corrupt-file test failed during test teardown with WinError 32, because an exception in `PublicComparisonJournal.__init__` left its SQLite connection open. This was a genuine Windows file-handle leak despite corruption detection. `__init__` now closes the connection and marks it closed on setup failure before re-raising. Earlier red CI remains part of the audit trail and must not be relabeled green. Existing 17S-8 recovery still classifies interrupted `ready` or `uncertain` records without any automatic replay.

## 3. Strict boundaries / acceptance

- Hosted Windows and Ubuntu full CI on **exact final branch HEAD** required; do not claim this complete until both succeed.
- Windows native Tk regression must actually execute, not skip.
- Check Windows logs for recurrence of the Tcl `invalid command name` warning; CI green alone cannot prove this is gone.
- Manual acceptance on the owner's Windows PC, unmocked live GitHub GETs, true Windows private-file read restriction, and Option C two-way sync of official consumer ChatGPT / Claude / Gemini conversations remain unverified or blocked. Existing Low MIC is not read isolation.
- PR #1 remains draft, branch `feat/local-memory-prototype-20261103`; do not touch `main`.

## Next

Complete owner-PC acceptance of the read-only public tool, audit journal permission/retention/tamper response, and prioritize Windows read-restricted child identity or ACL broker before any private data or mutating tool access is enabled.
