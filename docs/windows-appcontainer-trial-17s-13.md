# VARYN 17S-13 | Native Windows AppContainer primary-process experiment

Date: 2026-11-05. This is a **CI-only experiment with Windows OS security primitives**, not a production broker, not a working private-file sandbox, and not a replacement for the user's official-consumer-app synchronization requirement (Option C).

## Baseline and design decision

17S-12 verified real restricted **thread** access checks on a disposable Python executable and DLL, Windows system DLL, ancestor directories and two synthetic files, but 17S-11 restricted **primary** process startup remained blocked (\`0xC0000022\`). Blindly editing OS/System32/user directory ACLs to force Python startup is not an acceptable product design. Microsoft's supported path to launching an AppContainer is \`CreateAppContainerProfile\`, a \`SECURITY_CAPABILITIES\` attribute in \`STARTUPINFOEX\`, \`CreateProcessW\` with \`EXTENDED_STARTUPINFO_PRESENT\`, and an OS-issued AppContainer token in the child process.

## Implemented 17S-13 code

- \`varyn/windows_appcontainer_trial.py\` provides exactly **one opt-in offline trial**, \`run_ci_only_zero_capability_trial()\`. It refuses to run unless Windows, \`GITHUB_ACTIONS=true\`, \`RUNNER_OS=Windows\` and an explicit \`VARYN_CI_APPCONTAINER_TRIAL=1\` are set. It is not connected to the desktop GUI, API client, public GitHub tool or any owner-file tool. The normal owner's PC never creates profiles via the normal app flow.
- Each test creates a unique disposable profile under the ephemeral CI user with \`CreateAppContainerProfile\`. On any failure, only a profile created by the same invocation may be deleted, using \`DeleteAppContainerProfile\`; it refuses to reuse or delete an unrelated existing profile.
- \`InitializeProcThreadAttributeList\` and \`UpdateProcThreadAttribute(PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES)\` construct the AppContainer process attribute with a valid package SID, **zero requested capability SIDs**, and zero inherited handles. The child command is a **hardcoded** trusted Python \`-I -S\` script with a harmless exit-code marker, not arbitrary user-provided command execution.
- The process is created **suspended**. Before \`ResumeThread\`, the parent reads the actual newly created child's **primary token**, requiring \`TokenIsAppContainer=1\`, package SID identical to the profile SID, and \`TokenCapabilities\` count zero. Any failure refuses launch without substituting a regular unrestricted child. After resume it waits with a bound and forcibly cleans up on timeout. The report contains only booleans, numeric exit codes and whether the temporary profile was deleted, never user paths, SID bytes, output streams or file contents.
- \`tests/test_windows_appcontainer_trial.py\` requires ordinary desktop/non-CI invocations to reject profile creation, checks that production still reports \`os_sandbox=False\`, and on ephemeral hosted Windows checks native AppContainer child/token/cleanup. If Python never reaches its marker, the runtime test remains explicitly unavailable rather than claiming successful file read isolation.
- \`.github/workflows/memory-checks.yml\` includes a named CI gate for this native trial on Windows/Ubuntu. On Ubuntu no AppContainer OS access is claimed.

## Adversarial CI findings so far

- First native Windows suite on [red run #41958550217](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41958550217) found a defective application-level size threshold for \`InitializeProcThreadAttributeList\`, not a proven kernel rejection. The Win32 size-query's documented \`ERROR_INSUFFICIENT_BUFFER\` response and returned buffer size are now validated; a successfully created profile is marked as owned before SID validation so cleanup occurs even on an unexpected SID.
- Second native Windows suite on [red run #41958741709](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41958741709) created the profile and initialized security attributes but \`CreateProcessW\` refused to launch the AppContainer child. The most recent diagnostic reports **only the numeric Windows error code**, not target paths or raw token state.
- These failures are retained as evidence. Until the child token is actually inspected, **no native AppContainer child attestation has occurred**, even if unrelated tests are green. Hosted CI can create a profile but the ability to start and run a child is still an open question at this stage.

## Security gates that remain non-negotiable

1. \`CreateProcessW\` must create a genuinely suspended AppContainer child; read back \`TokenIsAppContainer\`, profile SID and empty capability set on the **actual process**. A regular \`subprocess.Popen\` is not an acceptable fallback.
2. The child must truly execute, not merely be created and die during Python/DLL loading. A successful exit marker is a separate explicit gate.
3. With an actual executable child, verify it cannot read a **known-present** synthetic owner-only file and that the broker accepts only an explicit grant through verified OS-controlled handles. No existing user documents or credentials are used in tests.
4. Add kill-on-job-close, time/memory limits, no-handle-leak checks, bounded authenticated parent-child communication, cancellation and owner consent before any production tool capability is enabled. Test on owner's Windows device separately.
5. Keep \`ProcessRepoFetcher.status()['os_sandbox']=False\` and \`['windows_restricted_primary_production_enabled']=False\` until an actual production integration passes these gates. No private files, mutating tools or automatic official consumer-app history synchronization are enabled here.

## References

- Microsoft: [Launch an AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer).
- Microsoft: [CreateAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile).
- Microsoft: [InitializeProcThreadAttributeList](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-initializeprocthreadattributelist).
- Microsoft: [SECURITY_CAPABILITIES](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-security_capabilities).
- Microsoft: [TOKEN_INFORMATION_CLASS](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_information_class).
- Microsoft: [DeleteAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deleteappcontainerprofile).

PR #1 stays OPEN/DRAFT; \`main\` untouched. Final hosted CI on the exact last HEAD and the precise Windows failure reason must be added to the PR evidence trail. Do not merge based on a diagnostic skip.
