# VARYN 17S-17 | Native pre-resume handle identity and kill-on-close Job containment

Date: 2026-11-05. Status: **verified on hosted Windows for synthetic AppContainer child**, plus portable negative-policy regressions. **Not a production broker, complete handle-table audit, or private-file sandbox.**

## Starting point and architectural intent

17S-16 established two-anonymous-pipe communication with a real zero-capability AppContainer primary process using an exact \`PROC_THREAD_ATTRIBUTE_HANDLE_LIST\`. The child-side Python \`GetHandleInformation\` probe of an intentionally excluded inheritable event returned ambiguous \`OSError(errno=22 / EINVAL)\`, so it did **not** prove the event was absent. Likewise, 17S-16 did not attach a Job Object to the AppContainer process. Despite its green CI, production \`os_sandbox=False\` remained correct.

17S-17 repairs both limitations **without granting new capabilities or reading any real personal files**. No native test runs on the owner's PC; real OS tests require explicit opt-in on ephemeral GitHub Actions Windows.

## Delivered native implementation

### 1. Parent-native identity checks while child still suspended

\`varyn/windows_suspended_handle_audit.py\` runs in the trusted host before \`ResumeThread\`. Using native \`DuplicateHandle\`, it duplicates the two expected handle values **from the actual suspended child process back into the parent**, then uses \`KernelBase.dll!CompareObjectHandles\` to verify that they reference the *same two anonymous-pipe kernel objects* as the trusted parent expects. It separately probes the **deliberately inheritable but not allowlisted event**, requiring either \`ERROR_INVALID_HANDLE\` or a proven different kernel object if that numeric slot was reused. If the event itself appears in the child, launch fails closed. No reliance on child-reported identity or Python's \`errno=22\`.

This is a proof about **three known fixture objects at the pre-resume instant**, not exhaustive inspection of every child handle, dynamically opened system handle, duplicate, IPC side channel or concurrently spawning parent process. The returned \`full_handle_table_audited=False\` is deliberate.

Initial CI was red because the code searched for \`CompareObjectHandles\` in \`kernel32.dll\`, but Microsoft documents its DLL as **\`KernelBase.dll\`**. Fixed the trusted native lookup; no test skip or ACL widening.

### 2. Native suspended AppContainer Job Object guard

\`varyn/windows_child_job.py\` adds \`WindowsSuspendedAppContainerJob\`, an AppContainer-specific guard that **does not rewrite the child token's mandatory integrity level** (the existing job class for non-AppContainer workers had Low MIC behavior unsuitable to reuse blindly). It creates and attaches a Windows Job Object **while the child is still suspended**, with the OS-native flags:

- \`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE\`
- \`JOB_OBJECT_LIMIT_ACTIVE_PROCESS\` with maximum **1** process
- \`JOB_OBJECT_LIMIT_PROCESS_MEMORY\` with **192 MiB** per process

The trusted parent reads the actual Job limit object back using \`QueryInformationJobObject\`, verifies the flag/value combination and \`IsProcessInJob\` membership, and refuses to \`ResumeThread\` until all checks pass. Missing process handles, invalid memory caps, unavailable Job APIs or assignment failures are fail-closed. No unrestricted fallback.

The \`inherited_trial=True\` AppContainer path now requires both the independent native handle fixture proof **and** Job attachment before any synthetic stdin request or child execution. The trusted host closes its child pipe endpoints after process creation, and closes the Job during cleanup.

### 3. Real kill-on-job-close, not a mock or flag-only check

\`run_ci_only_zero_capability_trial(cancel_trial=True)\` runs a separate fixed, offline AppContainer child with no user input, network, provider access, shell request or private files. The child **really executes** by creating one fixed marker inside its temporary profile-owned runtime directory, then sleeps. The host must confirm it reads the exact marker **and** that \`GetExitCodeProcess == STILL_ACTIVE\` immediately before closing the Job. It then invokes the Job's \`close()\` and requires \`WaitForSingleObject\` to confirm termination within three seconds, with no child still active. The profile and runtime copy are removed. Unexpected early exit, missing marker or timeout are hard failures, not skips.

The test uses \`TerminateProcess\` only as an emergency cleanup fallback if the native Job path fails, **not** as evidence of successful kill-on-close. The native child is tied to the same verified zero-capability AppContainer primary token.

### 4. Tests and CI

- \`tests/test_windows_appcontainer_trial.py\` now has **hard native Windows tests** for matching two expected pipe objects, excluding the fixture decoy event, readback of Job membership and resource limits, actual Job-close termination of a live child, original granted/denied synthetic-file controls, nonce-correlated bounded request/response and parent SQLite claim-before-dispatch. Neither invalid handle nor killed-process results are faked.
- \`tests/test_windows_appcontainer_job.py\` adds portable negative tests for rejected missing child handle, invalid memory cap, no Win32 on Ubuntu, and unchanged production \`os_sandbox=False\`.
- \`.github/workflows/memory-checks.yml\` runs the relevant native Windows AppContainer Job/handle/cancellation gate early, and adds a cross-platform Job-policy regression step. The full tests and dedicated older 17S-13/17S-16 checks still run.

**Early demonstrated success** [Actions #41972568690](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41972568690), code SHA \`cfa5af3815ff25750045f2a5286699b7cf16b131\`: Windows and Ubuntu both COMPLETED SUCCESS; **789 tests per OS, 0 failures**, Windows 19 skipped / Ubuntu 89 skipped. Native Windows logs explicitly show:
- \`test_real_appcontainer_excluded_decoy_handle_is_os_attested ... ok\`
- \`test_job_membership_and_limits_attested_before_child_runs ... ok\`
- \`test_real_job_kill_on_close_terminates_live_appcontainer ... ok\`
- \`17S-17 native AppContainer: kernel pre-resume two pipe identities and excluded decoy proved; Job membership and 192MiB/process=1 limits attested; synthetic IPC and owner-only read denial confirmed\`
- \`17S-17 native AppContainer Job close terminated an actual running fixed synthetic child after ready marker\`.

Earlier failed CI [#41972181975](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41972181975) identified the KernelBase import error; green result followed after correction. Do not reinterpret the earlier red as permission bypass.

Final commit including an additional explicit \`STILL_ACTIVE\` check, portable negative tests and documentation requires a **separate exact-HEAD CI check**; final PR audit comment will record that result rather than treating the first successful source-only commit as final.

## Security boundary and required next work

**This milestone is verified native OS containment of a fixed synthetic CI child**, NOT a production agent, full Windows sandbox, LPAC, broker-held private-file authorization or general network egress denial. No sensitive tool, owner document, official app session, provider credential, user prompt or arbitrary executable was passed to the child.

Important remaining risks:
- The fixture audit checks exactly the two intended pipe handles and one intentionally excluded event at the suspended instant; there is **no full process handle-table enumeration** and no proof against all other Windows object exposure.
- \`HANDLE_FLAG_INHERIT\` is temporarily set on two handles. A separate concurrently spawning parent thread/process that bypasses this controlled launch could inherit them. No product-wide process creation lock or hardened dedicated launcher has been proven.
- The 192 MiB limit and one-process restriction are natively configured and read back. The kill-on-close behavior is directly tested. **Actual memory-overuse and second-process-spawn denial tests were not performed**. Job limits are not proof of those independent adversarial behaviors in every environment.
- The bounded fixed pipe transport is test-only, with no real broker-issued capability tokens, owner approvals, production GUI cancellation, durable owner-side audit journal, malicious tool-result integrity, or hard network egress test. Existing SQLite journal tests prove no-replay semantics for synthetic request IDs but not universal side-effect exactly-once delivery.
- Hosted Windows runner is not the owner's Windows computer. There is no owner-device acceptance.
- Production \`ProcessRepoFetcher.status()['os_sandbox']=False\` and \`windows_restricted_primary_production_enabled=False\` stay unchanged; private-file and mutating agent operations stay disabled.
- User's Option C requires full bidirectional history and memory sync with **official ChatGPT, Claude and Gemini consumer applications**, not custom UI or API-only replacement. This milestone does not satisfy it.

## Recommended next gate

17S-18 should turn this verified primitive into a **narrow, parent-owned, consent-gated broker** with one read-only synthetic-to-real resource class, immutable file/operation allowlist, trusted parent-side authorization and persistently auditable no-replay dispatch, concurrency-safe handle creation, process limits/cancellation, malicious/oversized result tests, explicit network policy and real owner-device acceptance. Alternatively avoid private resource access until the threat model is fully audited. Keep PR #1 OPEN/DRAFT, main untouched.

**References:** [Microsoft CompareObjectHandles](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-compareobjecthandles), [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [Microsoft JobObjectExtendedLimitInformation](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information), [Windows handle inheritance](https://learn.microsoft.com/en-us/windows/win32/procthread/inheritance).
