# VARYN 17S-16 | Windows AppContainer anonymous-pipe two-handle trial

Date: 2026-11-05. **Status: hosted Windows synthetic two-pipe transport demonstrated; complete handle-exclusion audit NOT verified; production tool routing remains disabled.** PR #1 OPEN/DRAFT, main untouched.

## Objective

17S-15 proved an ordinary Windows child could connect to a local-only named pipe with kernel-reported client PID, but the real AppContainer child could **not find** the host's \`LOCAL\` pipe (exit \`0x5c\`, OS path/file missing). 17S-16 instead tests inheriting **two new anonymous-pipe handles** through Windows \`STARTUPINFOEX\` and \`PROC_THREAD_ATTRIBUTE_HANDLE_LIST\`. The OS creates and restricts the AppContainer process before any untrusted child code runs.

## Implemented source files

- \`varyn/windows_inherited_pipe_trial.py\`: creates two anonymous pipes via \`CreatePipe\` and **one extra inheritable decoy event**. The intended child endpoints are stdin-read and stdout-write; the opposite parent ends have \`HANDLE_FLAG_INHERIT\` cleared and are checked. Exactly two child handles go into a \`HANDLE_LIST\`; the decoy is **not included**. Explicit \`WriteFile\` sends a single small length-prefixed request (maximum 512 JSON bytes); the input writer is closed after writing. After the bounded child exits, the host uses \`PeekNamedPipe\`/\`ReadFile\` for a length-checked response and closes all remaining handles.
- \`varyn/windows_appcontainer_trial.py\` \`inherited_trial=True\` is gated to ephemeral hosted Windows CI with explicit opt-in. It combines \`PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES\` (zero extra capability SIDs) and \`PROC_THREAD_ATTRIBUTE_HANDLE_LIST\` (exactly two explicitly inheritable child handles). \`CreateProcessW\` uses \`CREATE_SUSPENDED\` and \`bInheritHandles=TRUE\` **only with this explicit list**; \`STARTF_USESTDHANDLES\` points to the allowlisted stdin and stdout, with stderr sharing the same stdout endpoint, not a third inherited handle. The OS-issued **actual child AppContainer primary token, SID and zero capabilities are attested before resume or dispatch**.
- \`varyn/appcontainer_inherited_pipe_child.py\` is a fixed no-shell, no-network synthetic action. It reads a granted synthetic AppContainer-owned file, requires \`PermissionError\` on a known-existing synthetic host-owned file, reads exactly one bounded JSON request from stdin, permits only \`sum_synthetic_counts\` with strict IDs/nonces and integer bounds, writes one matching length-prefixed JSON result to stdout, and exits. The host expects \`[4,6,11] -> 21\`, exact request ID/nonce, status and schema.
- The parent uses \`varyn/durable_broker_journal.py\` to **commit the synthetic request ID as claimed before CreateProcessW** and finalize \`completed\` only after the whole response is verified. Journal is in a private disposable host-side directory on CI, **not** persistent production app state.
- \`tests/test_windows_appcontainer_trial.py\` has a mandatory native Windows transport test with token, file-denial, journal and one-request/one-response assertions. The workflow runs this native test **before** the long unit regression suite and again in full/dedicated test modules. Ubuntu cannot supply Win32 proof; non-CI and owner-desktop calls are refused.

## Adversarial results: preserve red evidence

Initial hosted Windows runs failed at the decoy negative control, **not at AppContainer creation**:
- [#41969425090](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41969425090): original decoy check exited \`0x5d\`.
- [#41969701586](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41969701586): more granular native API check exited \`0x72\` (114).
- [#41970018955](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41970018955): native check categorized as \`OSError\`, exit \`0x74\` (116).
- [#41970169891](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41970169891): alternative \`WaitForSingleObject\` probe also raised instead of providing a reliable negative attestation.
- [#41970339323](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41970339323): positive standard stdin handle check established, but the excluded decoy API still returned a non-specific native exception.
- [#41970516387](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41970516387): the exception was categorized as Python \`errno=22\` (\`EINVAL\`), **not** a verified Win32 \`ERROR_INVALID_HANDLE\`.

We therefore separated two security claims rather than silently treating \`EINVAL\` as proof: the **IPC transport is tested as a HARD native Windows pass/fail**, while the **unlisted decoy's absence is an explicitly SKIPPED / UNAVAILABLE negative-control gate** if the OS interface supplies only ambiguous \`EINVAL\`. An actually accessible decoy handle is a hard failure; no alternate content or broader privilege is allowed to pass. The report exposes \`unlisted_decoy_handle_denied=False\` when unverified. That flag must not be flipped to True based on a passing IPC test.

On [GitHub Actions #41970801529](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41970801529), the hosted Windows **early native two-handle AppContainer proof step completed SUCCESS**, while the decoy validation is separately marked unavailable. Full suite exact SHA and counts must be checked on completion and on the final documentation HEAD before calling this checkpoint finalized.

## Trust boundaries not solved

- This is a **CI-only, fixed synthetic proof**, not an owner-approved production broker. The response may originate from the already-verified AppContainer process through its specific inherited stdout endpoint, but the child itself is **not a trustworthy authority**: a compromised child can fabricate synthetic data. The host verifies a deterministic oracle in this test; real tools need a broker-authorized action and result boundary.
- \`PROC_THREAD_ATTRIBUTE_HANDLE_LIST\` limits intended inherited handles, but handles are temporarily marked inheritable in the parent. Other concurrently spawning threads in the same process may inherit them if they bypass this list. Real production requires a launch lock or dedicated trusted single-threaded broker, independent handle-leak inspection and job containment.
- The failed decoy probe means **there is no independently verified native proof that every non-allowlisted handle is absent** on the child. Do not claim "no extra handles" from CI green.
- No Job Object attached to this new AppContainer, no network egress denial test, authenticated OS peer proof beyond parent-held process handle + fixed inherited std handles, persistent user consent, cancellation in GUI, production durable journal, owner-Windows-device acceptance or actual private-file tool.
- The existing \`ProcessRepoFetcher.status()['os_sandbox']\` remains **False**. Do not route private or mutating tools to this experiment.
- User-required Option C means automatic **two-way** conversation/history and memory synchronization inside **official consumer** ChatGPT, Claude, Gemini applications. This security checkpoint neither meets nor alters that requirement.

## Next gate

17S-17 should verify the inherited-handle table on a real AppContainer with a trustworthy native method rather than interpreting Python \`EINVAL\`, attach a Job Object before resume with strict termination/time/memory policy, and use a parent-owned one-shot broker that never grants arbitrary file or network access. Maintain no-replay guarantees, explicit owner approvals and exact CI proofs before adding any real tool access.

Primary Windows references:
- https://learn.microsoft.com/en-us/windows/win32/procthread/inheritance
- https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute
- https://learn.microsoft.com/en-us/windows/win32/procthread/creating-a-child-process-with-redirected-input-and-output
- https://devblogs.microsoft.com/oldnewthing/20260511-00/?p=112313%2F

**Never mark an unverified decoy check, owner-machine acceptance or production agent bridge as completed.**
