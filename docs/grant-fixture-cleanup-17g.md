# VARYN Checkpoint 17G: Grant-owned synthetic fixture lifecycle

**Date:** 2026-11-04 (Asia/Jakarta)
**Scope:** Disposal of VARYN-generated, non-sensitive demo files. No user-selected folders, provider synchronization, model file access, or persistent data.

## What was wrong with 17F

The 17E idle timer already revoked an expired folder grant and closed the pinned Windows/POSIX directory handle. But the 17F desktop retained ownership of its TemporaryDirectory separately, so the harmless sample.txt and notes.md files could remain in the OS temp folder until the next GUI action or a normal process exit. There was also a cleanup race between a timer callback and a desktop revoke/close.

## 17G implementation

- ScopedFileGrants.grant(..., on_release=...) accepts an **optional trusted-host-only callback**. The normal library default is unchanged (None). This callback is **not** accepted from an AI prompt, tool schema, provider response or untrusted JSON.
- The manager releases each entry **once**, always closing the pinned directory reader **before** invoking its callback. The callback is invoked on timer expiry, status-triggered expiry, explicit revoke, revoke_all, final quota use (success or failure), an operation crossing the time deadline, or scheduler creation/start/reschedule failure.
- All release paths share a single guarded routine. A released flag and a consumed callback enforce at-most-once invocation across races. The same grant manager RLock serializes active reads, quota decrements, timer callbacks, and revokes. A callback exception is recorded as a generic metadata-only cleanup_failed audit event; it does not restore access, leak a path or allow reading again.
- The desktop passes on_release=fixture.close only for the freshly generated two-file demo directory. The user cannot supply a filesystem path in this UI. Cleanup runs in the grant manager itself, so **no Tk operations are performed from the background timer thread**.
- SyntheticFixture.close() serializes concurrent attempts using a per-instance threading.Lock. Its TemporaryDirectory reference is cleared **after** cleanup succeeds, so an OS deletion error (e.g., transient Windows file lock) leaves the owner able to retry normal cleanup. Desktop revoke/close and the release hook may therefore safely call the same method more than once.
- Only fixture-owner code removes its own generated files; grant teardown never deletes a user-selected directory.

## Test coverage

- tests/test_grant_fixture_release.py: **12 tests** for expiry sweep, explicit revoke, revoke_all, successful and failed final quota operations, expiration during read with withheld result, exception handling, validation of hook type, scheduler failure, metadata-only audit, real one-second idle timer deletion with **no intervening UI/status/read**, and timer/revoke race.
- tests/test_desktop_file_scope.py: desktop-level real timer integration, confirming its VARYN-generated temporary directory disappears without pressing Inspect/Revoke.
- tests/test_synthetic_fixture.py: concurrent cleanup from multiple threads and retry after simulated OS file lock; fixed sample and neighbor-file noninterference tests remain.
- .github/workflows/memory-checks.yml: explicit grant-owned fixture regression step on **Windows and Ubuntu** in addition to full suites, desktop fixture checks, 17E timer checks and Windows-native handle regressions.

See docs/progress-log.md for exact commit SHA, CI jobs and discovered-test totals. Test fixture data is synthetic and requires no provider credentials or paid API use.

## Residual risks, stated precisely

1. **Best effort, not hard real-time:** Python's in-process timer may be delayed during sleep, process suspension or an operation holding the manager lock. Release runs when the scheduler can run; there is no real-time deadline guarantee.
2. **Crash residue:** abrupt process death or machine power loss can leave harmless sample files on disk. Normal finalization and in-process expiry cannot run after a hard crash. This checkpoint does not implement a persistent crash-recovery service.
3. **Deletion errors:** Windows may prevent removing a sample due to another process holding it open. The already-expired grant remains denied; a generic audit event records failure and a still-live desktop fixture object may retry cleanup on normal shutdown. No guarantee of complete deletion under adversarial filesystem conditions.
4. **No identity/authentication sandbox:** same-user arbitrary Python code can bypass the trusted object and read ordinary filesystem data. No OS process isolation, Windows identity-authenticated consent or comprehensive malware threat model is implemented.
5. **No owner-hardware UI acceptance:** GitHub Windows runners validate code and native APIs, not actual mouse interaction, antivirus behavior, sleep/wake timing or local hardware. Use only VARYN-generated sample files.
6. **Option C unchanged:** desired automatic two-way synchronization with the **official ChatGPT, Claude and Gemini consumer apps** remains independently blocked pending verified official read/write provider interfaces. Neither provider API calls, VARYN-only chats nor exports are a substitute.

## Synthetic verification commands

    python -m unittest discover -s tests -p "test_grant_fixture_release.py" -v
    python -m unittest discover -s tests -p "test_desktop_file_scope.py" -v
    python -m unittest discover -s tests -p "test_synthetic_fixture.py" -v

**Checkpoint conclusion:** demo file cleanup is now owned by the grant lease rather than manual UI interaction. This is prototype hardening, not authorization to use real sensitive folders. PR #1 stays draft; main untouched.
