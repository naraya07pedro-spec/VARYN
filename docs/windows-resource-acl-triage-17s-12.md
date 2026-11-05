# VARYN 17S-12 | Windows startup resource ACL triage

Date: 2026-11-05. Scope: **offline native Windows diagnostics and fail-closed capability reporting**. No production tool permission changes, no personal files accessed, no arbitrary shell tool enabled, no consumer-app history sync integration.

## Known baseline

- 17S-10 proved **restricted THREAD impersonation** with \`S-1-5-12\` can deny a fresh open on a known-present synthetic owner-readable file, native Windows CI verified.
- 17S-11 built a genuine **restricted PRIMARY-token** suspended launch using \`CreateRestrictedToken\` / \`CreateProcessAsUserW\`, checked the actual child token and intentionally refused an unrestricted fallback.
- On hosted Windows, restricted Python startup still fails with \`0xC0000022\` (access denied), even without Low MIC. A normal-token test of a disposable copied Python runtime succeeds, while a restricted-primary test **skips with an explicit unavailable reason**. Thus no production read-isolation proof exists; \`ProcessRepoFetcher.status()['windows_restricted_primary_production_enabled']\` remains false. The last verified 17S-11 CI was [run #41888725513](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41888725513): 751 discovered tests on both OSes, zero failures, Windows 15 skipped, Ubuntu 76 skipped. CI green here does NOT certify restricted-primary startup.
- Microsoft's documentation says \`DISABLE_MAX_PRIVILEGE\` leaves \`SeChangeNotifyPrivilege\` and the OS applies two ACL access checks for restricted SIDs. Therefore it would be wrong to assert that all previous errors were caused by directory traversal permissions or by low MIC without native evidence.

## Implemented 17S-12

- \`tests/windows_startup_acl_probe.py\`: an offline, disposable process first performs normal kernel \`CreateFileW\` opens for a bounded resource set; then it uses a real Windows \`CreateRestrictedToken\` (\`S-1-5-12\`, \`DISABLE_MAX_PRIVILEGE\`) and temporary \`ImpersonateLoggedOnUser\`, repeats the opens, reverts impersonation, and closes handles. Access categories are \`allowed / denied / missing / other\`. It never reads file **contents**, never executes untrusted code, does not send data to providers or network services, and emits **only resource-category keys**, not paths or user SID bytes.
- \`tests/test_windows_startup_acl_probe.py\`: constructs **only synthetic test files** and a disposable trusted Python EXE/DLL copy. A test-created file is granted restricted SID read/execute via \`icacls\` **only within the temporary runtime folder**; a separate owner-readable synthetic file is deliberately not granted this SID. Both controls must pass under normal and restricted thread tokens, with the denied file present and unmodified. The diagnostic also probes fixed categories: trusted EXE copy, Python DLL copy, runtime directory and three ancestor directories, and the fixed Windows system \`kernel32.dll\`. Only category labels and access outcomes may appear in logs. Missing or malformed target requests cannot certify protections.
- \`.github/workflows/memory-checks.yml\` includes a named 17S-12 gate on hosted Windows and Ubuntu. Windows must execute the native test; Ubuntu skips native Win32 checks and cannot attest Windows security.
- The probe remains in \`tests/\` and is excluded from the desktop source ZIP. The real production GitHub metadata subprocess retains its previous constraints and **does not use the new probe or restricted-primary launcher**.

## Interpretation and limitations

A resource being readable under restricted **thread impersonation** shows only that a corresponding file-handle ACL permits the operation. A process loader also opens section objects, may use registry and named objects, and has process-creation and desktop/window-station access constraints. This diagnostic **does not observe every Windows loader operation** and cannot directly identify the complete root cause of \`0xC0000022\`. It is a bounded, evidence-driven elimination test. A successful diagnostic must never be described as successfully launching a restricted primary-token child.

The next step after evaluating this report is to investigate **the specific denied object with safe Windows loader tracing** or adopt a properly packaged AppContainer / ACL-separated broker, test the genuine restricted primary process startup with the real runtime, and require an actual fresh read-denied proof on a known-existing synthetic file. If actual restricted startup remains impossible, no private-file or mutating tool should be enabled.

17S-12 CI verification status: pending exact final HEAD at the time of this document's creation. PR #1 remains OPEN/DRAFT; \`main\` untouched. Option C automatic bidirectional synchronization of official ChatGPT/Claude/Gemini consumer histories remains unverified and is not replaced by a new app or a provider API.

## Primary Windows reference

- https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken
- https://learn.microsoft.com/en-us/windows-hardware/drivers/ifs/checking-for-traverse-privilege-on-irp-mj-create
- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
- https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-impersonateloggedonuser
