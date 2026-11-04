# VARYN 17S-11 | Windows restricted primary-token startup, blocked pending trusted loader

Date: 2026-11-05. Status: **IMPLEMENTED EXPERIMENTAL LAUNCHER; FUNCTIONAL ISOLATION NOT VERIFIED**. This checkpoint does not enable any new private-file or mutating tools and must not be described as a working production sandbox.

## What was actually implemented

\`varyn/windows_restricted_primary.py\` implements an experimental, fail-closed native Windows launch sequence:

1. Open owner primary token with least necessary rights, including \`TOKEN_ADJUST_DEFAULT\` needed by \`SetTokenInformation\`.
2. Use \`CreateRestrictedToken\` with **S-1-5-12 (NT AUTHORITY\RESTRICTED)** to obtain a restricted **primary** token; read back exact \`TokenRestrictedSids\`.
3. Construct and read back token's \`TokenDefaultDacl\` on newly created kernel objects, granting owner, SYSTEM, and the restricting SID. This does not alter ACLs on existing files, directories or Python installation.
4. Use \`CreateProcessAsUserW\` with a fixed trusted Python executable, minimal \`SystemRoot\` environment, \`bInheritHandles=FALSE\`, noninteractive mode and \`CREATE_SUSPENDED\`. Verify the **actual child process's** primary token restricted SID before any resume. No unrestricted Popen fallback.
5. Return a bounded process wrapper with explicit resume/wait/kill/close. This is **not a production tool transport** and is not used by the desktop's \`ProcessRepoFetcher\`. The existing Job Object and Low MIC guard would have to be integrated and tested separately.

\`tests/test_windows_restricted_primary.py\` provides an offline native Windows diagnostic, plus portable fail-closed policy tests. The tests copy trusted Python binaries, DLLs, core \`encodings\` and \`os.py\` to a disposable sandbox directory and grant \`RESTRICTED\` **read/execute only on that copy** via Windows icacls. There is no modification of actual user documents, host Python runtime ACLs or OS folders. A normal Python positive control verifies this copy runs first.

## Adversarial results, including red CI

The functional primary-token read-denial proof is **not established** on hosted Windows:

- [Run #41884799572](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41884799572): first strict-token child exited \`0xC0000142\` (DLL initialization failed) before executing Python.
- [Run #41885172664](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41885172664) and [run #41885611611](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41885611611): experiments with broader Authenticated Users and BUILTIN Users restricting SIDs still exited \`0xC0000022\` (access denied). These SIDs are not accepted as a secure final private-data sandbox.
- [Run #41885960179](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41885960179): the failure remained \`0xC0000022\` **without Low MIC**, so MIC ordering is not a supported root-cause claim.
- [Run #41887055449](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41887055449) isolated a missing \`TOKEN_ADJUST_DEFAULT\` access right when attempting \`SetTokenInformation(TokenDefaultDacl)\`; this right was then added based on Microsoft's native token-rights specification.
- [Run #41887159880](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41887159880) progressed to \`0xC0000135\` (DLL not found) before Python entry.
- [Run #41888142729](https://github.com/naraya07pedro-spec/VARYN/actions/runs/41888142729): the disposable Python runtime **successfully started under the ordinary token**, yet the strict primary-token child still exited \`0xC0000022\`, even without Low MIC. Granting \`RESTRICTED\` RX on the runtime copy alone did not resolve all startup-object dependencies.

A process exiting with these OS codes **does not prove** any requested file read was denied. The tests now record the inability to execute as explicit \`SKIP\` with diagnostic code, instead of misleadingly passing a read-denial assertion. The native positive and absent-file assertions remain mandatory **if** a restricted child actually boots. Future host environments that support it can run both checks. The CI green result, if achieved, means the existing app and negative gates still work; it **does not mean this capability is available**. There must be no "verified read sandbox" status based on skipped tests.

## Security decision

Production \`ProcessRepoFetcher.status()\` explicitly exposes \`windows_restricted_primary_production_enabled=False\`, \`os_sandbox=False\` and \`windows_mic_blocks_private_reads=False\`. No private files are passed to any network child. No token, model, process or GUI can self-grant private-file access through this experiment.

**Next:** implement a trusted child runtime whose entire loader dependency chain and kernel security objects can be used under \`RESTRICTED\` (or pivot to a verified Windows AppContainer / ACL-separated broker). Determine the denied OS object using trustworthy Windows native tracing, preserve explicit handle allowlisting, and prove actual restricted process execution **and** known-existing private synthetic file read rejection. Only then integrate fixed public GitHub transport and existing Low MIC/Job containment. Owner Windows acceptance is still required.

Original Option C requirement, automatic bidirectional histories of official consumer ChatGPT/Claude/Gemini apps, remains an unsolved separate product gate. PR #1 stays draft, main remains unchanged.

Primary references:
- https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken
- https://learn.microsoft.com/en-us/windows/desktop/api/processthreadsapi/nf-processthreadsapi-createprocessasuserw
- https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-token_default_dacl
- https://learn.microsoft.com/en-us/windows/win32/secauthz/access-rights-for-access-token-objects
