# VARYN 17S-8 | Opt-in durable public comparison checkpoint journal

Date: 2026-11-04. This is a **metadata-only, opt-in** recovery audit for the existing manually reviewed 17S-7 public GitHub two-repository workflow. It is NOT autonomous network execution, a sandbox, private memory, or Option C official consumer-app synchronization.

## What changes in the owner's actual desktop

When starting VARYN, the owner may explicitly configure a separate SQLite checkpoint path:

```powershell
python -m varyn.desktop --comparison-journal "D:\\VARYN\\public-comparison-checkpoints.sqlite3"
```

The parent directory must already exist. No path means **no public-comparison journal**, preserving the previous RAM-only behavior. No private file or API credential access is enabled. This is metadata-only SQLite, NOT encrypted storage; avoid choosing a shared directory.

With this switch, the desktop records a random task ID, a SHA-256 digest derived from the random plan review nonce and the two targets, the numeric cursor (0..2), and a finite status. **It never persists repository targets, prompts, results, secret data, approval objects, raw tool requests, or external credentials.** The hash is an audit identifier, not a bearer grant.

## Crash-safe rules

1. The owner approves the whole plan separately from every individual network GET. The journal row is created after the whole-plan review, before any step review.
2. **Before** a reviewed GET can be submitted to the worker, the journal must atomically move from `ready` to `uncertain`. If this durable write fails, there is NO dispatch.
3. After the gateway has returned and the host validates the exact metadata result against the current approved step, the journal advances the cursor and becomes `ready` again. A missing or conflicting row prevents moving to the next step.
4. On completed step 2, the journal records `completed` before the final local summary is displayed. No outbound result/model handoff is added.
5. Explicit cancel while `ready` becomes `cancelled`; cancel after dispatch has possibly begun becomes `needs_reconciliation`.
6. On restart, `ready` becomes `needs_review` and `uncertain` becomes `needs_reconciliation`. **No task, consent, or network request is restored or replayed.** The desktop displays counts only.
7. The journal is closed during normal desktop exit and on the CLI's display-initialization failure path.

This prevents silent duplicate external read requests after a crash and makes uncertainty visible. It does NOT prove the external GET failed or succeeded after a connection drop. Even read-only GETs may consume API quota. Reconciliation remains manual.

## Evidence / limits

- `varyn/public_comparison_journal.py` is the narrowly scoped SQLite state machine.
- `tests/test_public_comparison_journal.py` covers interrupted pre-dispatch/dispatch/between-steps states, ordered transitions, replay rejection, aborted ambiguity, missing authorization, and metadata minimization.
- `tests/test_public_repo_plan.py` exercises integration with a mocked network worker: exactly three owner dialogs, two separate public GETs, completed journal and no saved authorization; separate test revokes during an in-flight request and requires `needs_reconciliation`.
- CI requires Windows and Ubuntu tests on exact final HEAD. Windows Tk smoke remains mocked; owner PC, real-network latency, storage failure-injection and private-read-denial OS acceptance are still pending.
- Enabling the journal is entirely optional. Existing `--task-journal` is a DIFFERENT experimental synthetic task journal and is not silently reused.
- 17S-6 Low MIC does not prevent reads of same-user files. Public network child must not receive personal information. Option C consumer ChatGPT/Claude/Gemini history two-way sync remains unresolved.

## Next

Owner-PC end-to-end acceptance of the manually reviewed public workflow; bounded journal retention / corruption recovery audit; genuine Windows read-restricted process or ACL broker before ever permitting private data, and secure real-task execution with explicit bounded permissions. Do not merge PR #1.
