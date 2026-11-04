# VARYN Checkpoint 17E: In-process idle grant expiry and deadline-safe results

**Date:** 2026-11-04 (Asia/Jakarta)
**Scope:** Synthetic-only temporary read permissions. No model file tool, real account data, or network/API access.
**Product requirement unchanged:** Option C means automatic two-way synchronization of the *official* ChatGPT/Claude/Gemini apps; this checkpoint does not implement or substitute that feature.

## Problem found in 17D

Grant expiry was checked on read/list/status and host operations, but if the desktop stayed idle with an approved folder handle, no deadline-triggered cleanup occurred. An in-progress read could also begin before expiration and return content after its lease deadline.

## 17E implementation

- **Desktop explicitly opts in:** VarynDesktop constructs ScopedFileGrants(auto_expire=True). Existing programmatic, deterministic and fake-clock callers default to auto_expire=False. No system service, scheduled network job, database, subprocess, or permanent watchdog is introduced.
- **At most one pending deadline timer per grant manager:** A cancellable Python threading.Timer is scheduled for the earliest active expiry. It is daemonized, runs only within the desktop Python process, and obtains the manager's existing RLock before releasing a handle. If a second grant arrives or the first is revoked, an old timer is cancelled and replaced. Generation counters prevent already-queued stale callbacks from revoking newer grants.
- **Timers do not access file contents:** On expiry, the callback runs the existing metadata-only sweep, closes pinned folder handles and removes expired grant records. The timer becomes unscheduled when there are no unexhausted active grants. A fully closed desktop has no retained active grant or timer.
- **Expiry during a read/list:** Each operation is serialized under the same lock. Before releasing the result, the manager checks the monotonic deadline *again*. If the operation crossed its expiry, PermissionError is raised and no bytes or filename listing are returned to the caller. Cleanup runs in a finally block, including unsuccessful operations. This cannot interrupt a kernel read already in flight, and an untrusted process with the same OS privileges is not isolated.
- **Fail-closed and bounded:** Temporary 300-second / 10-operation defaults still apply; permitted extensions remain .txt and .md and file limits unchanged. No additional privileges or file-write operations were granted.

## Evidence and explicit tests

- varyn/file_grants.py: guarded single-timer schedule, generation-based stale-callback rejection, deadline-check after I/O.
- varyn/desktop.py: enables idle expiry for desktop synthetic grants.
- tests/test_file_grant_idle_timer.py: **17 synthetic tests** including fake timer races, stale-callback rejection, single pending timer across several grants, concurrent revoke waiting for an in-flight operation, cancellation/revoke, expiry while idle, quota exhaustion, deadline crossed while reading, independent threads holding a lock, invalid configuration and default-off behavior. One test uses a **real one-second Python timer** with no intervening status/read call and verifies reader close.
- .github/workflows/memory-checks.yml: explicit cross-platform timer regression step in addition to the existing full suite and native-Windows-only checks.

The observed CI results and verified commit are recorded in docs/progress-log.md. A green hosted runner does not establish physical owner-laptop acceptance.

## Scheduler failure is a denial, never a quiet fallback

A resource-exhausted Python process may fail to instantiate or start a threading.Timer. When that happens, ScopedFileGrants now cancels its partial timer, revokes **all** grants owned by the manager, closes all pinned directory handles, and raises PermissionError rather than leaving any supposedly temporary permission without an expiry callback. The metadata-only audit adds timer_unavailable without paths, filenames, or content. Three additional regressions exercise factory failure, thread-start failure, and a failed reschedule with an existing earlier grant.

## Limitations and remaining gates

1. Python daemon timer scheduling is **best effort**, not a hard real-time guarantee. The OS may delay a callback during sleep, heavy CPU use, process suspension or an operation holding the lock. The grant is denied at its deadline during access regardless of callback scheduling; the OS handle may remain open until the callback obtains the lock or the app exits.
2. The timer does not authenticate a human, enforce Windows permissions outside the VARYN process or sandbox model output. The original user-confirmed flag is still a trusted-host assertion. Same-user malicious code may bypass these Python objects.
3. No actual mouse-click path, power-loss or unusual filesystem acceptance has been performed on the owner's Windows laptop. No sensitive file, browser profile, document library, cloud-drive root or API keys should be used.
4. This change does not provide official consumer-app conversation-history read/write APIs. Do not relabel provider model API access or imported exports as Option C synchronization.

## Synthetic local verification

    py -3.12 -m unittest discover -s tests -p "test_file_grant_idle_timer.py" -v
    py -3.12 -m varyn.desktop

In the desktop, grant a disposable synthetic folder, then leave the application idle beyond the default five-minute duration and verify an expired grant cannot be used again. Close and restart the desktop to confirm no grant persists. The current UI does not display a live countdown, and these manual actions are not yet recorded as passed on the owner's PC.

**Verdict:** A narrower lifetime for a Windows/POSIX directory handle, without promoting VARYN to production-safe or enabling provider-file uploads. PR remains draft and main unchanged.
