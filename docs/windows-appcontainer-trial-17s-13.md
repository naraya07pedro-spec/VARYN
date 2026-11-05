# VARYN 17S-13 | Real native Windows AppContainer prototype with tested file-read isolation

Date: 2026-11-05. **Status: OFFLINE NATIVE TEST VERIFIED on hosted Windows; production tool integration NOT enabled.** PR #1 stays DRAFT; main unchanged. This milestone addresses a **bounded synthetic OS security proof**, not the consumer-app Option C requirement.

## Why this succeeded where 17S-11 failed

17S-11's ordinary restricted-primary-token Python process could not initialize the runtime on hosted Windows (\`0xC0000022\`). 17S-12 then proved that a restricted **thread** could not open some host runtime ancestor directories and system DLLs; that test never established the exact loader failure. Instead of modifying system or personal ACLs, 17S-13 uses Microsoft's native **AppContainer** process model and profile-owned storage.

The actual process is created via:
- \`CreateAppContainerProfile\` with a **unique profile name**, zero requested capability SIDs, and deliberate refusal to reuse an existing profile.
- \`InitializeProcThreadAttributeList\` and \`UpdateProcThreadAttribute(PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES)\` in \`STARTUPINFOEX\`, using the **OS-issued package SID**.
- \`CreateProcessW\` with \`EXTENDED_STARTUPINFO_PRESENT\`, \`CREATE_SUSPENDED\`, \`bInheritHandles=FALSE\`, a fixed trusted Python command, and a minimal allowlisted environment (\`SystemRoot\` and \`LOCALAPPDATA\` only). The full parent environment, provider tokens, credentials, user prompts and model instructions are never passed.
- Before resuming, \`OpenProcessToken\` + \`GetTokenInformation\` attest \`TokenIsAppContainer=1\`, \`TokenAppContainerSid\` equal to the profile's package SID, and a zero count of \`TokenCapabilities\` in the **actual child primary token**. No fallback to an ordinary \`Popen\` exists.
- A copied Python executable, required DLLs and limited standard-library files are staged **only in storage returned by \`GetAppContainerFolderPath\`** for that newly created profile. The original Python installation, user file ACLs and Windows system files are not modified.
- The trusted subprocess has an 8-second bounded execution window, fixed exit-code protocol, cleanup of all process handles and copied runtime files, and \`DeleteAppContainerProfile\` for only the profile created in the same call. The experiment runs only with Windows GitHub Actions variables and explicit \`VARYN_CI_APPCONTAINER_TRIAL=1\`. Normal desktop invocation is rejected.

## Real dual-control file-read security proof

The parent constructs exactly two **new, disposable, synthetic** test files:

1. An authorized file within the test AppContainer's own storage, with fixed bytes \`varyn-17s13-granted\`.
2. A known-present file in a separate host-owned temporary directory, with fixed bytes \`varyn-17s13-owner-only\`. The parent **reads and verifies this file exists and has the expected bytes** before the child launch.

Inside the **actual AppContainer process**, fixed Python code first reads and verifies the authorized file. Only then does it attempt to open the second owner file. It returns exact marker \`73\` **only** if the authorized read succeeds **and** the second open raises \`PermissionError\`. Distinct non-success codes detect permitted private read, missing file, other exceptions, or failure to read the authorized file. This prevents a startup crash or nonexistent target from masquerading as successful isolation.

On the hosted Windows runner, the fixed process successfully ran Python; both controls completed and the owner-file read was kernel-denied. This is **a demonstrated isolation property for that synthetic fixture**, not a guarantee for every Windows document, network path, privileged handle, GUI channel or owner device.

## CI history, including findings and repairs

- [Red #41958550217](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41958550217): an application-side lower bound incorrectly rejected Win32's valid \`InitializeProcThreadAttributeList\` length. Fixed using the documented first-call \`ERROR_INSUFFICIENT_BUFFER (122)\` contract; profile cleanup ownership is set immediately on successful creation.
- [Red #41958741709](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41958741709) and [#41958921643](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41958921643): \`CreateProcessW\` failed with \`203=ERROR_ENVVAR_NOT_FOUND\`. The explicit minimal environment lacked \`LOCALAPPDATA\`, which Windows uses for AppContainer profile storage. Adding **only** \`LOCALAPPDATA\` resolved this stage, with no wholesale environment inheritance.
- [Green #41959168941](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41959168941): the **actual suspended AppContainer child primary token** was verified and the temporary profile deleted; the Python image still exited \`0xC0000135\` due to missing DLL/runtime access.
- [Green #41959737518](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41959737518): copying Python's trusted runtime into its **own AppContainer profile folder** enabled it to run fixed code and return the intended \`73\` marker. This was runtime execution evidence only.
- **[Verified CI #41960224522](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41960224522)**, exact functional-test SHA \`6edc02bd2e73992cf129b27f50a1d22e9e405601\`: hosted Windows and Ubuntu **SUCCESS**. Full suite **761 discovered tests per OS, zero failures**; Windows 17 skipped. Crucially \`test_native_python_denies_present_owner_only_file_after_granted_read ... ok\` actually ran on Windows. Log: \`Python executed=True; synthetic granted read=True; synthetic owner-only read denied=True; exit_status=0x49\`. The native test runs twice, in the full suite and dedicated 17S-13 CI step; it was not skipped. Ubuntu cannot attest Windows but must preserve the portable fail-closed policy tests.

## Hard boundaries: what 17S-13 does NOT establish

- This native test-only AppContainer controller is **not connected** to production \`ProcessRepoFetcher\`, desktop GUI, provider requests, file grants or the general-purpose agent. Production \`os_sandbox=False\` and \`windows_restricted_primary_production_enabled=False\` remain truthful. It provides no permission to turn on private-file tools, arbitrary command execution, GitHub writes or automatic replay.
- An AppContainer without capability SIDs is not a blanket assurance that networking, IPC, COM, registry, package ACL or inherited resources are secure in every scenario. No real network egress denial, broker IPC authorization, side-channel resistance or actual owner laptop acceptance has been demonstrated. A fixed test with \`bInheritHandles=FALSE\` is not a production handle-leak audit.
- The test uses ordinary AppContainer, **not LPAC**. All Application Packages default ACLs might give access to some broader host resources. Production needs explicit threat-model validation and ideally a narrower LPAC/broker architecture where feasible.
- **Next engineering gate:** introduce a narrowly scoped parent-host broker and authenticated, bounded tool request/response transport to an AppContainer child, then enforce allowed operations, cancellation, output validation, no persistent approvals or automatic replay, Job Object containment and real negative access tests. Require hosted CI plus user hardware validation before handling sensitive data.
- Option C means automatic two-way history/memory synchronization with **official ChatGPT, Claude and Gemini consumer applications**, not a replacement custom chat and not API-only. 17S-13 does not meet or weaken that external-integration requirement.

## Primary references

- [Microsoft: Launch an AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer)
- [Microsoft: CreateAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile)
- [Microsoft: GetAppContainerFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-getappcontainerfolderpath)
- [Microsoft: SECURITY_CAPABILITIES](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-security_capabilities)
- [Microsoft: TOKEN_APPCONTAINER_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-token_appcontainer_information)
- [Microsoft: DeleteAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deleteappcontainerprofile)

Do not merge based only on synthetic proof. Final CI on the last documentation HEAD must also be checked and documented in PR #1, while main remains untouched.
