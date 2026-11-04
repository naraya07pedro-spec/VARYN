# VARYN 17S-5 | Native Windows Job Object gate and SID consistency

Date: 2026-11-04. Engineering checkpoint, not product acceptance. Original Option C requirement remains unchanged.

## Problem

17S-4 moved the public, read-only GitHub metadata fetch into a same-user subprocess with minimal environment but did not enforce Windows kernel job limits or verify the spawned process's actual security token. One child could exceed resource budget; there was no Job Object process-tree guarantee.

## Implementation

- Added `varyn/windows_child_job.py` with native Windows API calls using Python `ctypes`: `CreateJobObjectW`, `SetInformationJobObject`, `QueryInformationJobObject`, `AssignProcessToJobObject`, `IsProcessInJob`, `OpenProcessToken`, `GetTokenInformation(TokenUser)` and `GetLengthSid`. Native API return values and read-back values must all pass, or the child is denied.
- On Windows, **before any repository intent is sent over the child's stdin**, `ProcessRepoFetcher` requires `WindowsChildJob(proc)` with the same OS-issued user SID as the parent, a configured and read-back **192 MiB process commit limit**, **one active process per job**, and **KILL_ON_JOB_CLOSE**. The job disallows breakaway flags and its last handle is closed during shutdown or cancellation. If setup or verification fails, VARYN kills the child, sends no tool input and refuses that request. The sender budget still counts the attempt.
- The child uses a fixed executable/script, `-I -S`, no shell, an allowlisted environment that does not copy provider/GitHub credentials, and bounded input/output. The parent still validates the response and suppresses stale results after consent revocation.
- New `tests/test_windows_child_job.py` exercises a real native Windows job with a subprocess blocked on stdin, verifies job membership, SID check and limit read-back in native code, asserts closing the job kills its process, and checks a real offline end-to-end ProcessRepoFetcher handshake. Fault-injection tests verify a missing/failed guard stops execution before `communicate(input=...)`. The normal network call remains mocked throughout CI.
- Existing `tests/test_public_tool_process.py` now injects a deliberately fake guard **only when it also injects a fake process**. The production Windows default constructor always installs the native guard.

## Boundaries, not inflated security claims

- **Windows Job Objects manage resource and process trees; they do not remove a process's normal file and network permissions.** This is not AppContainer, a restricted access token, an authenticated user-presence check or a hardened OS sandbox. A malicious process under the same Windows account can still potentially access personal files; keep personal/mutating tools disabled.
- Matching Windows SIDs verifies the OS account of a process, **not** that the human user clicked a button or approved anything. GUI consent is still an in-process assertion. The local process is not signed or protected against a malicious user-session process.
- The 192 MiB limit applies to Windows **committed process memory**, not total machine RAM, working set size or a measured peak RSS. It is a cap, not a performance benchmark.
- Job attachment is performed before trusted tool input; Python child startup and imports occur before attachment, so this is not a zero-execution suspended launch. Requiring kernel gating before handing off intent is a meaningful improvement but not full exploit containment.
- If the Windows job cannot be created/assigned under nested job constraints or OS policy, the action must **fail closed**, not silently downgrade to an unrestricted child. Linux remains a separate unsupported OS guard path; Ubuntu CI does not imply Linux sandboxing.
- Job closure or child kill cannot unsend an HTTP request already transmitted. There is no guaranteed remote cancellation, and GitHub public API availability on the owner's actual computer remains unverified.
- No private GitHub repos, arbitrary paths, GitHub writes, secrets, or automatic tool execution by LLM are introduced.
- Two-way sync for official consumer ChatGPT/Claude/Gemini apps (Option C) remains externally blocked by unverified supported interfaces. Do not quietly substitute API chats.

## Verification gate

Run complete Windows and Ubuntu GitHub Actions for the **final SHA**. Windows native tests must PASS (not skip); offline child launch and kernel membership must be supported. If hosted Windows forbids nested Job assignment, do not call the feature verified until a safe fix or a documented fail-closed unsupported status. Evidence in `docs/progress-log.md` must distinguish code validation from real owner's Windows device acceptance.

## Sources

- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information
- https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation
- https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject

## Next gate

Windows restricted-token/AppContainer or separately provisioned broker with ACL controls and manual owner-machine acceptance, before any private data or mutating tool is considered.